import os
import zmq
from Queue import Queue
import ConfigParser
from threading import Lock
from threading import Thread
from gdrive import GDrive
"""
At run. Read config file.
Read all the image file names based on time created and update a queue
start ipc worker to update queue
start threads to process queue
"""

IMG_DIR = os.path.join(os.path.expanduser('~'), '.cctvmails_temp', 'gdrive')
CONFIG_FILENAME = "config.ini"

class GDriveUploader(object):
    def __init__(self):
        self.img_queue = Queue()
        self.GDrive = GDrive()
        self.config = ConfigParser.ConfigParser()
        self.config_path = os.path.join(IMG_DIR, CONFIG_FILENAME)
        self.config_lock = Lock()
        if not os.path.isfile(self.config_path):
            os.mknod(self.config_path)
        self.config.read(self.config_path)
        self.create_pending_queue()
        for x in range(2):
            ipc_workers = IPCWorker(self)
            # Setting daemon to True will let the main thread exit even though the
            # workers are blocking
            ipc_workers.daemon = True
            ipc_workers.start()
        for x in range(4):
            queue_workers = QueueWorker(self)
            # Setting daemon to True will let the main thread exit even though the
            # workers are blocking
            queue_workers.daemon = True
            queue_workers.start()

    def create_pending_queue(self):
        file_paths = []
        for root, dirs, files in os.walk(IMG_DIR):
            for filename in [os.path.join(root, name) for name in files]:
                if not filename.endswith('.jpg'):
                    continue
                file_paths.append(filename)
        file_paths.sort(key=lambda x: os.stat(x).st_mtime, reverse=False)
        for i in range(len(file_paths)):
            self.img_queue.put(os.path.basename(file_paths[i]))

    def update_config_file(self):
        self.config_lock.acquire()
        f = open(self.config_path, "w")
        self.config.write(f)
        f.close()
        self.config_lock.release()


class IPCWorker(Thread):
    def __init__(self, uploader):
        super(IPCWorker, self).__init__()
        self.uploader = uploader
        context = zmq.Context()
        self.sock = context.socket(zmq.PULL)
        self.sock.connect("tcp://127.0.0.1:5690")

    def run(self):
        while True:
            message = self.sock.recv()
            self.uploader.img_queue.put(message)

class QueueWorker(Thread):
    def __init__(self, uploader):
        super(QueueWorker, self).__init__()
        self.uploader = uploader

    def run(self):
        while True:
            img_name = self.uploader.img_queue.get()
            self.uploader.img_queue.task_done()
            parts = img_name.split("#")
            unique_email = parts[0]
            camera_name = parts[1]
            date = parts[2].split(" ")[0]
            creds_path = os.path.join(IMG_DIR, unique_email + ".json")
            service = self.uploader.GDrive.get_cred_service(creds_path)
            date_dir_id = ""
            config_changed = False
            """
            check in config if config["unique_email"] is present. if not write it.
            check in config ig config["unique_email"]["date"] is present. Then create the dir and write it.
            upload image with config["unique_email"]["date"] as parent and name camera_name, date
            """
            if unique_email not in self.uploader.config.sections():
                self.uploader.config.add_section(unique_email)
                f = open(creds_path + ".id", "r")
                parent_id = f.read()
                f.close()
                self.uploader.config.set(unique_email, 'parent', parent_id)
                config_changed = True

            if date not in self.uploader.config.options(unique_email):
                date_dir_id = self.uploader.GDrive.create_dir(date, parent_id, service)
                self.uploader.config.set(unique_email, date, date_dir_id)
                config_changed = True

            ret = self.uploader.GDrive.upload_image(os.path.join(IMG_DIR, img_name),
                                                    "%s %s" % (camera_name, parts[2]),
                                                    date_dir_id,
                                                    service)

            if config_changed:
                self.uploader.update_config_file()



runner = GDriveUploader()
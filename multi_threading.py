import os
import uuid
from time import strftime
from threading import Thread


class DataWorker(Thread):
    def __init__(self, server):
        super(DataWorker, self).__init__()
        self.server = server

    def run(self):
        while True:
            mailfrom, data = self.server.data_queue.get()
            ret, user_data = self.server.get_user_info(mailfrom)

            self.server.debug_print("Received user_data: " + str(user_data))

            user_data["camera"] = self.server.get_camera(data, user_data)
            self.server.debug_print(ret)
            self.server.debug_print(user_data["configured"] == 1)
            ret_time = self.server.within_time_period(user_data)

            if (ret and user_data["configured"] == 1 and ret_time):
                self.server.debug_print("cleared to process")
                user_data["id"] = uuid.uuid4()
                imgs = self.server.decode_images(user_data, data)
                user_data["diff_rect"] = None
                if len(imgs) > 2:
                    user_data["diff_rect"] = self.server.get_motion_areas(imgs)
                for i in range(len(imgs)):
                    self.server.img_queue.put((user_data, imgs[i]))
            self.server.debug_print("dataworker done")
            self.server.data_queue.task_done()


class ImgWorker(Thread):
    def __init__(self, server):
        super(ImgWorker, self).__init__()
        self.server = server

    def run(self):
        while True:
            user_data, img = self.server.img_queue.get()
            user_data["detected"] = []
            action_required = False
            if ("People" in user_data["detections"]):
                ret = self.server.detect_faces(img, user_data["diff_rect"])
                if ret:
                    self.server.write_image(img)
                ret = self.server.dp.detect(img, user_data["diff_rect"])
                if ret:
                    self.server.write_image(img)
                    action_required = True
                    user_data["detected"].append("People")
            if action_required:
                user_data["event_time"] = strftime("%d-%h-%Y %I:%M:%S%p")
                self.server.action_queue.put(user_data)
                if ("GDrive" in user_data["actions"] and user_data["gdrive"] != ""):
                    user_data["cvimage"] = img
            self.server.img_queue.task_done()


class ActionWorker(Thread):
    def __init__(self, server):
        super(ActionWorker, self).__init__()
        self.server = server

    def run(self):
        while True:
            user_data = self.server.action_queue.get()
            if ("Email" in user_data["actions"] and user_data["to_email"] != "") and user_data["id"] in self.server.image_dict:
                self.server.send_email_alert(user_data)
            if ("GDrive" in user_data["actions"] and user_data["gdrive"] != ""):
                home_dir = os.path.expanduser('~')
                img_dir = os.path.join(home_dir, '.cctvmails_temp', '.images')
                file_name = user_data["id"]
                self.server.write_image(user_data["cvimage"], img_dir, file_name)
                self.server.GDrive.upload_image(user_data, os.path.join(img_dir, file_name))
                os.remove(os.path.join(img_dir, file_name))
            if user_data["id"] in self.server.image_dict:
                del self.server.image_dict[user_data["id"]]
            self.server.action_queue.task_done()

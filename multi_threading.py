import uuid
from datetime import datetime
from time import strftime
from threading import Thread


class DataWorker(Thread):
    def __init__(self, server):
        super(DataWorker, self).__init__()
        self.server = server

    def run(self):
        while True:
            mailfrom, data = self.server.data_queue.get()
            self.server.data_queue.task_done()
            ret, user_data = self.server.get_user_info(mailfrom)
            # TODO: If ret False, then log it and save the data.

            self.server.debug_print("Received user_data: " + str(user_data))

            user_data["camera"] = self.server.get_camera(data, user_data)
            # self.server.debug_print(ret)
            # self.server.debug_print(user_data["configured"] == 1)
            ret_time = self.server.within_time_period(user_data)

            if (ret and user_data["configured"] == 1 and ret_time):
                self.server.debug_print("cleared to process")
                user_data["id"] = str(uuid.uuid4())
                imgs = self.server.decode_images(user_data, data)
                self.server.debug_print(type(imgs))
                user_data["diff_rect"] = None
                user_data["imgs"] = imgs
                self.server.debug_print(type(user_data["imgs"]))
                user_data["detected"] = {}
                user_data["action_required"] = False
                user_data["event_time"] = strftime("%d-%h-%Y %I:%M:%S%p")
                user_data["img_processed"] = 0
                num_images = len(imgs)
                if num_images > 2:
                    user_data["diff_rect"] = self.server.get_motion_areas(imgs)

                with self.server.thread_lock:
                    self.server.mail_dict[user_data["id"]] = user_data

                for i in range(num_images):
                    self.server.img_queue.put((user_data["id"], i, num_images - 1))
            self.server.debug_print("dataworker done")


class ImgWorker(Thread):
    def __init__(self, server):
        super(ImgWorker, self).__init__()
        self.server = server

    def run(self):
        while True:
            mail_id, img_no, tot_images = self.server.img_queue.get()
            self.server.img_queue.task_done()
            action_required = False
            rom_user_data = None
            with self.server.thread_lock:
                # self.server.debug_print(self.server.mail_dict)
                rom_user_data = self.server.mail_dict[mail_id]
            self.server.debug_print(type(rom_user_data["imgs"][img_no]))
            if ("People" in rom_user_data["detections"]):
                """ret, rects, temp_img = self.server.detect_faces(rom_user_data["imgs"][img_no], rom_user_data["diff_rect"])
                if ret:
                    '''with self.server.thread_lock:
                        if "People" not in self.server.mail_dict[mail_id]["detected"]:
                            self.server.mail_dict[mail_id]["detected"]["People"] = []
                        self.server.mail_dict[mail_id]["detected"]["People"].append((img_no, rects))'''
                    self.server.write_image(temp_img)"""
                ret, rects, temp_img = self.server.dp.detect(rom_user_data["imgs"][img_no], rom_user_data["diff_rect"])
                if ret:
                    with self.server.thread_lock:
                        if "People" not in self.server.mail_dict[mail_id]["detected"]:
                            self.server.mail_dict[mail_id]["detected"]["People"] = []
                        self.server.mail_dict[mail_id]["detected"]["People"].append((img_no, rects))
                    self.server.write_image(temp_img)
                    action_required = True
                    self.server.debug_print("People detected")
            if action_required:
                with self.server.thread_lock:
                    self.server.mail_dict[mail_id]["action_required"] = True
            with self.server.thread_lock:
                if tot_images == self.server.mail_dict[mail_id]["img_processed"]:
                    self.server.mail_queue.put(rom_user_data["id"])
                self.server.mail_dict[mail_id]["img_processed"] += 1


class ActionWorker(Thread):
    def __init__(self, server):
        super(ActionWorker, self).__init__()
        self.server = server

    def run(self):
        while True:
            mail_id = self.server.mail_queue.get()
            self.server.mail_queue.task_done()
            rom_user_data = None
            with self.server.thread_lock:
                rom_user_data = self.server.mail_dict[mail_id]
            if rom_user_data["action_required"]:
                self.server.debug_print("Action Required")
                if ("Email" in rom_user_data["actions"] and rom_user_data["to_email"] != ""):
                    self.server.debug_print("Sending Email. ..")
                    self.server.send_email_alert(rom_user_data)
                    self.server.debug_print("Sent Email")
                if ("GDrive" in rom_user_data["actions"] and rom_user_data["gdrive"] != ""):
                    """
                    *Provide GDrive.add_to_upload_queue with the images.
                    *The GDrive class will write the images to .cctvmails/gdrive/unique_email/
                    *with image name in format "Channel 02@event time-no.jpg"
                    send a ping with image location.
                    receive the ping and add it to queue
                    thread workers use the queue to upload
                    """
                    self.server.GDrive.queue_image(rom_user_data)
            self.server.debug_print("Action worker done")
            self.server.email_no += 1
            processing_time = (datetime.now() -
                               datetime.strptime(rom_user_data["event_time"],
                                                 "%d-%b-%Y %I:%M:%S%p")).seconds
            with self.server.thread_lock:
                del self.server.mail_dict[mail_id]
            print "Processed email no %s in %s seconds" % (str(self.server.email_no), str(processing_time))

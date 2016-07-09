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
                imgs = self.server.decode_images(user_data, data)
                user_data["diff_rect"] = None
                if len(imgs) > 0:
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
            ret = self.server.detect_faces(img, user_data["diff_rect"])
            if ret:
                self.server.write_image(img)
            ret = self.server.dp.detect(img, user_data["diff_rect"])
            if ret:
                self.server.write_image(img)
            self.server.img_queue.task_done()

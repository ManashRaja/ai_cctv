from threading import Thread


class DataWorker(Thread):
    def __init__(self, server):
        super(DataWorker, self).__init__()
        self.server = server

    def run(self):
        while True:
            data = self.server.data_queue.get()
            imgs = self.server.decode_imges(data)
            for i in range(3):
                self.server.img_queue.put(imgs[i])
            self.server.data_queue.task_done()


class ImgWorker(Thread):
    def __init__(self, server):
        super(ImgWorker, self).__init__()
        self.server = server

    def run(self):
        while True:
            img = self.server.img_queue.get()
            ret = self.server.detect_faces(img)
            if ret:
                self.server.write_image(img)
            ret = self.server.dp.detect(img)
            if ret:
                self.server.write_image(img)
            self.server.img_queue.task_done()

import os
import re
import cv2
import base64
import asyncore
import numpy as np
import ConfigParser
import multi_threading
from time import time
from PIL import Image
from io import BytesIO
from Queue import Queue
from smtpd import SMTPServer
from datetime import datetime
from detect_people import DetectPeople


class EmlServer(SMTPServer):
    def __init__(self, local_address, remote_address, config):
        SMTPServer.__init__(self, local_address, remote_address)
        self.no = 0
        self.raw = 0
        self.dp = DetectPeople()
        self.data_queue = Queue()
        self.img_queue = Queue()
        self.config = config

    def readb64(self, base64_string):
        im = Image.open(BytesIO(base64.b64decode(base64_string)))
        return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

    def decode_imges(self, data):
        data = data.replace('\n', '')
        camera_regex = self.config.get('Settings', 'Camera Regex')
        found = re.search(camera_regex, data)
        camera_name = "None"
        if found:
            camera_name = found.group(1)
            print camera_name
        image_strings = re.findall("base64([^#]+)--#BOUNDARY", data)
        imgs = []
        imgs.append(self.readb64(image_strings[0]))
        imgs.append(self.readb64(image_strings[1]))
        imgs.append(self.readb64(image_strings[2]))

        mask = None
        mask_path = "settings/masks/" + camera_name + ".jpg"
        print mask_path
        if os.path.isfile(mask_path):
            mask = cv2.imread(mask_path)

        for i in range(3):
            if mask is not None:
                imgs[i] = cv2.add(imgs[i], mask)
            filename = 'images/raw/%s-%d.jpg' % (datetime.now().strftime('%Y%m%d%H%M%S'), self.raw)
            cv2.imwrite(filename, imgs[i])
            self.raw += 1
        return imgs

    def detect_faces(self, img):
        bool_detected = False
        face_cascade = cv2.CascadeClassifier("ml_trained/haarcascade_frontalface_alt.xml")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30),
            flags=cv2.CASCADE_SCALE_IMAGE  # previously cv2.cv.CV_HAAR_SCALE_IMAGE
        )
        if len(faces) > 0:
            # Draw a rectangle around the faces
            for (x, y, w, h) in faces:
                cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)
            bool_detected = True
        return bool_detected

    def write_image(self, img):
        filename = 'images/%s-%d.jpg' % (datetime.now().strftime('%Y%m%d%H%M%S'), self.no)
        cv2.imwrite(filename, img)
        self.no += 1

    def process_message(self, peer, mailfrom, rcpttos, data):
        print ("Received Email with %s in data_queue and %s in img_queue" %
               (str(self.data_queue.qsize()), str(self.img_queue.qsize())))
        ts = time()
        self.data_queue.put(data)
        print('Took {}'.format(time() - ts))

def run():
    print "Running"
    config = ConfigParser.ConfigParser()
    config.read("settings/config.ini")
    server = EmlServer(('0.0.0.0', 587), None, config)
    for x in range(1):
        data_worker = multi_threading.DataWorker(server)
        # Setting daemon to True will let the main thread exit even though the
        # workers are blocking
        data_worker.daemon = True
        data_worker.start()
    for x in range(2):
        img_worker = multi_threading.ImgWorker(server)
        # Setting daemon to True will let the main thread exit even though the
        # workers are blocking
        img_worker.daemon = True
        img_worker.start()
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass


run()
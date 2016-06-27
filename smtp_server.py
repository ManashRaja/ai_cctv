from datetime import datetime
import asyncore
from smtpd import SMTPServer
import re
from PIL import Image
from io import BytesIO
import base64
import cv2
import numpy as np
from detect_people import DetectPeople


class EmlServer(SMTPServer):
    no = 0
    raw = 0
    dp = DetectPeople()

    def readb64(self, base64_string):
        im = Image.open(BytesIO(base64.b64decode(base64_string)))
        return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

    def decode_imges(self, data):
        data = data.replace('\n', '')
        images = re.findall("base64([^#]+)--#BOUNDARY", data)
        img1 = self.readb64(images[0])
        img2 = self.readb64(images[1])
        img3 = self.readb64(images[2])
        filename = 'images/raw/%s-%d.jpg' % (datetime.now().strftime('%Y%m%d%H%M%S'), self.raw)
        cv2.imwrite(filename, img1)
        self.raw += 1
        filename = 'images/raw/%s-%d.jpg' % (datetime.now().strftime('%Y%m%d%H%M%S'), self.raw)
        cv2.imwrite(filename, img2)
        self.raw += 1
        filename = 'images/raw/%s-%d.jpg' % (datetime.now().strftime('%Y%m%d%H%M%S'), self.raw)
        cv2.imwrite(filename, img3)
        self.raw += 1
        return (img1, img2, img3)

    def detect_faces(self, imgs):
        image_no = []
        max_detections = 0
        faceCascade = cv2.CascadeClassifier("ml_trained/haarcascade_frontalface_alt.xml")
        for i in range(0, 2):
            gray = cv2.cvtColor(imgs[i], cv2.COLOR_BGR2GRAY)
            faces = faceCascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
                flags=cv2.cv.CV_HAAR_SCALE_IMAGE
            )
            if len(faces) > max_detections:
                max_detections = len(faces)
                image_no.append(i)
            # Draw a rectangle around the faces
            for (x, y, w, h) in faces:
                cv2.rectangle(imgs[i], (x, y), (x + w, y + h), (0, 255, 0), 2)
        return image_no

    def write_image(self, image_no, imgs):
        if len(image_no) > 0:
            for i in image_no:
                filename = 'images/%s-%d.jpg' % (datetime.now().strftime('%Y%m%d%H%M%S'), self.no)
                cv2.imwrite(filename, imgs[i])
                self.no += 1


    def process_message(self, peer, mailfrom, rcpttos, data):
        print "Received Email"
        # Decode images
        imgs = []
        (img1, img2, img3) = self.decode_imges(data)
        imgs.append(img1)
        imgs.append(img2)
        imgs.append(img3)

        # Detect faces in images
        image_no = self.detect_faces(imgs)
        self.write_image(image_no, imgs)

        # Detect People
        image_no = self.dp.detect(imgs)
        self.write_image(image_no, imgs)


def run():
    print "Running"
    server = EmlServer(('192.168.0.100', 587), None)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass


run()
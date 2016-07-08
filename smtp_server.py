import os
import re
import cv2
import json
import base64
import MySQLdb
import asyncore
import numpy as np
import multi_threading
from time import time
from PIL import Image
from io import BytesIO
from Queue import Queue
from smtpd import SMTPServer
from datetime import datetime
from detect_people import DetectPeople


class EmlServer(SMTPServer):
    def __init__(self, local_address, remote_address):
        SMTPServer.__init__(self, local_address, remote_address)
        self.no = 0
        self.raw = 0
        self.dp = DetectPeople()
        self.data_queue = Queue()
        self.img_queue = Queue()
        self.debug = True

    def get_camera(self, data, user_data):
        data = data.replace('\n', '')
        camera_regex = user_data["configs"]["Camera Regex"]
        found = re.search(camera_regex, data)
        camera_name = ""
        if found:
            camera_name = found.group(1)
        return camera_name

    def debug_print(self, minput):
        if self.debug:
            print minput

    def get_user_info(self, mailfrom):
        ret = False
        user_data = {}
        try:
            conn = MySQLdb.connect(host="manashpratim.in", user='manashpr_python', passwd='sqldb@Security', db='manashpr_cctvmails', port=3306)
            cur = conn.cursor()
            exec_string = "SELECT * FROM settings WHERE `uniqueemail` = '%s'" % mailfrom
            count = cur.execute(exec_string)
            if (count > 0):
                ret = True
                data = cur.fetchall()
                # print the rows
                for row in data:
                    user_data["reg_email"] = row[1]
                    user_data["unique_email"] = row[2]
                    user_data["username"] = row[3]
                    user_data["pss"] = row[4]
                    user_data["configs"] = json.loads(row[5])
                    user_data["rules"] = json.loads(row[6])
                    user_data["configured"] = row[7]
                    # user_data["to_email"] = row[8]
                    # user_data["gdrive"] = row[9]
                    # user_data["dropbox"] = row[10]
            cur.close()
            conn.close()
        except MySQLdb.Error, e:
            print "Mysql Error %d: %s" % (e.args[0], e.args[1])
        return (ret, user_data)

    def within_time_period(self, user_data):
        for i in range(len(user_data["rules"])):
            if user_data["rules"][str(i)]["camera"] == user_data["camera"]:
                time_periods = user_data["rules"][str(i)]["time_periods"].split(',')
                for time_period in time_periods:
                    time_pairs = time_period.split('-')
                    datetime_start = datetime.strptime(time_pairs[0], '%I:%M%p')
                    datetime_end = datetime.strptime(time_pairs[1], '%I:%M%p')
                    datetime_current = datetime.strptime(datetime.now().strftime('%I:%M%p'), '%I:%M%p')
                    self.debug_print(datetime_start)
                    self.debug_print(datetime_end)
                    self.debug_print(datetime_current)
                    if (datetime_start < datetime_end and (datetime_start < datetime_current and datetime_current < datetime_end)):
                        user_data["actions"] = user_data["rules"][str(i)]["action"]
                        user_data["detections"] = user_data["rules"][str(i)]["detection"]
                        self.debug_print("time_yes_up")
                        return True
                    elif (datetime_start > datetime_end and (datetime_start < datetime_current or datetime_current < datetime_end)):
                        user_data["actions"] = user_data["rules"][str(i)]["action"]
                        user_data["detections"] = user_data["rules"][str(i)]["detection"]
                        self.debug_print("time_yes_down")
                        return True
                    else:
                        self.debug_print("tried")
        self.debug_print("time_no")
        return False

    def readb64(self, base64_string):
        im = Image.open(BytesIO(base64.b64decode(base64_string)))
        return cv2.cvtColor(np.array(im), cv2.COLOR_RGB2BGR)

    def decode_images(self, user_data, data):
        data = data.replace('\n', '')
        camera_name = user_data["camera"]
        image_strings = re.findall(user_data["configs"]["Image Regex"], data)  # "base64([^#]+)--#BOUNDARY"
        imgs = []
        number_of_images = len(image_strings)
        for i in range(number_of_images):
            imgs.append(self.readb64(image_strings[i]))

        mask = None
        mask_path = "settings/masks/%s/%s.jpg" % (user_data["unique_email"], camera_name)
        print mask_path
        if os.path.isfile(mask_path):
            mask = cv2.imread(mask_path)

        for i in range(number_of_images):
            if mask is not None:
                imgs[i] = cv2.add(imgs[i], mask)
            directory = 'images/raw/%s/' % user_data["unique_email"]
            # TODO: create directory is non existent
            filename = '%s/%s-%d.jpg' % (directory, datetime.now().strftime('%Y%m%d%H%M%S'), self.raw)
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
        self.data_queue.put((mailfrom, data))
        self.debug_print("Mailfrom: " + mailfrom)
        print('Took {}'.format(time() - ts))


def run():
    print "Running"
    server = EmlServer(('0.0.0.0', 587), None)
    for x in range(2):
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
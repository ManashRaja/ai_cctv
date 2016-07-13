import os
import re
import cv2
import json
import base64
import MySQLdb
import asyncore
import traceback
import numpy as np
import ConfigParser
import multi_threading
from time import time
from PIL import Image
from io import BytesIO
from Queue import Queue
from gdrive import GDrive
from threading import Lock
from smtpd import SMTPServer
from datetime import datetime
from email.utils import formatdate
from email.mime.text import MIMEText
from detect_people import DetectPeople
from email.mime.multipart import MIMEMultipart
import smtplib, email, email.encoders, email.mime.text, email.mime.base


class EmlServer(SMTPServer):
    def __init__(self, local_address, remote_address, config):
        SMTPServer.__init__(self, local_address, remote_address)
        self.no = 0
        self.raw = 0
        self.email_no = 0
        self.dp = DetectPeople()
        self.GDrive = GDrive()
        self.mail_dict = {}
        self.data_queue = Queue()
        self.img_queue = Queue()
        self.mail_queue = Queue()
        self.debug = False
        self.config = config
        self.motion_thresh = 15
        self.thread_lock = Lock()
        self.write_raw = False

    def send_email_alert(self, user_data):
        try:
            msg = MIMEMultipart()
            send_from = self.config.get('Email', 'from_email')
            send_to = user_data["to_email"]
            msg['From'] = send_from
            msg['To'] = send_to
            msg['Date'] = formatdate(localtime=True)
            msg['Subject'] = self.config.get('Email', 'subject')
            text = """Hello %s,

                      An event was detected on your cctv system. The details of the
                      event are mentioned below.

                      EVENT TYPE: %s,
                      EVENT TIME: %s,
                      CAMERA NAME: %s,
                      RULE NUMBER: %s

                      The images of the event are attached.

                      This is an autogenerated email. Please do not reply to it.

                      Thanking you,
                      cctvmails.com
                   """ % (user_data["username"],
                          ', '.join(map(str, list(user_data["detected"]))),
                          user_data["event_time"],
                          user_data["camera"],
                          user_data["rule_applied"])

            msg.attach(MIMEText(text))

            i = 1
            for img in user_data["imgs"]:
                image_name = "%s-%s.jpg" % (user_data["event_time"], str(++i))
                filemsg = email.mime.base.MIMEBase('application', image_name)
                filemsg.set_payload(cv2.imencode('.jpg', img)[1].tostring())
                # filemsg.set_payload(base64.b64decode(image_string))
                email.encoders.encode_base64(filemsg)
                filemsg.add_header('Content-Disposition', 'attachment;filename=' + image_name)
                msg.attach(filemsg)

            username = self.config.get('Email', 'username')
            pss = self.config.get('Email', 'pss')
            smtp = smtplib.SMTP_SSL(self.config.get('Email', 'smtp_server'),
                                    int(self.config.get('Email', 'smtp_port')))
            smtp.ehlo()
            smtp.login(username, pss)
            smtp.sendmail(send_from, send_to, msg.as_string())
            smtp.close()
            print "Email Sent"
        except Exception as e:
            print "Email Send Error: " + str(traceback.format_exc())

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

    def crop_area(self, image, threshold=0):
        ret_rect = (0, 0, 0, 0)
        if len(image.shape) == 3:
            flatImage = np.max(image, 2)
        else:
            flatImage = image
        assert len(flatImage.shape) == 2

        rows = np.where(np.max(flatImage, 0) > threshold)[0]
        if rows.size:
            cols = np.where(np.max(flatImage, 1) > threshold)[0]
            # image = image[cols[0]: cols[-1] + 1, rows[0]: rows[-1] + 1]
            percentage = 0.1
            xa = rows[0] - int(image.shape[0] * percentage)
            ya = cols[0] - int(image.shape[1] * percentage)
            xb = rows[-1] + 1 + int(image.shape[0] * percentage)
            yb = cols[-1] + 1 + int(image.shape[1] * percentage)
            ret_rect = (xa, ya, xb, yb)
        return ret_rect

    def img_gray(self, image):
        new_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        return new_image

    def get_motion_areas(self, imgs):
        img_diff = cv2.absdiff(self.img_gray(imgs[0]), self.img_gray(imgs[1]))
        for i in range(2, len(imgs)):
            img_diff2 = cv2.absdiff(self.img_gray(imgs[0]), self.img_gray(imgs[i]))
            img_diff = cv2.add(img_diff, img_diff2)
        # img_diff = cv2.cvtColor(img_diff, cv2.COLOR_BGR2GRAY)
        img_diff = cv2.erode(img_diff, np.ones((9, 9)))
        # (thresh, img_diff) = cv2.threshold(img_diff, 128, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        img_diff = cv2.threshold(img_diff, self.motion_thresh, 255, cv2.THRESH_BINARY)[1]
        diff_rect = self.crop_area(img_diff)
        return diff_rect

    def get_user_info(self, mailfrom):
        ret = False
        user_data = {}
        try:
            conn = MySQLdb.connect(host=self.config.get('SQLdb', 'host'),
                                   user=self.config.get('SQLdb', 'user'),
                                   passwd=self.config.get('SQLdb', 'passwd'),
                                   db=self.config.get('SQLdb', 'db'),
                                   port=int(self.config.get('SQLdb', 'port')))
            cur = conn.cursor()
            exec_string = "SELECT * FROM %s WHERE `%s` = '%s'" % (self.config.get('SQLdb', 'table'),
                                                                  self.config.get('SQLdb', 'auth_field'),
                                                                  mailfrom)
            count = cur.execute(exec_string)
            if (count > 0):
                ret = True
                data = cur.fetchall()
                # print the rows
                for row in data:
                    user_data["username"] = row[1]
                    user_data["pss"] = row[2]
                    user_data["reg_email"] = row[3]
                    user_data["unique_email"] = row[4]
                    user_data["configs"] = json.loads(row[5])
                    user_data["rules"] = json.loads(row[6])
                    user_data["configured"] = row[7]
                    user_data["to_email"] = row[8]
                    user_data["gdrive"] = row[9]
                    user_data["dropbox"] = row[10]
                    user_data["gdrive_parent"] = row[11]
            cur.close()
            conn.close()
        except MySQLdb.Error, e:
            print "Mysql Error %d: %s" % (e.args[0], e.args[1])
        return (ret, user_data)

    def within_time_period(self, user_data):
        for i in range(len(user_data["rules"])):
            if user_data["rules"][str(i)]["camera"] == user_data["configs"]["Camera Identifier"][user_data["camera"]]:
                user_data["rule_applied"] = str(i + 1)
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
        image_strings = re.findall(user_data["configs"]["Image Regex"], data)
        imgs = []
        number_of_images = len(image_strings)
        for i in range(number_of_images):
            imgs.append(self.readb64(image_strings[i]))

        mask = None
        # mask_path = "settings/masks/%s/%s.jpg" % (user_data["unique_email"], camera_name)
        # print mask_path
        # if os.path.isfile(mask_path):
        #     mask = cv2.imread(mask_path)
        if self.write_raw:
            for i in range(number_of_images):
                if mask is not None:
                    imgs[i] = cv2.add(imgs[i], mask)
                directory = 'images/raw'
                # TODO: create directory is non existent
                filename = '%s/%s-%d.jpg' % (directory, datetime.now().strftime('%Y%m%d%H%M%S'), self.raw)
                cv2.imwrite(filename, imgs[i])
                self.raw += 1
        return imgs

    def rect_intersect(self, a, b):
        x = max(a[0], b[0])
        y = max(a[1], b[1])
        w = min(a[0] + a[2], b[0] + b[2]) - x
        h = min(a[1] + a[3], b[1] + b[3]) - y
        if w < 0 or h < 0:
            return False
        return True

    def detect_faces(self, img, diff_rect):
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
        rects = []
        temp_img = img
        if len(faces) > 0:
            # Draw a rectangle around the faces
            for (x, y, w, h) in faces:
                cv2.rectangle(temp_img, (x, y), (x + w, y + h), (0, 255, 0), 2)
                if self.rect_intersect((x, y, x + w, y + h), diff_rect):
                    rects.append((x, y, x + w, y + h))
                    cv2.rectangle(temp_img, (x, y), (x + w, y + h), (255, 255, 255), 2)
                    bool_detected = True
        return (bool_detected, rects, temp_img)

    def write_image(self, img, img_dir="", filename=""):
        if filename == "":
            filename = 'images/%s-%d.jpg' % (datetime.now().strftime('%Y%m%d%H%M%S'), self.no)
        if img_dir != "" and not os.path.exists(img_dir):
            os.makedirs(img_dir)
        file_path = os.path.join(img_dir, filename)
        cv2.imwrite(file_path, img)
        self.no += 1

    def process_message(self, peer, mailfrom, rcpttos, data):
        print ("Received Email with %s in data_queue, %s in img_queue and %s in mail_queue." %
               (str(self.data_queue.qsize()), str(self.img_queue.qsize()), str(self.mail_queue.qsize())))
        # ts = time()
        self.data_queue.put((mailfrom, data))
        self.debug_print("Mailfrom: " + mailfrom)
        # print('Took {}'.format(time() - ts))


def run():
    print "Running"
    config = ConfigParser.ConfigParser()
    config.read("settings/config.ini")
    server = EmlServer(('0.0.0.0', 587), None, config)
    for x in range(2):
        data_worker = multi_threading.DataWorker(server)
        # Setting daemon to True will let the main thread exit even though the
        # workers are blocking
        data_worker.daemon = True
        data_worker.start()
    for x in range(6):
        img_worker = multi_threading.ImgWorker(server)
        # Setting daemon to True will let the main thread exit even though the
        # workers are blocking
        img_worker.daemon = True
        img_worker.start()
    for x in range(2):
        action_worker = multi_threading.ActionWorker(server)
        # Setting daemon to True will let the main thread exit even though the
        # workers are blocking
        action_worker.daemon = True
        action_worker.start()
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass


run()

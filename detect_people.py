from __future__ import print_function
from imutils.object_detection import non_max_suppression
import numpy as np
import imutils
import cv2


class DetectPeople(object):
    def __init__(self):
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def rect_intersect(self, a, b):
        x = max(a[0], b[0])
        y = max(a[1], b[1])
        w = min(a[0] + a[2], b[0] + b[2]) - x
        h = min(a[1] + a[3], b[1] + b[3]) - y
        if w < 0 or h < 0:
            return False
        return True

    def detect(self, img, diff_rect):
        """ initialize the HOG descriptor/person detector
        # load the image and resize it to (1) reduce detection time
        # and (2) improve detection accuracy """
        bool_detected = False
        image = img.copy()
        image = image[25:image.shape[2] - 25, 0:image.shape[1]]
        image = imutils.resize(image, width=max(400, image.shape[1]))
        # orig = image.copy()

        # detect people in the image
        (rects, weights) = self._hog.detectMultiScale(image, winStride=(2, 2),
                                                      padding=(8, 8), scale=1.05)

        # draw the original bounding boxes
        # for (x, y, w, h) in rects:
        #     cv2.rectangle(orig, (x, y), (x + w, y + h), (0, 0, 255), 2)

        # apply non-maxima suppression to the bounding boxes using a
        # fairly large overlap threshold to try to maintain overlapping
        # boxes that are still people
        rects = np.array([[x, y, x + w, y + h] for (x, y, w, h) in rects])
        pick = non_max_suppression(rects, probs=None, overlapThresh=0.65)

        # draw the final bounding boxes
        temp_img = img.copy()
        rects = []
        if len(pick) > 0:
            for (xA, yA, xB, yB) in pick:
                cv2.rectangle(temp_img, (xA, yA + 25), (xB, yB + 25), (255, 0, 0), 2)
                if self.rect_intersect((xA, yA + 25, xB, yB + 25), diff_rect):
                    rects.append((xA, yA, xB + 25, yB + 25))
                    cv2.rectangle(temp_img, (xA, yA + 25), (xB, yB + 25), (0, 0, 0), 2)
                    bool_detected = True
        return (bool_detected, rects, temp_img)

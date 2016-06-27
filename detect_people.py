from __future__ import print_function
from imutils.object_detection import non_max_suppression
import numpy as np
import imutils
import cv2


class DetectPeople(object):
    def __init__(self):
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())


    def detect(self, img):
        """ initialize the HOG descriptor/person detector
        # load the image and resize it to (1) reduce detection time
        # and (2) improve detection accuracy """
        bool_detected = False
        image = img
        image = image[25:image.shape[2] - 25, 0:image.shape[1]]
        image = imutils.resize(image, width=min(400, image.shape[1]))
        # orig = image.copy()

        # detect people in the image
        (rects, weights) = self._hog.detectMultiScale(image, winStride=(4, 4),
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
        if len(pick) > 0:
            for (xA, yA, xB, yB) in pick:
                cv2.rectangle(img, (xA, yA + 25), (xB, yB + 25), (255, 0, 0), 2)
            bool_detected = True
        return bool_detected
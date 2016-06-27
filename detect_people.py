# import the necessary packages
from __future__ import print_function
from imutils.object_detection import non_max_suppression
import numpy as np
import imutils
import cv2


class DetectPeople(object):
    _hog = None

    def __init__(self):
        pass

    def detect(self, imgs):
        """ initialize the HOG descriptor/person detector
        # load the image and resize it to (1) reduce detection time
        # and (2) improve detection accuracy """

        _image_num = []
        _max_detections = 0
        for i in range(0, 2):
            image = imgs[i]
            image = image[25:image.shape[2] - 25, 0:image.shape[1]]
            image = imutils.resize(image, width=min(400, image.shape[1]))
            # orig = image.copy()

            # detect people in the image
            _hog = cv2.HOGDescriptor()
            _hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
            (rects, weights) = _hog.detectMultiScale(image, winStride=(4, 4),
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
            if len(pick) > _max_detections:
                _max_detections = len(pick)
                _image_num.append(i)
                for (xA, yA, xB, yB) in pick:
                    cv2.rectangle(imgs[i], (xA, yA), (xB, yB), (255, 0, 0), 2)

            # show the output images
            # cv2.imshow("Before NMS", orig)
            # cv2.imshow("After NMS", image)
            # cv2.waitKey(0)
            return _image_num
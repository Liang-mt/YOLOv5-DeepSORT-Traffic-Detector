from tracker import DeepSortTracker
import cv2


class baseDet(object):

    def __init__(self):

        self.img_size = 640
        self.threshold = 0.3
        self.stride = 1
        self.tracker = DeepSortTracker()

    def build_config(self):

        self.faceTracker = {}
        self.faceClasses = {}
        self.faceLocation1 = {}
        self.faceLocation2 = {}
        self.frameCounter = 0
        self.currentCarID = 0
        self.recorded = []

        self.font = cv2.FONT_HERSHEY_SIMPLEX

    def feedCap(self, im, count):

        retDict = {}
        self.frameCounter += 1

        total, im = self.tracker.update(self, im, count)

        retDict['frame'] = im
        retDict['car_num'] = int(total)

        return retDict

    def init_model(self):
        raise EOFError("Undefined model type.")

    def preprocess(self):
        raise EOFError("Undefined model type.")

    def detect(self):
        raise EOFError("Undefined model type.")

from .feedback_test import Feedbacks
from .base_test import BaseTest
from ingeniamotion.enums import SensorType


class DigitalIncremental2(Feedbacks):
    def __init__(self, mc, servo, axis):
        super().__init__()
        self.sensor = SensorType.QEI2
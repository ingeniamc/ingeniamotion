from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks
from ingeniamotion.enums import SensorType


class DigitalIncremental1(Feedbacks):
    BACKUP_REGISTERS_QEI = ["FBK_DIGENC1_POLARITY"]

    FEEDBACK_POLARITY_REGISTER = "FBK_DIGENC1_POLARITY"

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.QEI

    def __init__(self, mc, servo, axis):
        super().__init__(mc, servo, axis)
        self.backup_registers_names += self.BACKUP_REGISTERS_QEI

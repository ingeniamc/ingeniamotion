from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks
from ingeniamotion.enums import SensorType


class DigitalIncremental2Test(Feedbacks):
    BACKUP_REGISTERS_QEI2 = ["FBK_DIGENC2_POLARITY"]

    FEEDBACK_POLARITY_REGISTER = "FBK_DIGENC2_POLARITY"

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.QEI2

    def __init__(self, mc, servo, axis):
        super().__init__(mc, servo, axis)
        self.backup_registers_names += self.BACKUP_REGISTERS_QEI2

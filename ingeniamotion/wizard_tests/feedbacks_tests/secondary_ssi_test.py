from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks
from ingeniamotion.enums import SensorType


class SecondarySSITest(Feedbacks):
    BACKUP_REGISTERS_SSI2 = []

    FEEDBACK_POLARITY_REGISTER = "FBK_SSI2_POS_POLARITY"

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.SSI2

    def __init__(self, mc, servo, axis):
        super().__init__(mc, servo, axis)
        self.backup_registers_names += self.BACKUP_REGISTERS_SSI2


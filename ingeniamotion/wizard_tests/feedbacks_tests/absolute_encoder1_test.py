from ingeniamotion import MotionController
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks
from ingeniamotion.enums import SensorType


class AbsoluteEncoder1Test(Feedbacks):
    BACKUP_REGISTERS_ABS1 = ["FBK_BISS1_SSI1_POS_POLARITY"]

    FEEDBACK_POLARITY_REGISTER = "FBK_BISS1_SSI1_POS_POLARITY"

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.ABS1

    def __init__(self, mc: MotionController, servo: str, axis: int) -> None:
        super().__init__(mc, servo, axis)
        self.backup_registers_names.append(*self.BACKUP_REGISTERS_ABS1)

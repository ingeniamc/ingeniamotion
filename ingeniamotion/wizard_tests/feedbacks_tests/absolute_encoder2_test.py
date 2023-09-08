from ingeniamotion import MotionController
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks
from ingeniamotion.wizard_tests.base_test import BaseTest
from ingeniamotion.enums import SensorType


class AbsoluteEncoder2Test(Feedbacks):
    BACKUP_REGISTERS_BISSC2 = ["FBK_BISS2_POS_POLARITY"]

    FEEDBACK_POLARITY_REGISTER = "FBK_BISS2_POS_POLARITY"

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.BISSC2

    def __init__(self, mc: MotionController, servo:str, axis:int):
        super().__init__(mc, servo, axis)
        self.backup_registers_names.append(*self.BACKUP_REGISTERS_BISSC2)

    @BaseTest.stoppable
    def feedback_setting(self) -> None:
        super().feedback_setting()
        self.mc.configuration.set_auxiliar_feedback(
            SensorType.ABS1, servo=self.servo, axis=self.axis
        )

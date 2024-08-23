from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from ingeniamotion.wizard_tests.base_test import BaseTest
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks


class AbsoluteEncoder2Test(Feedbacks):
    BACKUP_REGISTERS_BISSC2: List[str] = ["FBK_BISS2_POS_POLARITY"]

    FEEDBACK_POLARITY_REGISTER = "FBK_BISS2_POS_POLARITY"

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.BISSC2

    def __init__(
        self, mc: "MotionController", servo: str, axis: int, logger_drive_name: Optional[str] = None
    ) -> None:
        super().__init__(mc, servo, axis, logger_drive_name)
        self.backup_registers_names.extend(self.BACKUP_REGISTERS_BISSC2)

    @BaseTest.stoppable
    def feedback_setting(self) -> None:
        super().feedback_setting()
        self.mc.configuration.set_auxiliar_feedback(
            SensorType.ABS1, servo=self.servo, axis=self.axis
        )

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks


class DigitalIncremental2Test(Feedbacks):
    BACKUP_REGISTERS_QEI2: list[str] = ["FBK_DIGENC2_POLARITY"]

    FEEDBACK_POLARITY_REGISTER = "FBK_DIGENC2_POLARITY"

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.QEI2

    def __init__(
        self, mc: "MotionController", servo: str, axis: int, logger_drive_name: Optional[str] = None
    ) -> None:
        super().__init__(mc, servo, axis, logger_drive_name)
        self.backup_registers_names.extend(self.BACKUP_REGISTERS_QEI2)

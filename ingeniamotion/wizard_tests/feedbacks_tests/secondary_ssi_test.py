from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks


class SecondarySSITest(Feedbacks):
    BACKUP_REGISTERS_SSI2: List[str] = []

    FEEDBACK_POLARITY_REGISTER = "FBK_SSI2_POS_POLARITY"

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.SSI2

    def __init__(
        self, mc: "MotionController", servo: str, axis: int, logger_drive_name: Optional[str] = None
    ) -> None:
        super().__init__(mc, servo, axis, logger_drive_name)
        self.backup_registers_names.extend(self.BACKUP_REGISTERS_SSI2)

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import Feedbacks


class DigitalIncremental1Test(Feedbacks):
    BACKUP_REGISTERS_QEI: List[str] = ["FBK_DIGENC1_POLARITY"]

    FEEDBACK_POLARITY_REGISTER = "FBK_DIGENC1_POLARITY"

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.QEI

    def __init__(self, mc: "MotionController", servo: str, axis: int) -> None:
        super().__init__(mc, servo, axis)
        self.backup_registers_names.extend(self.BACKUP_REGISTERS_QEI)

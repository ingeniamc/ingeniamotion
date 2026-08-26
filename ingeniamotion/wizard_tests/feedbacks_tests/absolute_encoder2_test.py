from typing import TYPE_CHECKING, Optional

from typing_extensions import override

if TYPE_CHECKING:
    from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from ingeniamotion.wizard_tests.base_test import BaseTest
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import FeedbacksTest


class AbsoluteEncoder2Test(FeedbacksTest):
    """Absolute encoder 2 test class."""

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.BISSC2

    def __init__(
        self, mc: "MotionController", servo: str, axis: int, logger_drive_name: Optional[str] = None
    ) -> None:
        super().__init__(mc, servo, axis, logger_drive_name)

    @override
    @BaseTest.stoppable
    def feedback_setting(self) -> None:
        super().feedback_setting()
        self._axis_feedbacks.auxiliary.set_encoder_type(SensorType.ABS1)

from typing import TYPE_CHECKING, Optional

from typing_extensions import override

if TYPE_CHECKING:
    from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from ingeniamotion.wizard_tests.base_test import BaseTest, TestConfigurationError
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import FeedbacksTest

SECONDARY_CHANNEL_PROTOCOL_REGISTER = "FBK_SSI2_PROTOCOL"
SSI_PROTOCOL_VALUE = 1


class SecondarySSITest(FeedbacksTest):
    """Secondary SSI test class."""

    SENSOR_TYPE_FEEDBACK_TEST = SensorType.SSI2

    def __init__(
        self, mc: "MotionController", servo: str, axis: int, logger_drive_name: Optional[str] = None
    ) -> None:
        super().__init__(mc, servo, axis, logger_drive_name)

    @override
    @BaseTest.stoppable
    def feedback_setting(self) -> None:
        protocol = self.mc.communication.get_register(
            SECONDARY_CHANNEL_PROTOCOL_REGISTER, servo=self.servo, axis=self.axis
        )
        if protocol != SSI_PROTOCOL_VALUE:
            raise TestConfigurationError(
                f"The secondary feedback channel is not configured for SSI: "
                f"{SECONDARY_CHANNEL_PROTOCOL_REGISTER} is {protocol}, expected "
                f"{SSI_PROTOCOL_VALUE}."
            )
        super().feedback_setting()

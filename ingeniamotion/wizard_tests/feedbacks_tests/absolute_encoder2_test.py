from typing import TYPE_CHECKING, Optional

from typing_extensions import override

if TYPE_CHECKING:
    from ingeniamotion import MotionController
from ingeniamotion.enums import SensorType
from ingeniamotion.wizard_tests.base_test import BaseTest, TestConfigurationError
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import FeedbacksTest

PRIMARY_CHAIN_PROTOCOL_REGISTER = "FBK_BISS1_SSI1_PROTOCOL"
PRIMARY_CHAIN_LENGTH_REGISTER = "FBK_BISS_CHAIN"
BISSC_PROTOCOL_VALUE = 0
BISSC2_CHAIN_LENGTH = 2


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
        protocol = self.mc.communication.get_register(
            PRIMARY_CHAIN_PROTOCOL_REGISTER, servo=self.servo, axis=self.axis
        )
        chain_length = self.mc.communication.get_register(
            PRIMARY_CHAIN_LENGTH_REGISTER, servo=self.servo, axis=self.axis
        )
        if protocol != BISSC_PROTOCOL_VALUE or chain_length != BISSC2_CHAIN_LENGTH:
            raise TestConfigurationError(
                "The primary feedback chain is not configured for BiSS-C slave 2: "
                f"{PRIMARY_CHAIN_PROTOCOL_REGISTER} is {protocol}, expected "
                f"{BISSC_PROTOCOL_VALUE}; {PRIMARY_CHAIN_LENGTH_REGISTER} is "
                f"{chain_length}, expected {BISSC2_CHAIN_LENGTH}."
            )
        super().feedback_setting()
        self._axis_feedbacks.auxiliary.set_encoder_type(SensorType.ABS1)

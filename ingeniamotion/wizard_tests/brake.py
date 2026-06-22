from typing import TYPE_CHECKING, Optional

import ingenialogger
from typing_extensions import override

from ingeniamotion.enums import CommutationMode, OperationMode, SensorType, SeverityLevel
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.wizard_tests.base_test import BaseTest, ReportBase

if TYPE_CHECKING:
    from ingeniamotion import MotionController


class ResultsBrakeTest(ReportBase):
    """Brake test result report."""


class Brake(BaseTest[ResultsBrakeTest]):
    """Brake test class."""

    BRAKE_OVERRIDE_REGISTER = "MOT_BRAKE_OVERRIDE"

    PRIMARY_ABSOLUTE_SLAVE_1_PROTOCOL = "FBK_BISS1_SSI1_PROTOCOL"
    PRIMARY_ABSOLUTE_SLAVE_1_FRAME_TYPE = "FBK_BISS1_SSI1_FRAME_TYPE"

    def __init__(
        self,
        mc: "MotionController",
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        logger_drive_name: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        if logger_drive_name is None:
            self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))
        else:
            self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=logger_drive_name)

    @override
    def setup(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.mc.configuration.disable_brake_override(servo=self.servo, axis=self.axis)
        self.mc.configuration.set_commutation_mode(
            CommutationMode.SINUSOIDAL, servo=self.servo, axis=self.axis
        )
        self.mc.motion.set_internal_generator_configuration(
            OperationMode.VOLTAGE, servo=self.servo, axis=self.axis
        )
        self.mc.configuration.set_reference_feedback(
            SensorType.INTGEN, servo=self.servo, axis=self.axis
        )
        self.mc.configuration.set_velocity_feedback(
            SensorType.INTGEN, servo=self.servo, axis=self.axis
        )
        self.mc.configuration.set_position_feedback(
            SensorType.INTGEN, servo=self.servo, axis=self.axis
        )
        # Set the auxiliar feedback to ABS1 because the internal generator is not allowed
        # as auxiliar feedback for all drives
        self.mc.configuration.set_auxiliar_feedback(
            SensorType.ABS1, servo=self.servo, axis=self.axis
        )
        # Set the absolute encoder protocol to SSI and the frame type to RAW to avoid errors.
        self.mc.communication.set_register(
            self.PRIMARY_ABSOLUTE_SLAVE_1_PROTOCOL, 1, servo=self.servo, axis=self.axis
        )
        self.mc.communication.set_register(
            self.PRIMARY_ABSOLUTE_SLAVE_1_FRAME_TYPE, 0, servo=self.servo, axis=self.axis
        )

    @override
    def loop(self) -> None:
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)

    @override
    def teardown(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)

    @override
    def get_result_severity(self, output: SeverityLevel) -> SeverityLevel:
        return output

    @override
    def get_result_msg(self, output: SeverityLevel) -> str:
        if output == SeverityLevel.SUCCESS:
            return "Success"
        else:
            return "Fail"

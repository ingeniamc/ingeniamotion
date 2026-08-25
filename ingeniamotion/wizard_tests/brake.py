from types import TracebackType
from typing import TYPE_CHECKING, Optional

import ingenialogger
from typing_extensions import override

from ingeniamotion.enums import CommutationMode, OperationMode, SensorType, SeverityLevel
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.wizard_tests.base_test import BaseTest, ReportBase

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

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
        self.__context: Optional[AbstractContextManager[None]] = None
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
        # Set the auxiliary feedback to ABS1 because the internal generator is not allowed
        # as auxiliary feedback for all drives
        axis_feedbacks = self._axis_feedbacks
        internal_generator = axis_feedbacks.get_sensor(SensorType.INTGEN)
        axis_feedbacks.update_configuration({
            axis_feedbacks.reference: internal_generator,
            axis_feedbacks.velocity: internal_generator,
            axis_feedbacks.position: internal_generator,
            axis_feedbacks.auxiliary: axis_feedbacks.get_sensor(SensorType.ABS1),
        })
        # Set the absolute encoder protocol to SSI and the frame type to RAW to avoid errors.
        self.mc.communication.set_register(
            self.PRIMARY_ABSOLUTE_SLAVE_1_PROTOCOL, 1, servo=self.servo, axis=self.axis
        )
        self.mc.communication.set_register(
            self.PRIMARY_ABSOLUTE_SLAVE_1_FRAME_TYPE, 0, servo=self.servo, axis=self.axis
        )

    @override
    def loop(self) -> SeverityLevel:
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
        return SeverityLevel.SUCCESS

    @override
    def teardown(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)

    def start(self) -> "Brake":
        """Configure the drive and return this brake test.

        Idempotent: the drive is configured on the first call. A later call
        (e.g. the implicit one made by a ``with`` statement after
        ``DriveTests.brake_test`` already configured the drive) is a no-op.

        Returns:
            This brake test.
        """
        if self.__context is None:
            context = self.run_context()
            context.__enter__()
            self.__context = context
        return self

    def finish(self) -> Optional[ResultsBrakeTest]:
        """Disable the motor and restore the drive state changed during the test.

        Equivalent to exiting the context manager. Idempotent: a second call
        (e.g. after the test already cleaned up) is a no-op.

        Returns:
            The test report.
        """
        self.__exit__(None, None, None)
        return self.report

    def __enter__(self) -> "Brake":
        """Configure the drive and return this brake test.

        Returns:
            This brake test.
        """
        return self.start()

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Restore the drive configuration when the context exits."""
        if self.__context is not None:
            self.__context.__exit__(exc_type, exc_value, traceback)
            self.__context = None

    @override
    def get_result_severity(self, output: SeverityLevel) -> SeverityLevel:
        return output

    @override
    def get_result_msg(self, output: SeverityLevel) -> str:
        if output == SeverityLevel.SUCCESS:
            return "Success"
        else:
            return "Fail"

from dataclasses import replace
from types import TracebackType
from typing import TYPE_CHECKING, Optional

import ingenialogger
from ingenialink.drive_context_manager import DriveContextManager, DriveRegistersValue
from ingenialink.exceptions import ILError
from typing_extensions import override

from ingeniamotion.enums import CommutationMode, OperationMode, SensorType, SeverityLevel
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.wizard_tests.base_test import BaseTest, ReportBase
from ingeniamotion.wizard_tests.stoppable import StopExceptionError

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
        self._context_manager: Optional[DriveContextManager] = None
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
        # Set the auxiliar feedback to ABS1 because the internal generator is not allowed
        # as auxiliar feedback for all drives
        self.axis_feedbacks.set_configuration(
            replace(
                self.axis_feedbacks.get_configuration(),
                reference=SensorType.INTGEN,
                velocity=SensorType.INTGEN,
                position=SensorType.INTGEN,
                auxiliar=SensorType.ABS1,
            )
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
    def run(
        self, registers_baseline: Optional[DriveRegistersValue] = None
    ) -> Optional[ResultsBrakeTest]:
        """Run the brake test, leaving the drive in its test configuration.

        Unlike a normal test, the brake test keeps the drive configured (and the
        register context open) so the caller can verify the brake. Call ``finish()``
        to disable the motor and restore the drive state.

        Args:
            registers_baseline: Optional pre-built register snapshot used as the
                restore baseline. Read from hardware when not provided.

        Returns:
            The test report (only populated once ``finish()`` runs).

        Raises:
            ILError: If the underlying drive communication fails during the test run.
        """
        self._context_manager = DriveContextManager(
            servo=self.mc._get_drive(self.servo),
            baseline=registers_baseline,
            do_not_restore_registers=list(self.ACCEPTED_CHANGED_REGISTERS),
            track_objects=False,
        )
        self._context_manager.__enter__()
        self.reset_stop()
        try:
            self.setup()
            self.loop()
        except ILError:
            self.finish()
            raise
        except StopExceptionError:
            self.logger.warning("Test has been stopped")
            self.finish()
        return self.report

    def finish(self) -> Optional[ResultsBrakeTest]:
        """Disable the motor and restore the drive state changed during the test.

        Idempotent: a second call (e.g. after ``run()`` already cleaned up on error)
        is a no-op.

        Returns:
            The test report.
        """
        if self._context_manager is None:
            return self.report
        try:
            self.teardown()
        finally:
            self._context_manager.__exit__(None, None, None)
            self._context_manager = None
        self.report = ResultsBrakeTest(
            result_severity=SeverityLevel.SUCCESS,
            result_message=self.get_result_msg(SeverityLevel.SUCCESS),
        )
        return self.report

    def __enter__(self) -> "Brake":
        """Enter the brake-test context. The drive is left configured for the test.

        Returns:
            This brake test instance.
        """
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        """Restore the drive state on context exit by calling ``finish()``."""
        self.finish()

    @override
    def get_result_severity(self, output: SeverityLevel) -> SeverityLevel:
        return output

    @override
    def get_result_msg(self, output: SeverityLevel) -> str:
        if output == SeverityLevel.SUCCESS:
            return "Success"
        else:
            return "Fail"

import math
from enum import IntEnum
from typing import TYPE_CHECKING, ClassVar, Optional

import ingenialogger
from typing_extensions import override

from ingeniamotion.enums import OperationMode, SensorType, SeverityLevel
from ingeniamotion.exceptions import IMTimeoutError
from ingeniamotion.wizard_tests.base_test import BaseTest, LegacyDictReportType, TestError

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class DCFeedbacksResolutionTest(BaseTest[LegacyDictReportType]):
    """DC feedback resolution test class."""

    MOVEMENT_ERROR_FACTOR = 0.05
    DEFAULT_PROFILE_MAX_VEL = 0.3
    DEFAULT_VELOCITY_PID: ClassVar[dict[str, float]] = {"kp": 0.1, "ki": 10, "kd": 0}
    POSITION_TUNE_BW = 1
    MOVEMENT_EXTRA_TIME_FACTOR = 1.5
    MOVEMENT_TIMEOUT = MOVEMENT_EXTRA_TIME_FACTOR / DEFAULT_PROFILE_MAX_VEL
    OPERATION_MODE = OperationMode.PROFILE_POSITION

    PID_LOG_MSG = "Kp = {kp}, Ki = {ki} and Kd = {kd}"

    class ResultType(IntEnum):
        """Test result."""

        SUCCESS = 0

    result_description: ClassVar[dict[ResultType, str]] = {
        ResultType.SUCCESS: "Feedback resolution test has been executed",
    }

    BACKUP_REGISTERS: ClassVar[list[str]] = [
        "CL_POS_FBK_SENSOR",
        "CL_VEL_FBK_SENSOR",
        "CL_AUX_FBK_SENSOR",
        "DRV_OP_CMD",
        "CL_VEL_PID_KP",
        "CL_VEL_PID_KI",
        "CL_VEL_PID_KD",
        "CL_POS_PID_KP",
        "CL_POS_PID_KI",
        "CL_POS_PID_KD",
        "PROF_MAX_VEL",
    ]

    feedback_resolution: int

    def __init__(
        self,
        mc: "MotionController",
        sensor: SensorType,
        servo: str,
        axis: int,
        kp: Optional[float] = None,
        ki: Optional[float] = None,
        kd: Optional[float] = None,
        logger_drive_name: Optional[str] = None,
    ):
        if sensor == SensorType.HALLS:
            raise NotImplementedError("This test is not implemented for Hall sensor")
        super().__init__()
        self.mc = mc
        self.sensor = sensor
        self.servo = servo
        self.axis = axis
        self.backup_registers_names = self.BACKUP_REGISTERS
        self.test_velocity_pid = self.DEFAULT_VELOCITY_PID.copy()
        if kp is not None:
            self.test_velocity_pid["kp"] = kp
            self.test_velocity_pid["ki"] = ki or 0
            self.test_velocity_pid["kd"] = kd or 0
        if logger_drive_name is None:
            self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))
        else:
            self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=logger_drive_name)

    @override
    @BaseTest.stoppable
    def setup(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.logger.info("Motor disable")
        self.feedback_resolution = self.mc.configuration.get_feedback_resolution(
            self.sensor, servo=self.servo, axis=self.axis
        )
        self.mc.configuration.set_velocity_feedback(self.sensor, servo=self.servo, axis=self.axis)
        self.mc.configuration.set_position_feedback(self.sensor, servo=self.servo, axis=self.axis)
        if self.sensor == SensorType.BISSC2:
            self.mc.configuration.set_auxiliar_feedback(
                SensorType.ABS1, servo=self.servo, axis=self.axis
            )
            self.logger.info(
                f"Set velocity and position feedbacks to {self.sensor.name}"
                f" and axuiliar to {SensorType.ABS1.name}"
            )
        else:
            self.mc.configuration.set_auxiliar_feedback(
                self.sensor, servo=self.servo, axis=self.axis
            )
            self.logger.info(f"Set velocity, position and auxiliar feedbacks to {self.sensor.name}")
        self.mc.configuration.set_velocity_pid(
            **self.test_velocity_pid, servo=self.servo, axis=self.axis
        )
        self.logger.info(f"Velocity PID set to {self.PID_LOG_MSG.format(**self.test_velocity_pid)}")
        position_kp = 2.0 * math.pi * self.POSITION_TUNE_BW / self.feedback_resolution
        self.mc.configuration.set_position_pid(kp=position_kp, servo=self.servo, axis=self.axis)
        self.logger.info(
            f"Position PID set to {self.PID_LOG_MSG.format(kp=position_kp, ki=0, kd=0)}"
        )
        self.mc.configuration.set_max_profile_velocity(
            self.DEFAULT_PROFILE_MAX_VEL, servo=self.servo, axis=self.axis
        )
        self.logger.info(f"Maximum profile velocity set to {self.DEFAULT_PROFILE_MAX_VEL}")
        self.mc.motion.set_operation_mode(self.OPERATION_MODE, servo=self.servo, axis=self.axis)
        self.logger.info(f"Set operation mode to {self.OPERATION_MODE.name}")

    @override
    @BaseTest.stoppable
    def loop(self) -> ResultType:
        initial_pos = self.mc.motion.get_actual_position(servo=self.servo, axis=self.axis)
        self.mc.motion.move_to_position(initial_pos, servo=self.servo, axis=self.axis)
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
        self.logger.info("Motor enable")
        try:
            self.logger.info(f"Try to reach position {initial_pos + self.feedback_resolution}")
            self.mc.motion.move_to_position(
                initial_pos + self.feedback_resolution,
                servo=self.servo,
                axis=self.axis,
                blocking=True,
                error=int(self.feedback_resolution * self.MOVEMENT_ERROR_FACTOR),
                timeout=self.MOVEMENT_TIMEOUT,
            )
        except IMTimeoutError as e:
            final_position = self.mc.motion.get_actual_position(servo=self.servo, axis=self.axis)
            if (
                abs(final_position - initial_pos)
                > self.feedback_resolution * self.MOVEMENT_ERROR_FACTOR
            ):
                raise TestError(e) from e
            raise TestError(
                "ERROR: No movement detected. Please, review your feedback configuration & wiring"
            ) from e
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        return self.ResultType.SUCCESS

    @override
    def teardown(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.logger.info("Motor disable")

    @override
    def get_result_msg(self, output: ResultType) -> str:
        description = self.result_description.get(output)
        if description is None:
            raise NotImplementedError("Result description not implemented")
        return description

    @override
    def get_result_severity(self, output: ResultType) -> SeverityLevel:
        if output == self.ResultType.SUCCESS:
            return SeverityLevel.SUCCESS
        return SeverityLevel.FAIL

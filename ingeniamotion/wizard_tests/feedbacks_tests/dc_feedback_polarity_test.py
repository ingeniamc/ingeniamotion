from enum import IntEnum
from typing import TYPE_CHECKING, Optional

import ingenialogger

from ingeniamotion.enums import FeedbackPolarity, OperationMode, SensorType, SeverityLevel
from ingeniamotion.wizard_tests.base_test import BaseTest, LegacyDictReportType, TestError

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class DCFeedbacksPolarityTest(BaseTest[LegacyDictReportType]):
    MOVEMENT_ERROR_FACTOR = 0.05
    CURRENT_RAMP_TOTAL_TIME = 5
    CURRENT_RAMP_INTERVAL = 0.1
    OPERATION_MODE = OperationMode.CURRENT

    class ResultType(IntEnum):
        """Test result."""

        SUCCESS = 0

    result_description = {
        ResultType.SUCCESS: "Feedback polarity test pass successfully",
    }

    BACKUP_REGISTERS = [
        "CL_POS_FBK_SENSOR",
        "CL_VEL_FBK_SENSOR",
        "CL_AUX_FBK_SENSOR",
        "DRV_OP_CMD",
        "CL_CUR_Q_SET_POINT",
    ]

    feedback_resolution: int

    def __init__(
        self,
        mc: "MotionController",
        sensor: SensorType,
        servo: str,
        axis: int,
        logger_drive_name: Optional[str] = None,
    ):
        if sensor == SensorType.HALLS:
            raise NotImplementedError("This test is not implemented for Hall sensor")
        super().__init__()
        self.mc = mc
        self.sensor = sensor
        self.servo = servo
        self.axis = axis
        self.BACKUP_REGISTERS.append(mc.configuration.get_feedback_polarity_register_uid(sensor))
        self.backup_registers_names = self.BACKUP_REGISTERS
        if logger_drive_name is None:
            self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))
        else:
            self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=logger_drive_name)

    @BaseTest.stoppable
    def setup(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.logger.info("Motor disable")
        self.feedback_resolution = self.mc.configuration.get_feedback_resolution(
            self.sensor, servo=self.servo, axis=self.axis
        )
        self.mc.configuration.set_feedback_polarity(
            FeedbackPolarity.NORMAL, self.sensor, servo=self.servo, axis=self.axis
        )
        self.logger.info(f"Set polarity to {FeedbackPolarity.NORMAL.name}")
        self.mc.motion.set_current_quadrature(0, servo=self.servo, axis=self.axis)
        self.logger.info("Set current to 0")
        self.mc.motion.set_operation_mode(self.OPERATION_MODE, servo=self.servo, axis=self.axis)
        self.logger.info(f"Set operation mode to {self.OPERATION_MODE.name}")
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

    @BaseTest.stoppable
    def increase_current_until_movement(self, initial_position: int, max_current: float) -> int:
        """Increase motor current until it moves.

        Args:
            initial_position: initial position
            max_current: motor rated current

        Returns:
            returns final position

        Raises:
            TestError: No movement detected

        """
        for set_curr in self.mc.motion.ramp_generator(
            0, max_current, self.CURRENT_RAMP_TOTAL_TIME, self.CURRENT_RAMP_INTERVAL
        ):
            self.check_stop()
            current_pos = self.mc.motion.get_actual_position(servo=self.servo, axis=self.axis)
            if (
                abs(current_pos - initial_position)
                > self.feedback_resolution * self.MOVEMENT_ERROR_FACTOR
            ):
                self.mc.motion.motor_disable(self.servo, self.axis)
                return current_pos
            self.mc.motion.set_current_quadrature(set_curr, servo=self.servo, axis=self.axis)
            self.logger.info(f"Set current to {set_curr}")
        self.mc.motion.motor_disable(self.servo, self.axis)
        raise TestError(
            "ERROR: No movement detected. Please, review your feedback configuration & wiring"
        )

    @staticmethod
    def calculate_polarity(initial_position: int, final_position: int) -> FeedbackPolarity:
        """Calculate motor polarity.

        Args:
            initial_position: initial position
            final_position: final position

        Returns:
            If final position is smaller than initial position return REVERSED, else NORMAL

        """
        if final_position - initial_position < 0:
            return FeedbackPolarity.REVERSED
        return FeedbackPolarity.NORMAL

    @BaseTest.stoppable
    def loop(self) -> ResultType:
        rated_current = self.mc.configuration.get_rated_current(servo=self.servo, axis=self.axis)
        max_current = self.mc.configuration.get_max_current(servo=self.servo, axis=self.axis)
        test_current = min(rated_current, max_current)
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
        self.logger.info("Motor enable")
        initial_position = self.mc.motion.get_actual_position(servo=self.servo, axis=self.axis)
        final_position = self.increase_current_until_movement(initial_position, test_current)
        polarity = self.calculate_polarity(initial_position, final_position)
        self.logger.info(f"Polarity found: {polarity.name}")
        polarity_uid = self.mc.configuration.get_feedback_polarity_register_uid(self.sensor)
        self.suggested_registers[polarity_uid] = polarity
        return self.ResultType.SUCCESS

    def teardown(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.logger.info("Motor disable")

    def get_result_msg(self, output: ResultType) -> str:
        description = self.result_description.get(output)
        if description is None:
            raise NotImplementedError("Result description not implemented")
        return description

    def get_result_severity(self, output: ResultType) -> SeverityLevel:
        if output == self.ResultType.SUCCESS:
            return SeverityLevel.SUCCESS
        return SeverityLevel.FAIL

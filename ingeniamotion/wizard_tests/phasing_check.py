from enum import IntEnum
import time
from typing import TYPE_CHECKING

import ingenialogger

from ingeniamotion.wizard_tests.base_test import BaseTest, TestError
from ingeniamotion.metaclass import DEFAULT_SERVO, DEFAULT_AXIS
from ingeniamotion.enums import SensorType, OperationMode, PhasingMode, SeverityLevel
if TYPE_CHECKING:
    from ingeniamotion import MotionController


class PhasingCheck(BaseTest):

    MAX_ALLOWED_ANGLE_MOVE = 15
    INITIAL_ANGLE = 180.0
    INITIAL_ANGLE_HALLS = 240.0
    CURRENT_SLOPE = 0.4

    PHASING_ACCURACY_REGISTER = "COMMU_PHASING_ACCURACY"
    PHASING_TIMEOUT_REGISTER = "COMMU_PHASING_TIMEOUT"
    MAX_CURRENT_ON_PHASING_SEQUENCE_REGISTER = "COMMU_PHASING_MAX_CURRENT"

    BACKUP_REGISTERS = ["DRV_OP_CMD", "CL_CUR_Q_SET_POINT", "CL_CUR_D_SET_POINT"]

    class ResultType(IntEnum):
        SUCCESS = 0
        WRONG_PHASING = -1

    result_description = {
        ResultType.SUCCESS: "Motor is well phased.",
        ResultType.WRONG_PHASING: "Phasing check failed. Wrong motor phasing.",
    }

    def __init__(
        self, mc: "MotionController", servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))
        self.backup_registers_names = self.BACKUP_REGISTERS

    @BaseTest.stoppable
    def setup(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.mc.motion.set_operation_mode(OperationMode.CURRENT, servo=self.servo, axis=self.axis)
        self.mc.motion.set_current_quadrature(0, servo=self.servo, axis=self.axis)
        self.mc.motion.set_current_direct(0, servo=self.servo, axis=self.axis)

    @BaseTest.stoppable
    def vary_current_and_check_position(self, current_sign: int, max_current: int) -> ResultType:
        init_pos = self.mc.motion.get_actual_position(servo=self.servo, axis=self.axis)
        pos_resolution = self.mc.configuration.get_position_feedback_resolution(
            servo=self.servo, axis=self.axis
        )
        is_ok = True
        total_time = max_current / self.CURRENT_SLOPE
        for value in self.mc.motion.ramp_generator(
            0, current_sign * max_current, total_time, interval=0.1
        ):
            self.mc.motion.set_current_direct(value, servo=self.servo, axis=self.axis)
            is_ok = self.check_position(init_pos, pos_resolution)
            if not is_ok:
                break
        self.mc.motion.set_current_direct(0, servo=self.servo, axis=self.axis)
        if not is_ok:
            return self.ResultType.WRONG_PHASING
        return self.ResultType.SUCCESS

    @BaseTest.stoppable
    def check_position(self, init_pos: int, resolution: int) -> bool:
        current_pos = self.mc.motion.get_actual_position(servo=self.servo, axis=self.axis)
        allowed_move = resolution * self.MAX_ALLOWED_ANGLE_MOVE / 360
        result_check = float(abs(current_pos - init_pos)) < allowed_move
        return result_check

    @BaseTest.stoppable
    def analyse_phasing_bit_and_force_to_high(self) -> None:
        if not self.mc.configuration.is_commutation_feedback_aligned(
            servo=self.servo, axis=self.axis
        ):
            phasing_mode = self.mc.configuration.get_phasing_mode(servo=self.servo, axis=self.axis)
            if phasing_mode == PhasingMode.FORCED:
                self.forced_phasing()
            else:
                self.not_forced_phasing()

    @BaseTest.stoppable
    def define_phasing_steps(self) -> int:
        pha_accuracy = self.mc.communication.get_register(
            self.PHASING_ACCURACY_REGISTER, servo=self.servo, axis=self.axis
        )
        if not isinstance(pha_accuracy, int):
            raise TypeError(f"{self.PHASING_ACCURACY_REGISTER} has to be an integer")
        delta = 3 * pha_accuracy / 1000
        ref_feedback = self.mc.configuration.get_reference_feedback(
            servo=self.servo, axis=self.axis
        )

        num_of_steps = 1
        if ref_feedback == SensorType.HALLS:
            actual_angle = self.INITIAL_ANGLE_HALLS
        else:
            actual_angle = self.INITIAL_ANGLE
        while actual_angle > delta:
            actual_angle = actual_angle / 2
            num_of_steps += 1
        return num_of_steps

    @BaseTest.stoppable
    def forced_phasing(self) -> None:
        num_of_steps = self.define_phasing_steps()
        phasing_bit_latched = False
        phasing_timeout = self.mc.communication.get_register(
            self.PHASING_TIMEOUT_REGISTER, servo=self.servo, axis=self.axis
        )
        if not isinstance(phasing_timeout, int):
            raise TypeError(f"{self.PHASING_TIMEOUT_REGISTER} has to be an integer")
        timeout = time.time() + (num_of_steps * phasing_timeout / 1000)
        while time.time() < timeout:
            self.stoppable_sleep(0.1)
            if self.mc.configuration.is_commutation_feedback_aligned(
                servo=self.servo, axis=self.axis
            ):
                phasing_bit_latched = True
                break
        if not phasing_bit_latched:
            raise TestError("Motor phasing fail")

    @BaseTest.stoppable
    def not_forced_phasing(self) -> None:
        self.logger.info(
            "Increasing slowly current quadrature set-point until phasing bit is latched"
        )
        phasing_bit_latched = False
        i = 0.0
        delta_i = 0.1
        while not phasing_bit_latched:
            if not self.mc.configuration.is_motor_enabled(servo=self.servo, axis=self.axis):
                self.mc.errors.get_last_buffer_error(servo=self.servo, axis=self.axis)
                self.show_error_message()
            self.mc.motion.set_current_quadrature(i, servo=self.servo, axis=self.axis)
            self.stoppable_sleep(0.1)
            i += delta_i
            if self.mc.configuration.is_commutation_feedback_aligned(
                servo=self.servo, axis=self.axis
            ):
                phasing_bit_latched = True
        self.mc.motion.set_current_quadrature(0, servo=self.servo, axis=self.axis)
        self.logger.info("Wait until motor has stopped")
        self.mc.motion.wait_for_velocity(0, servo=self.servo, axis=self.axis)

    @BaseTest.stoppable
    def check_motor_commutation(self) -> ResultType:
        phasing_current = self.mc.communication.get_register(
            self.MAX_CURRENT_ON_PHASING_SEQUENCE_REGISTER, servo=self.servo, axis=self.axis
        )
        if not isinstance(phasing_current, float):
            raise TypeError(
                f"{self.MAX_CURRENT_ON_PHASING_SEQUENCE_REGISTER} has to be an integer"
            )
        max_test_current = round(phasing_current, 2)
        ref_feedback = self.mc.configuration.get_reference_feedback(
            servo=self.servo, axis=self.axis
        )
        comm_feedback = self.mc.configuration.get_commutation_feedback(
            servo=self.servo, axis=self.axis
        )

        # With Halls only, this test makes no sense
        if ref_feedback == SensorType.HALLS and comm_feedback == SensorType.HALLS:
            return self.ResultType.SUCCESS

        self.logger.info(
            "{} {} {}".format(
                "Slowly increasing Current Direct Set-point until", max_test_current, "A"
            )
        )
        result = self.vary_current_and_check_position(1, max_test_current)
        if result != self.ResultType.SUCCESS:
            return result
        self.logger.info(
            "{} {} {}".format(
                "Slowly decreasing Current Direct Set-point until", -max_test_current, "A"
            )
        )
        return self.vary_current_and_check_position(-1, max_test_current)

    @BaseTest.stoppable
    def loop(self) -> ResultType:
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
        self.analyse_phasing_bit_and_force_to_high()
        return self.check_motor_commutation()

    def teardown(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)

    def get_result_msg(self, output: ResultType) -> str:
        return self.result_description[output]

    def get_result_severity(self, output: ResultType) -> SeverityLevel:
        if output < self.ResultType.SUCCESS:
            return SeverityLevel.FAIL
        else:
            return SeverityLevel.SUCCESS

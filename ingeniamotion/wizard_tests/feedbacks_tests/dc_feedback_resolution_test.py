from enum import IntEnum
from typing import TYPE_CHECKING

import ingenialogger

from ingeniamotion.exceptions import IMTimeoutError
from ingeniamotion.wizard_tests.base_test import BaseTest, TestError
from ingeniamotion.enums import SensorType, OperationMode, SeverityLevel

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class DCFeedbacksResolutionTest(BaseTest):
    MOVEMENT_ERROR_FACTOR = 0.05
    DEFAULT_PROFILE_MAX_VEL = 0.3
    DEFAULT_VELOCITY_PID = {"kp": 3, "ki": 1, "kd": 0}
    DEFAULT_POSITION_PID = {"kp": 0.01, "ki": 0, "kd": 0}
    MOVEMENT_EXTRA_TIME_FACTOR = 1.5
    MOVEMENT_TIMEOUT = MOVEMENT_EXTRA_TIME_FACTOR / DEFAULT_PROFILE_MAX_VEL

    class ResultType(IntEnum):
        SUCCESS = 0

    result_description = {
        ResultType.SUCCESS: "Feedback resolution test has been executed",
    }

    BACKUP_REGISTERS = [
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

    def __init__(self, mc: "MotionController", sensor: SensorType, servo: str, axis: int):
        if sensor == SensorType.HALLS:
            raise NotImplementedError("This test is not implemented for Hall sensor")
        super().__init__()
        self.mc = mc
        self.sensor = sensor
        self.servo = servo
        self.axis = axis
        self.backup_registers_names = self.BACKUP_REGISTERS

    def setup(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.feedback_resolution = self.mc.configuration.get_feedback_resolution(
            self.sensor, servo=self.servo, axis=self.axis
        )
        self.mc.configuration.set_velocity_feedback(self.sensor, servo=self.servo, axis=self.axis)
        self.mc.configuration.set_position_feedback(self.sensor, servo=self.servo, axis=self.axis)
        if self.sensor == SensorType.BISSC2:
            self.mc.configuration.set_auxiliar_feedback(
                SensorType.ABS1, servo=self.servo, axis=self.axis
            )
        else:
            self.mc.configuration.set_auxiliar_feedback(
                self.sensor, servo=self.servo, axis=self.axis
            )
        self.mc.configuration.set_velocity_pid(
            **self.DEFAULT_VELOCITY_PID, servo=self.servo, axis=self.axis
        )
        self.mc.configuration.set_position_pid(
            **self.DEFAULT_POSITION_PID, servo=self.servo, axis=self.axis
        )
        self.mc.configuration.set_max_profile_velocity(
            self.DEFAULT_PROFILE_MAX_VEL, servo=self.servo, axis=self.axis
        )
        self.mc.motion.set_operation_mode(
            OperationMode.PROFILE_POSITION_S_CURVE, servo=self.servo, axis=self.axis
        )

    def loop(self) -> ResultType:
        initial_pos = self.mc.motion.get_actual_position(servo=self.servo, axis=self.axis)
        self.mc.motion.move_to_position(initial_pos, servo=self.servo, axis=self.axis)
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
        try:
            self.mc.motion.move_to_position(
                initial_pos + self.feedback_resolution,
                servo=self.servo,
                axis=self.axis,
                blocking=True,
                timeout=self.MOVEMENT_TIMEOUT,
            )
        except IMTimeoutError as e:
            final_position = self.mc.motion.get_actual_position(servo=self.servo, axis=self.axis)
            if abs(final_position - initial_pos) > self.feedback_resolution * 0.1:
                raise TestError(e) from e
            raise TestError(
                "ERROR: No movement detected. Please, review your feedback configuration & wiring"
            ) from e
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        return self.ResultType.SUCCESS

    def teardown(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)

    def get_result_msg(self, output: ResultType) -> str:
        description = self.result_description.get(output)
        if description is None:
            raise NotImplementedError("Result description not implemented")
        return description

    def get_result_severity(self, output: ResultType) -> SeverityLevel:
        if output == self.ResultType.SUCCESS:
            return SeverityLevel.SUCCESS
        return SeverityLevel.FAIL

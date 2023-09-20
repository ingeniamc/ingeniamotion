from enum import IntEnum
from typing import Optional, Union

import ingenialogger

from ingeniamotion.enums import SeverityLevel, OperationMode
from ingeniamotion.exceptions import IMRegisterNotExist
from ingeniamotion.metaclass import DEFAULT_SERVO, DEFAULT_AXIS
from ingeniamotion.motion_controller import MotionController
from ingeniamotion.wizard_tests import stoppable
from ingeniamotion.wizard_tests.base_test import BaseTest


class BrakeRegKey(IntEnum):
    """Brake Register Keys for dictionaries"""

    FEEDBACK_SOURCE = 0
    CONTROL_MODE = 1


class ResultBrakeType(IntEnum):
    """Type of result once a brake tuning is stopped or failed"""

    SUCCESS = 0
    FAIL_FEEDBACK_SOURCE = 1
    FAIL_CURRENT_MODE = 2
    FAIL_DICTIONARY = 3


class BrakeTune(BaseTest):
    """A class to perform a brake tuning. It enables and disables a brake through enabling/disabling the motor.

    Args:
        mc: Motion Controller.
        enable_disable_motor_period: Period of time in seconds between a motor starts to be enabled,
            and it finishes to be disabled.
        servo: servo alias to reference it. ``default`` by default.
        axis: axis that will run the test. 1 by default.

    """

    BRAKE_CURRENT_FEEDBACK_SOURCE = "MOT_BRAKE_CUR_FBK"
    BRAKE_CONTROL_MODE = "MOT_BRAKE_CONTROL_MODE"

    BACKUP_REGISTERS = [
        "MOT_BRAKE_OVERRIDE",
        "DRV_OP_CMD",
        "CL_VOL_Q_SET_POINT",
        "CL_VOL_D_SET_POINT",
    ]

    def __init__(
        self,
        mc: MotionController,
        enable_disable_motor_period: float = 1.0,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))
        self.backup_registers_names = self.BACKUP_REGISTERS
        self.__enable_disable_motor_period = enable_disable_motor_period

    def setup(self) -> None:
        # Make sure Brake override is disabled
        self.mc.configuration.disable_brake_override(servo=self.servo, axis=self.axis)
        # Make sure the operation mode is set as Voltage mode
        self.mc.motion.set_operation_mode(OperationMode.VOLTAGE, servo=self.servo, axis=self.axis)
        # Make sure quadrature voltage is set to 0v
        self.mc.motion.set_voltage_quadrature(0, servo=self.servo, axis=self.axis)
        # Make sure direct voltage is set to 0v
        self.mc.motion.set_voltage_direct(0, servo=self.servo, axis=self.axis)

    @BaseTest.stoppable
    def loop(self) -> Optional[ResultBrakeType]:
        try:
            reg_values = self.__update_brake_registers_values()
        except IMRegisterNotExist:
            return ResultBrakeType.FAIL_DICTIONARY
        # Register values to avoid meanwhile the test is being executed
        no_brake_current_feedback_source = 0
        brake_is_current_mode = 1
        # Start the test
        try:
            while (
                reg_values[BrakeRegKey.FEEDBACK_SOURCE] != no_brake_current_feedback_source
            ) and (reg_values[BrakeRegKey.CONTROL_MODE] == brake_is_current_mode):
                # Motor enable
                self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
                self.stoppable_sleep(self.__enable_disable_motor_period / 2)
                # Motor disable
                self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
                self.stoppable_sleep(self.__enable_disable_motor_period / 2)

                reg_values = self.__update_brake_registers_values()
        except stoppable.StopException:
            self.logger.info("Test has been stopped")
            return ResultBrakeType.SUCCESS

        if reg_values[BrakeRegKey.FEEDBACK_SOURCE] == no_brake_current_feedback_source:
            return ResultBrakeType.FAIL_FEEDBACK_SOURCE
        elif reg_values[BrakeRegKey.CONTROL_MODE] != brake_is_current_mode:
            return ResultBrakeType.FAIL_CURRENT_MODE
        else:
            return None

    def __update_brake_registers_values(self) -> dict[BrakeRegKey, Union[int, float, str]]:
        brake_registers_updated = {}
        updated_brake_current_feedback_source = self.mc.communication.get_register(
            self.BRAKE_CURRENT_FEEDBACK_SOURCE, servo=self.servo, axis=self.axis
        )
        brake_registers_updated[BrakeRegKey.FEEDBACK_SOURCE] = updated_brake_current_feedback_source
        updated_brake_control_mode = self.mc.communication.get_register(
            self.BRAKE_CONTROL_MODE, servo=self.servo, axis=self.axis
        )
        brake_registers_updated[BrakeRegKey.CONTROL_MODE] = updated_brake_control_mode
        return brake_registers_updated

    def teardown(self) -> None:
        self.logger.info("Disabling brake")
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)

    def get_result_severity(self, output: ResultBrakeType) -> SeverityLevel:
        severity_options = {
            ResultBrakeType.SUCCESS: SeverityLevel.SUCCESS,
            ResultBrakeType.FAIL_FEEDBACK_SOURCE: SeverityLevel.FAIL,
            ResultBrakeType.FAIL_CURRENT_MODE: SeverityLevel.FAIL,
            ResultBrakeType.FAIL_DICTIONARY: SeverityLevel.FAIL,
        }
        return severity_options[output]

    def get_result_msg(self, output: ResultBrakeType) -> str:
        message_options = {
            ResultBrakeType.SUCCESS: "Brake tune is stopped properly",
            ResultBrakeType.FAIL_FEEDBACK_SOURCE: "A brake current feedback source is not set",
            ResultBrakeType.FAIL_CURRENT_MODE: "The brake is not in current mode",
            ResultBrakeType.FAIL_DICTIONARY: "Brake current control mode is not implemented in the drive",
        }
        return message_options[output]

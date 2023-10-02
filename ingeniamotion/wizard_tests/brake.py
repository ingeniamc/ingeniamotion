from typing import TYPE_CHECKING, Dict, Union

import ingenialogger
from ingenialink.exceptions import ILError

from ingeniamotion.wizard_tests.base_test import BaseTest
from ingeniamotion.wizard_tests.stoppable import StopException
from ingeniamotion.enums import OperationMode, SeverityLevel
from ingeniamotion.metaclass import DEFAULT_SERVO, DEFAULT_AXIS

if TYPE_CHECKING:
    from ingeniamotion import MotionController


class Brake(BaseTest):

    BRAKE_OVERRIDE_REGISTER = "MOT_BRAKE_OVERRIDE"

    BACKUP_REGISTERS = [
        "MOT_BRAKE_OVERRIDE",
        "DRV_OP_CMD",
        "MOT_PAIR_POLES",
        "COMMU_PHASING_MODE",
        "COMMU_ANGLE_SENSOR",
        "MOT_COMMU_MOD",
    ]

    def __init__(
        self, mc: "MotionController", servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))
        self.backup_registers_names = self.BACKUP_REGISTERS

    def setup(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.mc.configuration.disable_brake_override(servo=self.servo, axis=self.axis)
        self.mc.communication.set_register("MOT_COMMU_MOD", 0, servo=self.servo, axis=self.axis)
        self.mc.motion.set_internal_generator_configuration(
            OperationMode.VOLTAGE, servo=self.servo, axis=self.axis
        )

    def loop(self) -> SeverityLevel:
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
        return SeverityLevel.SUCCESS

    def teardown(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)

    def finish(self, output: SeverityLevel) -> Dict[str, Union[SeverityLevel, str]]:
        try:
            self.teardown()
        finally:
            self.restore_backup_registers()
        return {
            "result_severity": self.get_result_severity(output),
            "result_message": self.get_result_msg(output),
        }

    def run(self) -> None:
        self.reset_stop()
        self.save_backup_registers()
        try:
            self.setup()
            output = self.loop()
        except ILError as err:
            self.finish(output)
            raise err
        except StopException:
            self.logger.warning("Test has been stopped")
            self.finish(output)

    def get_result_severity(self, output: SeverityLevel) -> SeverityLevel:
        return output

    def get_result_msg(self, output: SeverityLevel) -> str:
        if output == SeverityLevel.SUCCESS:
            return "Success"
        else:
            return "Fail"

import ingenialogger

from ingenialink.exceptions import ILError

from .base_test import BaseTest
from .stoppable import StopException
from ingeniamotion.enums import OperationMode, SeverityLevel
from ingeniamotion.metaclass import DEFAULT_SERVO, DEFAULT_AXIS


class Brake(BaseTest):

    BRAKE_OVERRIDE_REGISTER = "MOT_BRAKE_OVERRIDE"

    BACKUP_REGISTERS = ["MOT_BRAKE_OVERRIDE",
                        "DRV_OP_CMD",
                        "MOT_PAIR_POLES",
                        "COMMU_PHASING_MODE",
                        "COMMU_ANGLE_SENSOR"]

    def __init__(self, mc, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        self.logger = ingenialogger.get_logger(__name__, axis=axis,
                                               drive=mc.servo_name(servo))
        self.backup_registers_names = self.BACKUP_REGISTERS

    def setup(self):
        self.mc.motion.motor_disable(
            servo=self.servo, axis=self.axis)
        self.mc.configuration.disable_brake_override(
            servo=self.servo, axis=self.axis)
        self.mc.motion.set_internal_generator_configuration(
            OperationMode.VOLTAGE, servo=self.servo, axis=self.axis)

    def loop(self):
        self.mc.motion.motor_enable(
            servo=self.servo, axis=self.axis)

    def teardown(self):
        self.mc.motion.motor_disable(
            servo=self.servo, axis=self.axis)

    def finish(self):
        try:
            self.teardown()
        finally:
            self.restore_backup_registers()
        output = SeverityLevel.SUCCESS
        return {
            "result_severity": self.get_result_severity(output),
            "result_message": self.get_result_msg(output)
        }

    def run(self):
        self.reset_stop()
        self.save_backup_registers()
        try:
            self.setup()
            self.loop()
        except ILError as err:
            self.finish()
            raise err
        except StopException:
            self.logger.warning("Test has been stopped")
            self.finish()

    def get_result_severity(self, output):
        return output

    def get_result_msg(self, output):
        if output == SeverityLevel.SUCCESS:
            return "Success"
        else:
            return "Fail"

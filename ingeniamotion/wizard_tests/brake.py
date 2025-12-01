from typing import TYPE_CHECKING, ClassVar, Optional, Union

import ingenialogger
from ingenialink.exceptions import ILError
from typing_extensions import override

from ingeniamotion.enums import CommutationMode, OperationMode, SensorType, SeverityLevel
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.wizard_tests.base_test import BaseTest
from ingeniamotion.wizard_tests.stoppable import StopExceptionError

if TYPE_CHECKING:
    from ingeniamotion import MotionController


class Brake(BaseTest[None]):  # type: ignore [type-var]
    """Brake test class."""

    BRAKE_OVERRIDE_REGISTER = "MOT_BRAKE_OVERRIDE"

    PRIMARY_ABSOLUTE_SLAVE_1_PROTOCOL = "FBK_BISS1_SSI1_PROTOCOL"

    BACKUP_REGISTERS: ClassVar[list[str]] = [
        "MOT_BRAKE_OVERRIDE",
        "DRV_OP_CMD",
        "MOT_PAIR_POLES",
        "COMMU_PHASING_MODE",
        "COMMU_ANGLE_SENSOR",
        "COMMU_ANGLE_REF_SENSOR",
        "CL_VEL_FBK_SENSOR",
        "CL_POS_FBK_SENSOR",
        "CL_AUX_FBK_SENSOR",
        "MOT_COMMU_MOD",
        PRIMARY_ABSOLUTE_SLAVE_1_PROTOCOL,
    ]

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
        self.backup_registers_names = self.BACKUP_REGISTERS

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
        self.mc.configuration.set_auxiliar_feedback(
            SensorType.ABS1, servo=self.servo, axis=self.axis
        )
        self.mc.communication.set_register(
            self.PRIMARY_ABSOLUTE_SLAVE_1_PROTOCOL, 1, servo=self.servo, axis=self.axis
        )

    @override
    def loop(self) -> None:
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)

    @override
    def teardown(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)

    def finish(self) -> dict[str, Union[SeverityLevel, str]]:
        """Finish the test.

        Returns:
            The test result.

        """
        try:
            self.teardown()
        finally:
            self.restore_backup_registers()
        output = SeverityLevel.SUCCESS
        return {
            "result_severity": self.get_result_severity(output),
            "result_message": self.get_result_msg(output),
        }

    @override
    def run(self) -> None:
        self.reset_stop()
        self.save_backup_registers()
        try:
            self.setup()
            self.loop()
        except ILError as err:
            self.finish()
            raise err
        except StopExceptionError:
            self.logger.warning("Test has been stopped")
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

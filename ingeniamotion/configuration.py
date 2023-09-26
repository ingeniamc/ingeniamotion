from os import path
from enum import IntEnum
from typing import Optional

from ingenialink import Servo
from ingenialink.exceptions import ILError
import ingenialogger
from ingeniamotion.exceptions import IMException

from ingeniamotion.homing import Homing
from ingeniamotion.feedbacks import Feedbacks
from ingeniamotion.enums import PhasingMode, GeneratorMode
from ingeniamotion.metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO


class TYPE_SUBNODES(IntEnum):
    COCO = 0
    MOCO = 1


class Configuration(Homing, Feedbacks, metaclass=MCMetaClass):
    """Configuration."""

    class BrakeOverride(IntEnum):
        """Brake override configuration enum"""

        OVERRIDE_DISABLED = 0
        RELEASE_BRAKE = 1
        ENABLE_BRAKE = 2

    BRAKE_OVERRIDE_REGISTER = "MOT_BRAKE_OVERRIDE"
    PROFILE_MAX_ACCELERATION_REGISTER = "PROF_MAX_ACC"
    PROFILE_MAX_DECELERATION_REGISTER = "PROF_MAX_DEC"
    PROFILE_MAX_VELOCITY_REGISTER = "PROF_MAX_VEL"
    MAX_VELOCITY_REGISTER = "CL_VEL_REF_MAX"
    POWER_STAGE_FREQUENCY_SELECTION_REGISTER = "DRV_PS_FREQ_SELECTION"
    POWER_STAGE_FREQUENCY_REGISTERS = [
        "DRV_PS_FREQ_1",
        "DRV_PS_FREQ_2",
        "DRV_PS_FREQ_3",
        "DRV_PS_FREQ_4",
    ]
    POSITION_AND_VELOCITY_LOOP_RATE_REGISTER = "DRV_POS_VEL_RATE"
    CURRENT_LOOP_RATE_REGISTER = "CL_CUR_FREQ"
    STATUS_WORD_REGISTER = "DRV_STATE_STATUS"
    PHASING_MODE_REGISTER = "COMMU_PHASING_MODE"
    GENERATOR_MODE_REGISTER = "FBK_GEN_MODE"
    MOTOR_POLE_PAIRS_REGISTER = "MOT_PAIR_POLES"
    STO_STATUS_REGISTER = "DRV_PROT_STO_STATUS"

    STATUS_WORD_OPERATION_ENABLED_BIT = 0x04
    STATUS_WORD_COMMUTATION_FEEDBACK_ALIGNED_BIT = 0x4000
    STO1_ACTIVE_BIT = 0x1
    STO2_ACTIVE_BIT = 0x2
    STO_SUPPLY_FAULT_BIT = 0x4
    STO_ABNORMAL_FAULT_BIT = 0x8
    STO_REPORT_BIT = 0x10

    STO_ACTIVE_STATE = 4
    STO_INACTIVE_STATE = 23
    STO_LATCHED_STATE = 31

    PRODUCT_ID_REGISTERS = {
        TYPE_SUBNODES.COCO: "DRV_ID_PRODUCT_CODE_COCO",
        TYPE_SUBNODES.MOCO: "DRV_ID_PRODUCT_CODE",
    }
    REVISION_NUMBER_REGISTERS = {
        TYPE_SUBNODES.COCO: "DRV_ID_REVISION_NUMBER_COCO",
        TYPE_SUBNODES.MOCO: "DRV_ID_REVISION_NUMBER",
    }
    SERIAL_NUMBER_REGISTERS = {
        TYPE_SUBNODES.COCO: "DRV_ID_SERIAL_NUMBER_COCO",
        TYPE_SUBNODES.MOCO: "DRV_ID_SERIAL_NUMBER",
    }
    SOFTWARE_VERSION_REGISTERS = {
        TYPE_SUBNODES.COCO: "DRV_APP_COCO_VERSION",
        TYPE_SUBNODES.MOCO: "DRV_ID_SOFTWARE_VERSION",
    }

    def __init__(self, motion_controller):
        Homing.__init__(self, motion_controller)
        Feedbacks.__init__(self, motion_controller)
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def release_brake(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> None:
        """Override the brake status to released in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. 1 by default.

        """
        self.mc.communication.set_register(
            self.BRAKE_OVERRIDE_REGISTER, self.BrakeOverride.RELEASE_BRAKE, servo=servo, axis=axis
        )

    def enable_brake(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> None:
        """Override the brake status of the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. 1 by default.

        """
        self.mc.communication.set_register(
            self.BRAKE_OVERRIDE_REGISTER, self.BrakeOverride.ENABLE_BRAKE, servo=servo, axis=axis
        )

    def disable_brake_override(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> None:
        """Disable the brake override of the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. 1 by default.

        """
        self.mc.communication.set_register(
            self.BRAKE_OVERRIDE_REGISTER,
            self.BrakeOverride.OVERRIDE_DISABLED,
            servo=servo,
            axis=axis,
        )

    def default_brake(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> None:
        """Disable the brake override of the target servo and axis, as
        :func:`disable_brake_override`.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. 1 by default.

        """
        self.disable_brake_override(servo, axis)

    def load_configuration(
        self, config_path: str, axis: Optional[int] = None, servo: str = DEFAULT_SERVO
    ) -> None:
        """Load a configuration file to the target servo.

        Args:
            config_path : config file path to load.
            axis : target axis to load configuration.
                If ``None`` function loads all axis. ``None`` by default.
            servo : servo alias to reference it. ``default`` by default.

        Raises:
            FileNotFoundError: If configuration file does not exist.

        """
        if not path.isfile(config_path):
            raise FileNotFoundError("{} file does not exist!".format(config_path))
        servo_inst = self.mc.servos[servo]
        servo_inst.load_configuration(config_path, subnode=axis)
        self.logger.info(
            "Configuration loaded from %s", config_path, drive=self.mc.servo_name(servo)
        )

    def save_configuration(
        self, output_file: str, axis: Optional[int] = None, servo: str = DEFAULT_SERVO
    ) -> None:
        """Save the servo configuration to a target file.

        Args:
            output_file : servo configuration destination file.
            axis : target axis to load configuration.
                If ``None`` function loads all axis. ``None`` by default.
            servo : servo alias to reference it. ``default`` by default.

        """
        servo_inst = self.mc.servos[servo]
        servo_inst.save_configuration(output_file, subnode=axis)
        self.logger.info("Configuration saved to %s", output_file, drive=self.mc.servo_name(servo))

    def store_configuration(self, axis: Optional[int] = None, servo: str = DEFAULT_SERVO) -> None:
        """Store servo configuration to non-volatile memory.

        Args:
            axis : target axis to load configuration.
                If ``None`` function loads all axis. ``None`` by default.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.store_parameters(axis)
        self.logger.info("Configuration stored", drive=self.mc.servo_name(servo))

    def restore_configuration(self, axis: Optional[int] = None, servo: str = DEFAULT_SERVO) -> None:
        """Restore servo to default configuration.

        Args:
            axis : target axis to load configuration.
                If ``None`` function loads all axis. ``None`` by default.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.restore_parameters(axis)
        self.logger.info("Configuration restored", drive=self.mc.servo_name(servo))

    def set_max_acceleration(
        self, acceleration: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Update maximum acceleration register.

        .. warning::
            This function is deprecated. Please use
            "set_max_profile_acceleration" or "set_profiler" instead.

        Args:
            acceleration : maximum acceleration in rev/s^2.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If acceleration is not a float.

        """
        self.logger.warning(
            '"set_max_acceleration" is deprecated. '
            'Please use "set_max_profile_acceleration" or '
            '"set_profiler".'
        )
        self.mc.communication.set_register(
            self.PROFILE_MAX_ACCELERATION_REGISTER, acceleration, servo=servo, axis=axis
        )
        self.logger.debug(
            "Max acceleration set to %s", acceleration, axis=axis, drive=self.mc.servo_name(servo)
        )

    def set_max_profile_acceleration(
        self, acceleration: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Update maximum profile acceleration register.

        Args:
            acceleration: maximum profile acceleration in rev/s^2.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.PROFILE_MAX_ACCELERATION_REGISTER, acceleration, servo=servo, axis=axis
        )
        self.logger.debug(
            "Max profile acceleration set to %s",
            acceleration,
            axis=axis,
            drive=self.mc.servo_name(servo),
        )

    def set_max_profile_deceleration(
        self, deceleration: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Update maximum profile deceleration register.

        Args:
            deceleration: maximum profile deceleration in rev/s^2.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.PROFILE_MAX_DECELERATION_REGISTER, deceleration, servo=servo, axis=axis
        )
        self.logger.debug(
            "Max profile deceleration set to %s",
            deceleration,
            axis=axis,
            drive=self.mc.servo_name(servo),
        )

    def set_profiler(
        self,
        acceleration: Optional[float] = None,
        deceleration: Optional[float] = None,
        velocity: Optional[float] = None,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Set up the acceleration, deceleration and velocity profilers.
        All of these parameters are optional, meaning the user can set only one
        if desired. However, At least a minimum of one of these parameters
        is mandatory to call this function.

        Raises:
            TypeError: Missing arguments. All the arguments given were None.

        Args:
            acceleration: maximum acceleration in rev/s^2.
            deceleration: maximum deceleration in rev/s^2.
            velocity: maximum profile velocity in rev/s.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
        """
        if acceleration is None and deceleration is None and velocity is None:
            raise TypeError("Missing arguments. At least one argument is required.")

        if acceleration is not None:
            self.set_max_profile_acceleration(acceleration, servo=servo, axis=axis)

        if deceleration is not None:
            self.set_max_profile_deceleration(deceleration, servo=servo, axis=axis)

        if velocity is not None:
            self.set_max_profile_velocity(velocity, servo=servo, axis=axis)

    def set_max_velocity(
        self, velocity: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Update maximum velocity register.

        Args:
            velocity: maximum velocity in rev/s.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If velocity is not a float.

        """
        self.mc.communication.set_register(
            self.MAX_VELOCITY_REGISTER, velocity, servo=servo, axis=axis
        )
        self.logger.debug(
            "Max velocity set to %s", velocity, axis=axis, drive=self.mc.servo_name(servo)
        )

    def set_max_profile_velocity(
        self, velocity: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Update maximum profile velocity register.

        Args:
            velocity: maximum profile velocity in rev/s.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.PROFILE_MAX_VELOCITY_REGISTER, velocity, servo=servo, axis=axis
        )
        self.logger.debug(
            "Max profile velocity set to %s", velocity, axis=axis, drive=self.mc.servo_name(servo)
        )

    def get_position_and_velocity_loop_rate(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Get position & velocity loop rate frequency.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            Position & velocity loop rate frequency in Hz.

        """
        return self.mc.communication.get_register(
            self.POSITION_AND_VELOCITY_LOOP_RATE_REGISTER, servo=servo, axis=axis
        )

    def get_current_loop_rate(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """Get current loop rate frequency.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            Current loop rate frequency in Hz.
        """
        return self.mc.communication.get_register(
            self.CURRENT_LOOP_RATE_REGISTER, servo=servo, axis=axis
        )

    def get_power_stage_frequency(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS, raw: bool = False
    ) -> int:
        """Get Power stage frequency register.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            raw : if ``False`` return frequency in Hz, if ``True``
                return raw register value. ``False`` by default.

        Returns:
            Frequency in Hz if raw is ``False``, else, raw register value.

        Raises:
            ValueError: If power stage frequency selection register has an
                invalid value.
        """
        pow_stg_freq = self.mc.communication.get_register(
            self.POWER_STAGE_FREQUENCY_SELECTION_REGISTER, servo=servo, axis=axis
        )
        if raw:
            return pow_stg_freq
        try:
            pow_stg_freq_reg = self.POWER_STAGE_FREQUENCY_REGISTERS[pow_stg_freq]
        except IndexError:
            raise ValueError("Invalid power stage frequency register")
        freq = self.mc.communication.get_register(pow_stg_freq_reg, servo=servo, axis=axis)
        return freq

    def get_power_stage_frequency_enum(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> IntEnum:
        """Return Power stage frequency register enum.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            IntEnum: Enum with power stage frequency available values.

        """
        return self.mc.get_register_enum(self.POWER_STAGE_FREQUENCY_SELECTION_REGISTER, servo, axis)

    @MCMetaClass.check_motor_disabled
    def set_power_stage_frequency(
        self, value: int, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set power stage frequency from enum value.
        See :func: `get_power_stage_frequency_enum`.

        Args:
            value : Enum value to set power stage frequency.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.

        """
        self.mc.communication.set_register(
            self.POWER_STAGE_FREQUENCY_SELECTION_REGISTER, value, servo=servo, axis=axis
        )

    def get_status_word(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """Return status word register value.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            Status word.

        """
        return self.mc.communication.get_register(self.STATUS_WORD_REGISTER, servo, axis)

    def is_motor_enabled(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> bool:
        """Return motor status.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            ``True`` if motor is enabled, else ``False``.

        """
        status_word = self.mc.configuration.get_status_word(servo=servo, axis=axis)
        return bool(status_word & self.STATUS_WORD_OPERATION_ENABLED_BIT)

    def is_commutation_feedback_aligned(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> bool:
        """Return commutation feedback aligned status.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            ``True`` if commutation feedback is aligned, else ``False``.

        """
        status_word = self.mc.configuration.get_status_word(servo=servo, axis=axis)
        return bool(status_word & self.STATUS_WORD_COMMUTATION_FEEDBACK_ALIGNED_BIT)

    def set_phasing_mode(
        self, phasing_mode: PhasingMode, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set phasing mode.

        Args:
            phasing_mode : phasing mode.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        """
        self.mc.communication.set_register(self.PHASING_MODE_REGISTER, phasing_mode, servo, axis)

    def get_phasing_mode(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> PhasingMode:
        """
        Get current phasing mode.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            PhasingMode: Phasing mode value.

        """
        phasing_mode = self.mc.communication.get_register(self.PHASING_MODE_REGISTER, servo, axis)
        try:
            return PhasingMode(phasing_mode)
        except ValueError:
            return phasing_mode

    def set_generator_mode(
        self, mode: GeneratorMode, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """
        Set generator mode.

        Args:
            mode : generator mode value.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        """
        self.mc.communication.set_register(self.GENERATOR_MODE_REGISTER, mode, servo, axis)

    def set_motor_pair_poles(
        self, pair_poles: int, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """
        Set motor pair poles.

        Args:
            pair_poles : motor pair poles-
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If pair poles is not an int.
            ingenialink.exceptions.ILValueError: If pair poles is less than 0.

        """
        self.mc.communication.set_register(
            self.MOTOR_POLE_PAIRS_REGISTER, pair_poles, servo=servo, axis=axis
        )

    def get_motor_pair_poles(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """
        Get motor pair poles.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            Pair poles value.

        """
        return self.mc.communication.get_register(
            self.MOTOR_POLE_PAIRS_REGISTER, servo=servo, axis=axis
        )

    def get_sto_status(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """
        Get STO register

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            STO register value.

        """
        return self.mc.communication.get_register(self.STO_STATUS_REGISTER, servo=servo, axis=axis)

    def is_sto1_active(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """
        Get STO1 bit from STO register

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            return value of STO1 bit.

        """
        if self.get_sto_status(servo, axis) & self.STO1_ACTIVE_BIT:
            return 1
        else:
            return 0

    def is_sto2_active(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """
        Get STO2 bit from STO register

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            return value of STO2 bit.

        """
        if self.get_sto_status(servo, axis) & self.STO2_ACTIVE_BIT:
            return 1
        else:
            return 0

    def check_sto_power_supply(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """
        Get power supply bit from STO register

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            return value of power supply bit.

        """
        if self.get_sto_status(servo, axis) & self.STO_SUPPLY_FAULT_BIT:
            return 1
        else:
            return 0

    def check_sto_abnormal_fault(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """
        Get abnormal fault bit from STO register

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            return value of abnormal fault bit.

        """
        if self.get_sto_status(servo, axis) & self.STO_ABNORMAL_FAULT_BIT:
            return 1
        else:
            return 0

    def get_sto_report_bit(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """
        Get report bit from STO register

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            return value of report bit.

        """
        if self.get_sto_status(servo, axis) & self.STO_REPORT_BIT:
            return 1
        else:
            return 0

    def is_sto_active(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> bool:
        """
        Check if STO is active

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            ``True`` if STO is active, else ``False``.

        """
        return self.get_sto_status(servo, axis) == self.STO_ACTIVE_STATE

    def is_sto_inactive(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> bool:
        """
        Check if STO is inactive

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            ``True`` if STO is inactive, else ``False``.

        """
        return self.get_sto_status(servo, axis) == self.STO_INACTIVE_STATE

    def is_sto_abnormal_latched(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> bool:
        """
        Check if STO is abnormal latched

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            ``True`` if STO is abnormal latched, else ``False``.

        """
        return self.get_sto_status(servo, axis) == self.STO_LATCHED_STATE

    def change_tcp_ip_parameters(
        self, ip_address: str, subnet_mask: str, gateway: str, servo: str = DEFAULT_SERVO
    ) -> None:
        """Change TCP IP parameters and store it.

        Args:
            ip_address : IP Address to be changed.
            subnet_mask : Subnet mask to be changed.
            gateway : Gateway to be changed.
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.change_tcp_ip_parameters(ip_address, subnet_mask, gateway)

    def store_tcp_ip_parameters(self, servo: str = DEFAULT_SERVO) -> None:
        """Store TCP IP parameters to non-volatile memory.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.store_tcp_ip_parameters()

    def restore_tcp_ip_parameters(self, servo: str = DEFAULT_SERVO) -> None:
        """Restore TCP IP parameters to default values.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        drive.restore_tcp_ip_parameters()

    def get_drive_info_coco_moco(
        self, alias: str
    ) -> tuple[list[Optional[int]], list[Optional[int]], list[Optional[str]], list[Optional[int]]]:
        """Get info from COCO and MOCO registers.

        Args:
            alias: Servo alias.

        Returns:
            Product codes (COCO, MOCO).
            Revision numbers (COCO, MOCO).
            FW versions (COCO, MOCO).
            Serial numbers (COCO, MOCO).

        """
        prod_codes: list[Optional[int]] = [None, None]
        rev_numbers: list[Optional[int]] = [None, None]
        fw_versions: list[Optional[str]] = [None, None]
        serial_number: list[Optional[int]] = [None, None]

        for subnode in [0, 1]:
            # Product codes
            try:
                prod_codes[subnode] = self.get_product_code(alias, subnode)
            except (
                ILError,
                IMException,
            ) as e:
                self.logger.error(e)
            # Revision numbers
            try:
                rev_numbers[subnode] = self.get_revision_number(alias, subnode)
            except (ILError, IMException) as e:
                self.logger.error(e)
            # FW versions
            try:
                fw_versions[subnode] = self.get_fw_version(alias, subnode)
            except (ILError, IMException) as e:
                self.logger.error(e)
            # Serial numbers
            try:
                serial_number[subnode] = self.get_serial_number(alias, subnode)
            except (ILError, IMException) as e:
                self.logger.error(e)

        return prod_codes, rev_numbers, fw_versions, serial_number

    def get_drive_info(self, alias: str) -> tuple[int, int, str, int]:
        """Get info from MOCO if it is available or from COCO if it is not.

        Args:
            alias: Servo alias.
            force_reading: If True, cleans the cache before reading the drive.

        Returns:
            Product code.
            Revision number.
            FW version.
            Serial number.
        """
        prod_codes, rev_numbers, fw_versions, serial_numbers = self.get_drive_info_coco_moco(alias)

        prod_code = prod_codes[1] or prod_codes[0] or 0

        rev_number = rev_numbers[1] or rev_numbers[0] or 0

        fw_version = fw_versions[1] or fw_versions[0] or "-"
        fw_version = "_" + ".".join(fw_version.split(".")[:4])

        serial_number = serial_numbers[1] or serial_numbers[0] or 0

        return prod_code, rev_number, fw_version, serial_number

    @staticmethod
    def get_subnode_type(subnode: int) -> TYPE_SUBNODES:
        """Get a subnode type depending on the axis number.

        Args:
            subnode: Axis number of the drive.

        Returns:
            Subnode type.

        Raises:
            ValueError: For negative subnode values.
        """
        if subnode < 0:
            raise ValueError("There are no subnodes with negative values")
        return TYPE_SUBNODES.COCO if subnode == 0 else TYPE_SUBNODES.MOCO

    def get_product_code(self, alias: str, subnode: int) -> int:
        """Get the product code of a drive.

        Args:
            alias: Alias of the drive.
            subnode: Axis number of the drive.

        Returns:
            Product code
        """
        product_code_register = self.PRODUCT_ID_REGISTERS[self.get_subnode_type(subnode)]
        return self.mc.communication.get_register(product_code_register, alias, axis=subnode)

    def get_revision_number(self, alias: str, subnode: int) -> int:
        """Get the revision number of a drive.

        Args:
            alias: Alias of the drive.
            subnode: Axis number of the drive.

        Returns:
            Revision number
        """
        revision_number_register = self.REVISION_NUMBER_REGISTERS[self.get_subnode_type(subnode)]
        return self.mc.communication.get_register(revision_number_register, alias, axis=subnode)

    def get_serial_number(self, alias: str, subnode: int) -> int:
        """Get the serial number of a drive.

        Args:
            alias: Alias of the drive.
            subnode: Axis number of the drive.

        Returns:
            Serial number
        """
        serial_number_register = self.SERIAL_NUMBER_REGISTERS[self.get_subnode_type(subnode)]
        return self.mc.communication.get_register(serial_number_register, alias, axis=subnode)

    def get_fw_version(self, alias: str, subnode: int) -> str:
        """Get the firmware version of a drive.

        Args:
            alias: Alias of the drive.
            subnode: Axis number of the drive.

        Returns:
            Firmware version.
        """
        fw_register = self.SOFTWARE_VERSION_REGISTERS[self.get_subnode_type(subnode)]
        return self.mc.communication.get_register(fw_register, alias, axis=subnode)

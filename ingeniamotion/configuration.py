from enum import IntEnum
from os import path
from typing import TYPE_CHECKING, List, Optional, Tuple, Union

import ingenialogger
from ingenialink.canopen.network import CAN_BAUDRATE, CanopenNetwork
from ingenialink.ethernet.servo import EthernetServo
from ingenialink.exceptions import ILError

from ingeniamotion.enums import (
    CommutationMode,
    FilterNumber,
    FilterSignal,
    FilterType,
    GeneratorMode,
    PhasingMode,
)
from ingeniamotion.exceptions import IMException
from ingeniamotion.feedbacks import Feedbacks
from ingeniamotion.homing import Homing
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO, MCMetaClass

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


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
    VELOCITY_LOOP_KP_REGISTER = "CL_VEL_PID_KP"
    VELOCITY_LOOP_KI_REGISTER = "CL_VEL_PID_KI"
    VELOCITY_LOOP_KD_REGISTER = "CL_VEL_PID_KD"
    POSITION_LOOP_KP_REGISTER = "CL_POS_PID_KP"
    POSITION_LOOP_KI_REGISTER = "CL_POS_PID_KI"
    POSITION_LOOP_KD_REGISTER = "CL_POS_PID_KD"
    RATED_CURRENT_REGISTER = "MOT_RATED_CURRENT"
    MAX_CURRENT_REGISTER = "CL_CUR_REF_MAX"
    COMMUTATION_MODE_REGISTER = "MOT_COMMU_MOD"
    BUS_VOLTAGE_REGISTER = "DRV_PROT_VBUS_VALUE"
    POSITION_TO_VELOCITY_RATIO_REGISTER = "PROF_POS_VEL_RATIO"
    FILTER_TYPE_REGISTER = "CL_{}_FILTER{}_TYPE"
    FILTER_FREQ_REGISTER = "CL_{}_FILTER{}_FREQ"
    FILTER_Q_REGISTER = "CL_{}_FILTER{}_Q"
    FILTER_GAIN_REGISTER = "CL_{}_FILTER{}_GAIN"

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
    VENDOR_ID_COCO_REGISTER = "DRV_ID_VENDOR_ID_COCO"
    VENDOR_ID_REGISTER = "DRV_ID_VENDOR_ID"

    def __init__(self, motion_controller: "MotionController") -> None:
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

        Args:
            acceleration: maximum acceleration in rev/s^2.
            deceleration: maximum deceleration in rev/s^2.
            velocity: maximum profile velocity in rev/s.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: Missing arguments. All the arguments given were None.

        """
        if acceleration is None and deceleration is None and velocity is None:
            raise TypeError("Missing arguments. At least one argument is required.")

        if acceleration is not None:
            self.set_max_profile_acceleration(acceleration, servo=servo, axis=axis)

        if deceleration is not None:
            self.set_max_profile_deceleration(deceleration, servo=servo, axis=axis)

        if velocity is not None:
            self.set_max_profile_velocity(velocity, servo=servo, axis=axis)

    def get_max_velocity(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> float:
        """Get the maximum velocity.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            Max velocity.

        Raises:
            TypeError: If the read value has the wrong type.

        """
        max_velocity = self.mc.communication.get_register(
            self.MAX_VELOCITY_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(max_velocity, float):
            raise TypeError("Max velocity value has to be a float")
        return max_velocity

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

        Raises:
            TypeError: If some read value has a wrong type.

        """
        pos_vel_loop_rate = self.mc.communication.get_register(
            self.POSITION_AND_VELOCITY_LOOP_RATE_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(pos_vel_loop_rate, int):
            raise TypeError("Position and velocity loop has to be an integer")
        return pos_vel_loop_rate

    def get_current_loop_rate(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """Get current loop rate frequency.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            Current loop rate frequency in Hz.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        current_loop = self.mc.communication.get_register(
            self.CURRENT_LOOP_RATE_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(current_loop, int):
            raise TypeError("Current loop value has to be an integer")
        return current_loop

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
            TypeError: If some read value has a wrong type.

        """
        pow_stg_freq = self.mc.communication.get_register(
            self.POWER_STAGE_FREQUENCY_SELECTION_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(pow_stg_freq, int):
            raise TypeError("Power stage frequency value has to be an integer")
        if raw:
            return pow_stg_freq
        try:
            pow_stg_freq_reg = self.POWER_STAGE_FREQUENCY_REGISTERS[pow_stg_freq]
        except IndexError:
            raise ValueError("Invalid power stage frequency register")
        freq = self.mc.communication.get_register(pow_stg_freq_reg, servo=servo, axis=axis)
        if not isinstance(freq, int):
            raise TypeError("Frequency value has to be an integer")
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

        Raises:
            TypeError: If some read value has a wrong type.

        """
        status_word = self.mc.communication.get_register(self.STATUS_WORD_REGISTER, servo, axis)
        if not isinstance(status_word, int):
            raise TypeError("Power stage frequency value has to be an integer")
        return status_word

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

    def get_phasing_mode(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Union[PhasingMode, int]:
        """
        Get current phasing mode.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            Phasing mode value.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        phasing_mode = self.mc.communication.get_register(self.PHASING_MODE_REGISTER, servo, axis)
        if not isinstance(phasing_mode, int):
            raise TypeError("Phasing mode value has to be an integer")
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

        Raises:
            TypeError: If some read value has a wrong type.
        """
        pair_poles = self.mc.communication.get_register(
            self.MOTOR_POLE_PAIRS_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(pair_poles, int):
            raise TypeError("Pair poles value has to be an integer")
        return pair_poles

    def get_sto_status(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """
        Get STO register

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            STO register value.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        sto_status = self.mc.communication.get_register(
            self.STO_STATUS_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(sto_status, int):
            raise TypeError("STO status value has to be an integer")
        return sto_status

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
        if not isinstance(drive, EthernetServo):
            raise IMException("TCP IP parameters can only be changed in ethernet servos.")
        drive.change_tcp_ip_parameters(ip_address, subnet_mask, gateway)

    def store_tcp_ip_parameters(self, servo: str = DEFAULT_SERVO) -> None:
        """Store TCP IP parameters to non-volatile memory.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        if not isinstance(drive, EthernetServo):
            raise IMException("TCP IP parameters can only be stored in ethernet servos.")
        drive.store_tcp_ip_parameters()

    def restore_tcp_ip_parameters(self, servo: str = DEFAULT_SERVO) -> None:
        """Restore TCP IP parameters to default values.

        Args:
            servo : servo alias to reference it. ``default`` by default.

        """
        drive = self.mc._get_drive(servo)
        if not isinstance(drive, EthernetServo):
            raise IMException("TCP IP parameters can only be restored in ethernet servos.")
        drive.restore_tcp_ip_parameters()

    def get_drive_info_coco_moco(
        self, alias: str
    ) -> Tuple[List[Optional[int]], List[Optional[int]], List[Optional[str]], List[Optional[int]]]:
        """Get product codes, revision numbers, firmware versions and serial numbers from
        COCO and MOCO.

        Args:
            alias: Servo alias.

        Returns:
            Product codes (COCO, MOCO).
            Revision numbers (COCO, MOCO).
            FW versions (COCO, MOCO).
            Serial numbers (COCO, MOCO).

        """
        prod_codes: List[Optional[int]] = [None, None]
        rev_numbers: List[Optional[int]] = [None, None]
        fw_versions: List[Optional[str]] = [None, None]
        serial_number: List[Optional[int]] = [None, None]

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

        Raises:
            TypeError: If some read value has a wrong type.
        """
        product_code_register = self.PRODUCT_ID_REGISTERS[self.get_subnode_type(subnode)]
        product_code_value = self.mc.communication.get_register(
            product_code_register, alias, axis=subnode
        )
        if not isinstance(product_code_value, int):
            raise TypeError("Product code value has to be an integer")
        return product_code_value

    def get_revision_number(self, alias: str, subnode: int) -> int:
        """Get the revision number of a drive.

        Args:
            alias: Alias of the drive.
            subnode: Axis number of the drive.

        Returns:
            Revision number

        Raises:
            TypeError: If some read value has a wrong type.
        """
        revision_number_register = self.REVISION_NUMBER_REGISTERS[self.get_subnode_type(subnode)]
        revision_number_value = self.mc.communication.get_register(
            revision_number_register, alias, axis=subnode
        )
        if not isinstance(revision_number_value, int):
            raise TypeError("Revision number value has to be an integer")
        return revision_number_value

    def get_serial_number(self, alias: str, subnode: int) -> int:
        """Get the serial number of a drive.

        Args:
            alias: Alias of the drive.
            subnode: Axis number of the drive.

        Returns:
            Serial number

        Raises:
            TypeError: If some read value has a wrong type.
        """
        serial_number_register = self.SERIAL_NUMBER_REGISTERS[self.get_subnode_type(subnode)]
        serial_number_value = self.mc.communication.get_register(
            serial_number_register, alias, axis=subnode
        )
        if not isinstance(serial_number_value, int):
            raise TypeError("Serial number value has to be an integer")
        return serial_number_value

    def get_fw_version(self, alias: str, subnode: int) -> str:
        """Get the firmware version of a drive.

        Args:
            alias: Alias of the drive.
            subnode: Axis number of the drive.

        Returns:
            Firmware version.

        Raises:
            TypeError: If some read value has a wrong type.
        """
        fw_register = self.SOFTWARE_VERSION_REGISTERS[self.get_subnode_type(subnode)]
        fw_value = self.mc.communication.get_register(fw_register, alias, axis=subnode)
        if not isinstance(fw_value, str):
            raise TypeError("Firmware value has to be a string")
        return fw_value

    def get_vendor_id(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """Get the vendor ID of a drive.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            Vendor ID.

        Raises:
            TypeError: If the read vendor ID has the wrong type.

        """
        if axis == 0:
            register = self.VENDOR_ID_COCO_REGISTER
        else:
            register = self.VENDOR_ID_REGISTER
        vendor_id = self.mc.communication.get_register(register, servo, axis)
        if not isinstance(vendor_id, int):
            raise TypeError(
                f"Wrong {register} value for axis {axis}. Expected int, got {type(vendor_id)}"
            )
        return vendor_id

    def change_baudrate(self, baud_rate: CAN_BAUDRATE, servo: str = DEFAULT_SERVO) -> None:
        """Change a CANopen device's baudrate.

        Args:
            baud_rate: New baud rate value.
            servo : servo alias to reference it. ``default`` by default.

        Raises:
            ValueError: If the servo is not a CANopen device.

        """
        drive = self.mc._get_drive(servo)
        net = self.mc._get_network(servo)
        if not isinstance(net, CanopenNetwork):
            raise ValueError(f"Servo {servo} is not a CANopen device.")
        vendor_id = self.get_vendor_id(servo)
        prod_code = self.get_product_code(servo, subnode=0)
        rev_number = self.get_revision_number(servo, subnode=0)
        serial_number = self.get_serial_number(servo, subnode=0)
        net.change_baudrate(
            int(drive.target), baud_rate, vendor_id, prod_code, rev_number, serial_number
        )

    def change_node_id(self, node_id: int, servo: str = DEFAULT_SERVO) -> None:
        """Change a CANopen device's node ID.

        Args:
            node_id: New node ID.
            servo : servo alias to reference it. ``default`` by default.

        Raises:
            ValueError: If servo is not a CANopen device.

        """
        drive = self.mc._get_drive(servo)
        net = self.mc._get_network(servo)
        if not isinstance(net, CanopenNetwork):
            raise ValueError(f"Servo {servo} is not a CANopen device.")
        vendor_id = self.get_vendor_id(servo)
        prod_code = self.get_product_code(servo, subnode=0)
        rev_number = self.get_revision_number(servo, subnode=0)
        serial_number = self.get_serial_number(servo, subnode=0)
        net.change_node_id(
            int(drive.target), node_id, vendor_id, prod_code, rev_number, serial_number
        )

    def set_velocity_pid(
        self,
        kp: float,
        ki: float = 0,
        kd: float = 0,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Set velocity PID values in the target servo and axis.

        Args:
            kp: proportional constant
            ki: integral constant
            kd: derivative constant
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        """
        self.mc.communication.set_register(
            self.VELOCITY_LOOP_KP_REGISTER, kp, servo=servo, axis=axis
        )
        self.mc.communication.set_register(
            self.VELOCITY_LOOP_KI_REGISTER, ki, servo=servo, axis=axis
        )
        self.mc.communication.set_register(
            self.VELOCITY_LOOP_KD_REGISTER, kd, servo=servo, axis=axis
        )

    def set_position_pid(
        self,
        kp: float,
        ki: float = 0,
        kd: float = 0,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Set position PID values in the target servo and axis.

        Args:
            kp: proportional constant
            ki: integral constant
            kd: derivative constant
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        """
        self.mc.communication.set_register(
            self.POSITION_LOOP_KP_REGISTER, kp, servo=servo, axis=axis
        )
        self.mc.communication.set_register(
            self.POSITION_LOOP_KI_REGISTER, ki, servo=servo, axis=axis
        )
        self.mc.communication.set_register(
            self.POSITION_LOOP_KD_REGISTER, kd, servo=servo, axis=axis
        )

    def get_rated_current(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> float:
        """Get rated current in the target servo and axis.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        Returns:
            Rated current

        Raises:
            TypeError: If some read value has a wrong type.

        """
        rated_current = self.mc.communication.get_register(
            self.RATED_CURRENT_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(rated_current, float):
            raise TypeError(
                f"Wrong {self.RATED_CURRENT_REGISTER} value for axis {axis}. "
                f"Expected int, got {type(rated_current)}"
            )
        return rated_current

    def set_rated_current(
        self, rated_current: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set rated current in the target servo and axis.

        Args:
            rated_current: target rated current.
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        """
        self.mc.communication.set_register(
            self.RATED_CURRENT_REGISTER, rated_current, servo=servo, axis=axis
        )

    def get_max_current(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> float:
        """Get max current in the target servo and axis.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        Returns:
            Max current

        Raises:
            TypeError: If some read value has a wrong type.

        """
        max_current = self.mc.communication.get_register(
            self.MAX_CURRENT_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(max_current, float):
            raise TypeError(
                f"Wrong {self.MAX_CURRENT_REGISTER} value for axis {axis}. "
                f"Expected int, got {type(max_current)}"
            )
        return max_current

    def get_commutation_mode(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> CommutationMode:
        """Get commutation mode in the target servo and axis.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        Returns:
            Commutation mode.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        commutation_mode = self.mc.communication.get_register(
            self.COMMUTATION_MODE_REGISTER, servo, axis
        )
        if not isinstance(commutation_mode, int):
            raise TypeError("Commutation mode value has to be an integer")

        return CommutationMode(commutation_mode)

    def set_commutation_mode(
        self,
        commutation_mode: CommutationMode,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Set commutation mode in the target servo and axis.

        Args:
            rated_current: target commutation mode.
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        """
        self.mc.communication.set_register(
            self.COMMUTATION_MODE_REGISTER, commutation_mode, servo, axis
        )

    def get_bus_voltage(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> float:
        """Get Bus voltage.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        Returns:
            Bus voltage.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        bus_voltage = self.mc.communication.get_register(self.BUS_VOLTAGE_REGISTER, servo, axis)
        if not isinstance(bus_voltage, float):
            raise TypeError("Bus voltage value has to be a float")

        return bus_voltage

    def get_pos_to_vel_ratio(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> float:
        """Get the position-to-velocity ratio.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        Returns:
            Position-to-velocity ratio.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        pos_to_vel_ratio = self.mc.communication.get_register(
            self.POSITION_TO_VELOCITY_RATIO_REGISTER, servo, axis
        )
        if not isinstance(pos_to_vel_ratio, float):
            raise TypeError("Position-to-velocity ratio value has to be a float")

        return pos_to_vel_ratio

    def set_pos_to_vel_ratio(
        self, pos_to_vel_ratio: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set the position-to-velocity ratio.

        Args:
            pos_to_vel_ratio: position-to-velocity ratio.
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        """
        self.mc.communication.set_register(
            self.POSITION_TO_VELOCITY_RATIO_REGISTER, pos_to_vel_ratio, servo, axis
        )

    def configure_filter(
        self,
        signal: FilterSignal,
        number: FilterNumber,
        filter_type: Optional[FilterType] = None,
        frequency: Optional[int] = None,
        q_factor: Optional[float] = None,
        gain: Optional[float] = None,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Configure a filter.

        Args:
            signal: Signal to be filtered.
            number: Filter number (1 or 2).
            filter_type: Filter type.
            frequency: Cut-off frequency.
            q_factor: Q factor.
            gain: Filter gain.
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.
        """
        arguments = [filter_type, frequency, q_factor, gain]
        registers = [
            self.FILTER_TYPE_REGISTER,
            self.FILTER_FREQ_REGISTER,
            self.FILTER_Q_REGISTER,
            self.FILTER_GAIN_REGISTER,
        ]
        for value, reg_template in zip(arguments, registers):
            if value is None:
                continue
            register = reg_template.format(signal.value, number.value)
            self.mc.communication.set_register(register, value, servo, axis)

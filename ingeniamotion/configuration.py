import re
import ingenialogger

from os import path
from enum import IntEnum

from .homing import Homing
from .feedbacks import Feedbacks


class Configuration(Homing, Feedbacks):
    """Configuration.
    """

    class BrakeOverride(IntEnum):
        """
        Brake override configuration enum
        """
        OVERRIDE_DISABLED = 0
        RELEASE_BRAKE = 1
        ENABLE_BRAKE = 2

    BRAKE_OVERRIDE_REGISTER = "MOT_BRAKE_OVERRIDE"
    PROFILE_MAX_ACCELERATION_REGISTER = "PROF_MAX_ACC"
    PROFILE_MAX_VELOCITY_REGISTER = "PROF_MAX_VEL"
    POWER_STAGE_FREQUENCY_REGISTER = "DRV_PS_FREQ_SELECTION"
    POSITION_AND_VELOCITY_LOOP_RATE_REGISTER = "DRV_POS_VEL_RATE"
    STATUS_WORD_REGISTER = "DRV_STATE_STATUS"

    def __init__(self, motion_controller):
        Homing.__init__(self, motion_controller)
        Feedbacks.__init__(self, motion_controller)
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def release_brake(self, servo="default", axis=1):
        """
        Override the brake status to released in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. 1 by default.
        """
        self.mc.check_servo(servo)
        self.mc.communication.set_register(
            self.BRAKE_OVERRIDE_REGISTER,
            self.BrakeOverride.RELEASE_BRAKE,
            servo=servo,
            axis=axis
        )

    def enable_brake(self, servo="default", axis=1):
        """
        Override the brake status of the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. 1 by default.
        """
        self.mc.check_servo(servo)
        self.mc.communication.set_register(
            self.BRAKE_OVERRIDE_REGISTER,
            self.BrakeOverride.ENABLE_BRAKE,
            servo=servo,
            axis=axis
        )

    def disable_brake_override(self, servo="default", axis=1):
        """
        Disable the brake override of the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. 1 by default.
        """
        self.mc.check_servo(servo)
        self.mc.communication.set_register(
            self.BRAKE_OVERRIDE_REGISTER,
            self.BrakeOverride.OVERRIDE_DISABLED,
            servo=servo,
            axis=axis
        )

    def default_brake(self, servo="default", axis=1):
        """
        Disable the brake override of the target servo and axis, as :func:`disable_brake_override`.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): axis that will run the test. 1 by default.
        """
        self.disable_brake_override(servo, axis)

    def load_configuration(self, config_path, servo="default"):
        """
        Load a configuration file to the target servo.

        Args:
            config_path (str): config file path to load.
            servo (str): servo alias to reference it. ``default`` by default.
        """
        if not path.isfile(config_path):
            raise FileNotFoundError("{} file does not exist!".format(config_path))
        servo_inst = self.mc.servos[servo]
        servo_inst.dict_storage_write(config_path)
        self.logger.info("Configuration loaded from %s", config_path,
                         drive=self.mc.servo_name(servo))

    def save_configuration(self, output_file, servo="default"):
        """
        Save the servo configuration to a target file.

        Args:
            output_file (str): servo configuration destination file.
            servo (str): servo alias to reference it. ``default`` by default.
        """
        servo_inst = self.mc.servos[servo]
        servo_inst.dict_storage_read(output_file)
        self.logger.info("Configuration saved to %s", output_file,
                         drive=self.mc.servo_name(servo))

    def set_max_acceleration(self, acceleration, servo="default", axis=1):
        """

        Args:
            acceleration: maximum acceleration in rev/s^2.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.PROFILE_MAX_ACCELERATION_REGISTER,
            acceleration,
            servo=servo,
            axis=axis
        )
        self.logger.debug("Max acceleration set to %s", acceleration,
                          axis=axis, drive=self.mc.servo_name(servo))

    def set_max_velocity(self, velocity, servo="default", axis=1):
        """

        Args:
            velocity: maximum velocity in rev/s.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.PROFILE_MAX_VELOCITY_REGISTER,
            velocity,
            servo=servo,
            axis=axis
        )
        self.logger.debug("Max velocity set to %s", velocity,
                          axis=axis, drive=self.mc.servo_name(servo))

    def get_position_and_velocity_loop_rate(self, servo="default", axis=1):
        """
        Get position & velocity loop rate frequency.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            int: Position & velocity loop rate frequency in Hz.
        """
        return self.mc.communication.get_register(
            self.POSITION_AND_VELOCITY_LOOP_RATE_REGISTER,
            servo=servo,
            axis=axis
        )

    def get_power_stage_frequency(self, servo="default", axis=1, raw=False):
        """
        Get Power stage frequency register.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            raw (bool): if ``False`` return frequency in Hz, if ``True`` return raw register value.
                ```False`` by default.

        Returns:
            int: Frequency in Hz if raw is ``False``, else, raw register value.
        """
        pow_stg_freq = self.mc.communication.get_register(
            self.POWER_STAGE_FREQUENCY_REGISTER,
            servo=servo,
            axis=axis
        )
        if raw:
            return pow_stg_freq
        pow_stg_freq_enum = self.mc.get_register_enum(self.POWER_STAGE_FREQUENCY_REGISTER, servo, axis)
        freq_label = pow_stg_freq_enum(pow_stg_freq).name
        match = re.match(r"(\d+) (\w+)", freq_label)
        value, unit = match.groups()
        if unit == "MHz":
            return int(value)*1000000
        if unit == "kHz":
            return int(value)*1000
        return int(value)

    def get_power_stage_frequency_enum(self, servo="default", axis=1):
        """
        Return Power stage frequency register enum.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            IntEnum: Enum with power stage frequency available values.

        """
        return self.mc.get_register_enum(self.POWER_STAGE_FREQUENCY_REGISTER, servo, axis)

    def set_power_stage_frequency(self, value, servo="default", axis=1):
        """
        Set power stage frequency from enum value. See :func: `get_power_stage_frequency_enum`.

        Args:
            value (int): Enum value to set power stage frequency.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.POWER_STAGE_FREQUENCY_REGISTER,
            value,
            servo=servo,
            axis=axis
        )

    def get_status_word(self, servo="default", axis=1):
        return self.mc.communication.get_register(self.STATUS_WORD_REGISTER, servo, axis)

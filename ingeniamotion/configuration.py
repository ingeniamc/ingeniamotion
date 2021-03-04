from os import path
from enum import IntEnum


class Configuration:
    """Configuration.
    """

    class BrakeOverride(IntEnum):
        """
        Brake override configuration enum
        """
        OVERRIDE_DISABLED = 0
        RELEASE_BRAKE = 1
        ENABLE_BRAKE = 2

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def release_brake(self, servo="default", subnode=1):
        """
        Override the brake status to released in the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            subnode (int): axis that will run the test. 1 by default.
        """
        self.mc.check_servo(servo)
        servo = self.mc.servos[servo]
        servo.raw_write(
            "MOT_BRAKE_OVERRIDE",
            self.BrakeOverride.RELEASE_BRAKE,
            subnode=subnode
        )

    def enable_brake(self, servo="default", subnode=1):
        """
        Override the brake status of the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            subnode (int): axis that will run the test. 1 by default.
        """
        self.mc.check_servo(servo)
        servo = self.mc.servos[servo]
        servo.raw_write(
            "MOT_BRAKE_OVERRIDE",
            self.BrakeOverride.ENABLE_BRAKE,
            subnode=subnode
        )

    def disable_brake_override(self, servo="default", subnode=1):
        """
        Disable the brake override of the target servo and axis.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            subnode (int): axis that will run the test. 1 by default.
        """
        self.mc.check_servo(servo)
        servo = self.mc.servos[servo]
        servo.raw_write(
            "MOT_BRAKE_OVERRIDE",
            self.BrakeOverride.OVERRIDE_DISABLED,
            subnode=subnode
        )

    def default_brake(self, servo="default", subnode=1):
        """
        Disable the brake override of the target servo and axis, as :func:`disable_brake_override`.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            subnode (int): axis that will run the test. 1 by default.
        """
        self.disable_brake_override(servo, subnode)

    def load_configuration(self, config_path, servo="default"):
        """
        Load a configuration file to the target servo.

        Args:
            config_path (str): config file path to load.
            servo (str): servo alias to reference it. ``default`` by default.
        """
        if not path.isfile(config_path):
            raise FileNotFoundError("{} file not exist!".format(config_path))
        servo_inst = self.mc.servos[servo]
        servo_inst.dict_load(config_path)
        servo_inst.dict_storage_write()

    def save_configuration(self, output_file, servo="default"):
        """
        Save the servo configuration to a target file.

        Args:
            output_file (str): servo configuration destination file.
            servo (str): servo alias to reference it. ``default`` by default.
        """
        servo_inst = self.mc.servos[servo]
        servo_inst.dict_storage_read()
        servo_dict = servo_inst.dict
        servo_dict.save(output_file)

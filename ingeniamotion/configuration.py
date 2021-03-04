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

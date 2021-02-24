from enum import IntEnum


class Configuration(object):
    """Commissioning.

    Parameters:
        
    Returns:
        
    """

    class BrakeOverride(IntEnum):
        OVERRIDE_DISABLED = 0
        RELEASE_BRAKE = 1
        ENABLE_BRAKE = 2

    def __init__(self, mc):
        self.mc = mc

    def release_brake(self, servo="default", subnode=1):
        self.mc.check_servo(servo)
        servo = self.mc.servos[servo]
        servo.raw_write(
            "MOT_BRAKE_OVERRIDE",
            self.BrakeOverride.RELEASE_BRAKE,
            subnode=subnode
        )

    def enable_brake(self, servo="default", subnode=1):
        self.mc.check_servo(servo)
        servo = self.mc.servos[servo]
        servo.raw_write(
            "MOT_BRAKE_OVERRIDE",
            self.BrakeOverride.ENABLE_BRAKE,
            subnode=subnode
        )

    def disable_brake_override(self, servo="default", subnode=1):
        self.mc.check_servo(servo)
        servo = self.mc.servos[servo]
        servo.raw_write(
            "MOT_BRAKE_OVERRIDE",
            self.BrakeOverride.OVERRIDE_DISABLED,
            subnode=subnode
        )

    def default_brake(self, servo="default", subnode=1):
        self.disable_brake_override(servo, subnode)

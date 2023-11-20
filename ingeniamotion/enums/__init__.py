from enum import IntEnum


class OperationMode(IntEnum):
    """Operation Mode Enum"""

    VOLTAGE = 0x00
    CURRENT_AMPLIFIER = 0x01
    CURRENT = 0x02
    CYCLIC_CURRENT = 0x22
    VELOCITY = 0x03
    PROFILE_VELOCITY = 0x13
    CYCLIC_VELOCITY = 0x23
    POSITION = 0x04
    PROFILE_POSITION = 0x14
    CYCLIC_POSITION = 0x24
    PROFILE_POSITION_S_CURVE = 0x44
    INTERPOLATED_POSITION = 0xA4
    PVT = 0xB4
    HOMING = 0x113
    TORQUE = 0x05
    CYCLIC_TORQUE = 0x25


class Protocol(IntEnum):
    """Communication protocol"""

    TCP = 1
    UDP = 2


class HomingMode(IntEnum):
    """Homing modes"""

    CURRENT_POSITION = 0
    POSITIVE_LIMIT_SWITCH = 1
    NEGATIVE_LIMIT_SWITCH = 2
    POSITIVE_IDX_PULSE = 3
    NEGATIVE_IDX_PULSE = 4
    POSITIVE_LIMIT_SWITCH_IDX_PULSE = 5
    NEGATIVE_LIMIT_SWITCH_IDX_PULSE = 6


class MonitoringSoCType(IntEnum):
    """Monitoring start of condition type"""

    TRIGGER_EVENT_AUTO = 0
    """No trigger"""
    TRIGGER_EVENT_FORCED = 1
    """Forced trigger"""
    TRIGGER_EVENT_EDGE = 2
    """Edge trigger"""


class MonitoringSoCConfig(IntEnum):
    TRIGGER_CONFIG_RISING_OR_FALLING = 0
    """Rising or falling edge trigger"""
    TRIGGER_CONFIG_RISING = 1
    """Rising edge trigger"""
    TRIGGER_CONFIG_FALLING = 2
    """Falling edge trigger"""


class MonitoringProcessStage(IntEnum):
    """Monitoring process stage"""

    INIT_STAGE = 0x0
    """Init stage"""
    FILLING_DELAY_DATA = 0x2
    """Filling delay data"""
    WAITING_FOR_TRIGGER = 0x4
    """Waiting for trigger"""
    DATA_ACQUISITION = 0x6
    """Data acquisition"""
    END_STAGE = 0x8
    """End stage"""


class SensorType(IntEnum):
    """Summit series feedback type enum"""

    ABS1 = 1
    """Absolute encoder 1"""
    INTGEN = 3
    """Internal generator"""
    QEI = 4
    """Digital/Incremental encoder 1"""
    HALLS = 5
    """Digital halls"""
    SSI2 = 6
    """Secondary SSI"""
    BISSC2 = 7
    """Absolute encoder 2"""
    QEI2 = 8
    """Digital/Incremental encoder 2"""


class SensorCategory(IntEnum):
    """Feedback category enum"""

    ABSOLUTE = 0
    INCREMENTAL = 1


class PhasingMode(IntEnum):
    """Phasing modes"""

    NON_FORCED = 0
    """Non forced"""
    FORCED = 1
    """Forced"""
    NO_PHASING = 2
    """No phasing"""


class GeneratorMode(IntEnum):
    """Generator modes"""

    CONSTANT = 0
    """Constant"""
    SAW_TOOTH = 1
    """Saw tooth"""
    SQUARE = 2
    """Square"""


class MonitoringVersion(IntEnum):
    """Monitoring version"""

    MONITORING_V1 = 0
    """Monitoring V1 used for Everest 1.8.1 and older."""
    MONITORING_V2 = 1
    """Monitoring V2 used for Capitan and some custom low-power drivers."""
    MONITORING_V3 = 2
    """Monitoring V3 used for Everest and Capitan newer than 1.8.1."""


class SeverityLevel(IntEnum):
    """Test result enum"""

    SUCCESS = 0
    WARNING = 1
    FAIL = 2


class COMMUNICATION_TYPE(IntEnum):
    Canopen = 0
    Ethernet = 1
    Ethercat = 2


class FeedbackPolarity(IntEnum):
    """Feedback polarity enum"""

    NORMAL = 0
    REVERSED = 1


enums = list(globals().keys())
enums.remove("IntEnum")
__all__ = enums

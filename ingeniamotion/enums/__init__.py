from enum import Enum, IntEnum
from typing import Type, TypeVar

from ingenialink.canopen.network import CAN_BAUDRATE, CAN_DEVICE
from ingenialink.enums.register import REG_ACCESS, REG_DTYPE

T = TypeVar("T", bound=Type[Enum])

__all__ = ["CAN_BAUDRATE", "CAN_DEVICE", "REG_ACCESS", "REG_DTYPE"]


def export(obj: T) -> T:
    """Decorator use to explicitly export a class"""
    __all__.append(obj.__name__)
    return obj


@export
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


@export
class Protocol(IntEnum):
    """Communication protocol"""

    TCP = 1
    UDP = 2


@export
class HomingMode(IntEnum):
    """Homing modes"""

    CURRENT_POSITION = 0
    POSITIVE_LIMIT_SWITCH = 1
    NEGATIVE_LIMIT_SWITCH = 2
    POSITIVE_IDX_PULSE = 3
    NEGATIVE_IDX_PULSE = 4
    POSITIVE_LIMIT_SWITCH_IDX_PULSE = 5
    NEGATIVE_LIMIT_SWITCH_IDX_PULSE = 6


@export
class MonitoringSoCType(IntEnum):
    """Monitoring start of condition type"""

    TRIGGER_EVENT_AUTO = 0
    """No trigger"""
    TRIGGER_EVENT_FORCED = 1
    """Forced trigger"""
    TRIGGER_EVENT_EDGE = 2
    """Edge trigger"""


@export
class MonitoringSoCConfig(IntEnum):
    TRIGGER_CONFIG_RISING_OR_FALLING = 0
    """Rising or falling edge trigger"""
    TRIGGER_CONFIG_RISING = 1
    """Rising edge trigger"""
    TRIGGER_CONFIG_FALLING = 2
    """Falling edge trigger"""


@export
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


@export
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


@export
class SensorCategory(IntEnum):
    """Feedback category enum"""

    ABSOLUTE = 0
    INCREMENTAL = 1


@export
class PhasingMode(IntEnum):
    """Phasing modes"""

    NON_FORCED = 0
    """Non forced"""
    FORCED = 1
    """Forced"""
    NO_PHASING = 2
    """No phasing"""


@export
class GeneratorMode(IntEnum):
    """Generator modes"""

    CONSTANT = 0
    """Constant"""
    SAW_TOOTH = 1
    """Saw tooth"""
    SQUARE = 2
    """Square"""


@export
class MonitoringVersion(IntEnum):
    """Monitoring version"""

    MONITORING_V1 = 0
    """Monitoring V1 used for Everest 1.8.1 and older."""
    MONITORING_V2 = 1
    """Monitoring V2 used for Capitan and some custom low-power drivers."""
    MONITORING_V3 = 2
    """Monitoring V3 used for Everest and Capitan newer than 1.8.1."""


@export
class SeverityLevel(IntEnum):
    """Test result enum"""

    SUCCESS = 0
    WARNING = 1
    FAIL = 2


@export
class COMMUNICATION_TYPE(IntEnum):
    Canopen = 0
    Ethernet = 1
    Ethercat = 2


@export
class FeedbackPolarity(IntEnum):
    """Feedback polarity enum"""

    NORMAL = 0
    REVERSED = 1


@export
class CommutationMode(IntEnum):
    """Commutation Mode Enum"""

    SINUSOIDAL = 0
    TRAPEZOIDAL = 1
    SINGLE_PHASE = 2


@export
class FilterType(IntEnum):
    """
    Biquad filter type.
    """

    DISABLED = 0
    """ Filter disabled """
    LOWPASS = 1
    """ Low-pass filter """
    HIGHPASS = 2
    """ High-pass filter """
    BANDPASS = 3
    """ Band-pass filter """
    PEAK = 4
    """ Peak filter """
    NOTCH = 5
    """ Notch filter """
    LOWSHELF = 6
    """ Low Shelf filter """
    HIGHSHELF = 7
    """ High Shelf filter """


@export
class FilterSignal(Enum):
    """Signal to configure filter."""

    POSITION_FEEDBACK = "POS_FBK"
    """Position feedback."""
    POSITION_REFERENCE = "POS_REF"
    """Position reference."""
    VELOCITY_FEEDBACK = "VEL_FBK"
    """Velocity feedback."""
    VELOCITY_REFERENCE = "VEL_REF"
    """Velocity reference."""
    CURRENT_FEEDBACK = "CUR_FBK"
    """Current feedback."""
    CURRENT_REFERENCE = "CUR_REF"
    """Current reference."""


@export
class FilterNumber(IntEnum):
    """Filter number (1 or 2)."""

    FILTER1 = 1
    FILTER2 = 2


@export
class DigitalVoltageLevel(IntEnum):
    """GPIOs voltage level (HIGH/LOW) enum"""

    HIGH = 1
    LOW = 0


@export
class GPIOPolarity(IntEnum):
    """GPIOs polarity enum"""

    NORMAL = 0
    REVERSED = 1


@export
class GPI(IntEnum):
    """GPIs identifier enum"""

    GPI1 = 1
    GPI2 = 2
    GPI3 = 3
    GPI4 = 4


@export
class GPO(IntEnum):
    """GPOs identifier enum"""

    GPO1 = 1
    GPO2 = 2
    GPO3 = 3
    GPO4 = 4


@export
class FSoEState(IntEnum):
    """FSoE Master Handler state"""

    RESET = 0
    SESSION = 1
    CONNECTION = 2
    PARAMETER = 3
    DATA = 4

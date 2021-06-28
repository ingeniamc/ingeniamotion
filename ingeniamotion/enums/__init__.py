from enum import IntEnum


class OperationMode(IntEnum):
    """
    Operation Mode Enum
    """
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
    CYCLIC_POSITION_S_CURVE = 0x44
    PVT = 0xB4
    HOMING = 0x113


class Protocol(IntEnum):
    """
    Communication protocol
    """
    TCP = 1
    UDP = 2


class HomingMode(IntEnum):
    """
    Homing modes
    """
    CURRENT_POSITION = 0
    POSITIVE_LIMIT_SWITCH = 1
    NEGATIVE_LIMIT_SWITCH = 2
    POSITIVE_IDX_PULSE = 3
    NEGATIVE_IDX_PULSE = 4
    POSITIVE_LIMIT_SWITCH_IDX_PULSE = 5
    NEGATIVE_LIMIT_SWITCH_IDX_PULSE = 6


class MonitoringSoCType(IntEnum):
    """
    Monitoring start of condition type
    """
    TRIGGER_EVENT_NONE = 0
    """ No trigger """
    TRIGGER_EVENT_FORCED = 1
    """ Forced trigger """
    TRIGGER_CYCLIC_RISING_EDGE = 2
    """ Rising edge trigger """
    TRIGGER_NUMBER_SAMPLES = 3
    TRIGGER_CYCLIC_FALLING_EDGE = 4
    """ Falling edge trigger """


class MonitoringProcessStage(IntEnum):
    """
    Monitoring process stage
    """
    INIT_STAGE = 0x0
    """ Init stage """
    FILLING_DELAY_DATA = 0x2
    """ Filling delay data """
    WAITING_FOR_TRIGGER = 0x4
    """ Waiting for trigger """
    DATA_ACQUISITION = 0x6
    """ Data acquisition """


class SensorType(IntEnum):
    """
    Summit series feedback type enum
    """
    ABS1 = 1
    """ Absolute encoder 1 """
    INTGEN = 3
    """ Internal generator """
    QEI = 4
    """ Digital/Incremental encoder 1 """
    HALLS = 5
    """ Digital halls """
    SSI2 = 6
    """ Secondary SSI """
    BISSC2 = 7
    """ Absolute encoder 2 """
    QEI2 = 8
    """ Digital/Incremental encoder 2 """
    SMO = 9
    """ SMO """


class PhasingMode(IntEnum):
    """
    Phasing modes
    """
    NON_FORCED = 0
    """ Non forced """
    FORCED = 1
    """ Forced """
    NO_PHASING = 2
    """ No phasing """


class GeneratorMode(IntEnum):
    """
    Generator modes
    """
    CONSTANT = 0
    """ Constant """
    SAW_TOOTH = 1
    """ Saw tooth """
    SQUARE = 2
    """ Square """

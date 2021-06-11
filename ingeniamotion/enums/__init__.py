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

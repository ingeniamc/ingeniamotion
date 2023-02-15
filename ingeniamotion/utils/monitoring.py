from typing import Union

from ingenialink.ethernet.register import EthernetRegister
from ingenialink.canopen.register import CanopenRegister


def map_register_address(register: Union[EthernetRegister, CanopenRegister]) -> int:
    """
    Map register address in order to use it in a monitoring/disturbance process.

    Args:
        register: Register to be mapped.

    Returns:
        Mapped register address.

    """
    reg_map_offset = 0x800
    address_offset = reg_map_offset * (register.subnode - 1)
    return (
        register.address + address_offset
        if isinstance(register, EthernetRegister)
        else register.idx
    )

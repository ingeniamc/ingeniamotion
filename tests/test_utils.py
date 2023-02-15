import pytest

from ingenialink.ethernet.register import EthernetRegister, REG_DTYPE, REG_ACCESS
from ingenialink.canopen.register import CanopenRegister

from ingeniamotion.utils.monitoring import map_register_address


@pytest.mark.parametrize(
    "subnode, address, mapped_address_eth, mapped_address_can",
    [
        (1, 0x0010, 0x0010, 0x0010),
        (2, 0x0020, 0x0820, 0x0020),
        (3, 0x0030, 0x1030, 0x0030),
    ],
)
def test_map_register_address(subnode, address, mapped_address_eth, mapped_address_can):
    ethernet_param_dict = {
        'subnode': subnode,
        'address': address,
        'dtype': REG_DTYPE.U16,
        'access': REG_ACCESS.RW
    }
    canopen_param_dict = {
        'subnode': subnode,
        'idx': address,
        'subidx': 0x00,
        'dtype': REG_DTYPE.U16,
        'access': REG_ACCESS.RW,
        'identifier': '',
        'units': '',
        'cyclic': 'CONFIG'
    }
    register = EthernetRegister(**ethernet_param_dict)
    assert mapped_address_eth == map_register_address(register)
    register = CanopenRegister(**canopen_param_dict)
    assert mapped_address_can == map_register_address(register)

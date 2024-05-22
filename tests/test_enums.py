import pytest


@pytest.mark.virtual
def test_import_ingenialink_enums():
    from ingeniamotion.enums import CAN_BAUDRATE, CAN_DEVICE, REG_ACCESS, REG_DTYPE

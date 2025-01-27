import pytest


@pytest.mark.virtual
def test_import_ingenialink_enums():
    from ingeniamotion.enums import REG_ACCESS, REG_DTYPE, CanBaudrate, CanDevice  # noqa: F401

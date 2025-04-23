import pytest

from ingeniamotion.drive_context_manager import DriveContextManager


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_drive_context_manager(motion_controller):
    user_over_voltage_uid = "DRV_PROT_USER_OVER_VOLT"
    mc, alias, _ = motion_controller

    def _read_user_over_voltage_uid():
        return mc.communication.get_register(user_over_voltage_uid, servo=alias)

    context = DriveContextManager(motion_controller=mc, alias=alias)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid()
    assert previous_reg_value != new_reg_value

    with context:
        mc.communication.set_register(
            register=user_over_voltage_uid, value=new_reg_value, servo=alias
        )
        assert _read_user_over_voltage_uid() == new_reg_value

    assert _read_user_over_voltage_uid() == previous_reg_value

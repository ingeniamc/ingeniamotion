import pytest

from ingeniamotion.drive_context_manager import DriveContextManager

_USER_OVER_VOLTAGE_UID = "DRV_PROT_USER_OVER_VOLT"


def _read_user_over_voltage_uid(mc, alias):
    return mc.communication.get_register(_USER_OVER_VOLTAGE_UID, servo=alias)


@pytest.mark.smoke
@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_drive_context_manager(motion_controller):
    mc, alias, _ = motion_controller
    context = DriveContextManager(motion_controller=mc, alias=alias)

    new_reg_value = 100.0
    previous_reg_value = _read_user_over_voltage_uid(mc, alias)
    assert previous_reg_value != new_reg_value

    with context:
        mc.communication.set_register(
            register=_USER_OVER_VOLTAGE_UID, value=new_reg_value, servo=alias
        )
        assert _read_user_over_voltage_uid(mc, alias) == new_reg_value

    assert _read_user_over_voltage_uid(mc, alias) == previous_reg_value


class TestDriveContextFixture:
    original_value = None

    @pytest.mark.smoke
    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @pytest.mark.dependency(name="test_change_register_without_context")
    def test_change_register_without_context(self, motion_controller):
        mc, alias, _ = motion_controller
        new_reg_value = 100.0

        original_value = _read_user_over_voltage_uid(mc, alias)
        TestDriveContextFixture.original_value = original_value
        assert original_value != new_reg_value

        mc.communication.set_register(
            register=_USER_OVER_VOLTAGE_UID, value=new_reg_value, servo=alias
        )
        assert _read_user_over_voltage_uid(mc, alias) == new_reg_value

    @pytest.mark.smoke
    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @pytest.mark.dependency(
        name="test_read_register_if_changed_without_context",
        depends=["test_change_register_without_context"],
    )
    def test_read_register_if_changed_without_context(self, motion_controller):
        mc, alias, _ = motion_controller
        assert TestDriveContextFixture.original_value is not None
        # Drive context manager didn't restore the value
        assert _read_user_over_voltage_uid(mc, alias) != TestDriveContextFixture.original_value
        TestDriveContextFixture.original_value = None

    @pytest.mark.smoke
    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @pytest.mark.dependency(
        name="test_change_register_with_context",
        depends=["test_read_register_if_changed_without_context"],
    )
    def test_change_register_with_context(self, motion_controller, drive_context_manager):  # noqa: ARG002
        mc, alias, _ = motion_controller
        new_reg_value = 60.0

        assert TestDriveContextFixture.original_value is None
        original_value = _read_user_over_voltage_uid(mc, alias)
        TestDriveContextFixture.original_value = original_value
        assert original_value != new_reg_value

        mc.communication.set_register(
            register=_USER_OVER_VOLTAGE_UID, value=new_reg_value, servo=alias
        )
        assert _read_user_over_voltage_uid(mc, alias) == new_reg_value

    @pytest.mark.smoke
    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @pytest.mark.dependency(
        name="test_read_register_if_changed_with_context",
        depends=["test_change_register_with_context"],
    )
    def test_read_register_if_changed_with_context(self, motion_controller):
        mc, alias, _ = motion_controller
        assert TestDriveContextFixture.original_value is not None
        # Drive context manager restored the value, so it should be the original one
        assert _read_user_over_voltage_uid(mc, alias) == TestDriveContextFixture.original_value

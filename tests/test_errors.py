import pytest
from ingenialink.exceptions import ILError


@pytest.fixture
def error_number(motion_controller):
    mc, alias = motion_controller
    return mc.errors.get_number_total_errors(servo=alias)


@pytest.fixture
def generate_drive_errors(motion_controller):
    mc, alias = motion_controller
    errors_list = [
        {"code": 0x3241, "register": "DRV_PROT_USER_UNDER_VOLT", "value": 100},
        {"code": 0x4303, "register": "DRV_PROT_USER_OVER_TEMP", "value": 1},
        {"code": 0x3231, "register": "DRV_PROT_USER_OVER_VOLT", "value": 1},
        {"code": 0x4304, "register": "DRV_PROT_USER_UNDER_TEMP", "value": 200},
    ]
    error_code_list = []
    for item in errors_list:
        old_value = mc.communication.get_register(item["register"], servo=alias)
        mc.communication.set_register(item["register"], item["value"], servo=alias)
        try:
            mc.motion.motor_enable(servo=alias)
        except ILError:
            pass
        error_code_list.append(item["code"])
        mc.communication.set_register(item["register"], old_value, servo=alias)
    return error_code_list[::-1]


class TestErrors:

    @pytest.mark.smoke
    def test_get_last_error(self, motion_controller, generate_drive_errors):
        mc, alias = motion_controller
        last_error = mc.errors.get_last_error(servo=alias)
        assert last_error == generate_drive_errors[0]

    @pytest.mark.smoke
    def test_get_last_buffer_error(self, motion_controller, generate_drive_errors):
        mc, alias = motion_controller
        last_error = mc.errors.get_last_buffer_error(servo=alias)
        assert last_error == generate_drive_errors[0]

    @pytest.mark.smoke
    def test_get_buffer_error_by_index(self, motion_controller, generate_drive_errors):
        mc, alias = motion_controller
        index_list = [2, 1, 3, 0]
        for i in index_list:
            last_error = mc.errors.get_buffer_error_by_index(i, servo=alias)
            assert last_error == generate_drive_errors[i]

    @pytest.mark.smoke
    def test_get_number_total_errors(self, motion_controller, error_number,
                                     generate_drive_errors):
        mc, alias = motion_controller
        test_error_number = mc.errors.get_number_total_errors(servo=alias)
        assert test_error_number == error_number + len(generate_drive_errors)

    @pytest.mark.smoke
    def test_get_all_errors(self, motion_controller, generate_drive_errors):
        mc, alias = motion_controller
        test_all_errors = mc.errors.get_all_errors(servo=alias)
        for i, code_error in enumerate(generate_drive_errors):
            assert test_all_errors[i] == code_error

    @pytest.mark.smoke
    def test_is_fault_active(self, motion_controller, generate_drive_errors):
        mc, alias = motion_controller
        assert mc.errors.is_fault_active(servo=alias)

    @pytest.mark.smoke
    @pytest.mark.skip("Not implemented")
    def test_is_warning_active(self, motion_controller, generate_drive_errors):
        mc, alias = motion_controller

    @pytest.mark.smoke
    @pytest.mark.parametrize("error_code, affected_module, error_type, error_msg", [
        (0x3241, "Power stage", "Cyclic", "User Under-voltage detected"),
        (0x4303, "Power stage", "Cyclic", "Over-temperature detected (user limit)"),
        (0x3231, "Power stage", "Cyclic", "User Over-voltage detected"),
        (0x4304, "Power stage", "Cyclic", "Under-temperature detected (user limit)"),
    ])
    def test_get_error_data(self, motion_controller, error_code,
                            affected_module, error_type, error_msg):
        mc, alias = motion_controller
        test_id, test_aff_mod, test_type, test_msg = \
            mc.errors.get_error_data(error_code, servo=alias)
        assert error_code == int(test_id, base=16)
        assert test_aff_mod == affected_module
        assert test_type == error_type
        assert test_msg == error_msg

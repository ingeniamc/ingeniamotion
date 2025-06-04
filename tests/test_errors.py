import contextlib

import pytest
from ingenialink.exceptions import ILError

USER_UNDER_VOLTAGE_ERROR_OPTION_CODE_REGISTER = "ERROR_PROT_UNDER_VOLT_OPTION"
USER_UNDER_VOLTAGE_LEVEL_REGISTER = "DRV_PROT_USER_UNDER_VOLT"


@pytest.fixture
def error_number(mc, alias):
    return mc.errors.get_number_total_errors(servo=alias)


@pytest.fixture
def generate_drive_errors(mc, alias):
    errors_list = [
        {"code": 0x3241, "register": "DRV_PROT_USER_UNDER_VOLT", "value": 100},
        {"code": 0x4303, "register": "DRV_PROT_USER_OVER_TEMP", "value": 1},
        {"code": 0x3231, "register": "DRV_PROT_USER_OVER_VOLT", "value": 1},
        {"code": 0x4304, "register": "DRV_PROT_USER_UNDER_TEMP", "value": 200},
    ]
    error_code_list = []
    for item in errors_list:
        mc.motion.fault_reset(servo=alias)
        old_value = mc.communication.get_register(item["register"], servo=alias)
        mc.communication.set_register(item["register"], item["value"], servo=alias)
        with contextlib.suppress(ILError):
            mc.motion.motor_enable(servo=alias)
        error_code_list.append(item["code"])
        try:
            mc.communication.set_register(item["register"], old_value, servo=alias)
        except ILError:
            # Sometimes fails with EVE-XCR-E
            mc.communication.set_register(item["register"], old_value, servo=alias)
    yield error_code_list[::-1]
    mc.motion.fault_reset(servo=alias)


@pytest.fixture
def force_warning(mc, alias):
    mc.communication.set_register(USER_UNDER_VOLTAGE_ERROR_OPTION_CODE_REGISTER, 1, servo=alias)
    mc.communication.set_register(USER_UNDER_VOLTAGE_LEVEL_REGISTER, 100, servo=alias)
    mc.motion.motor_enable(servo=alias)
    yield
    mc.communication.set_register(USER_UNDER_VOLTAGE_ERROR_OPTION_CODE_REGISTER, 0, servo=alias)
    mc.communication.set_register(USER_UNDER_VOLTAGE_LEVEL_REGISTER, 10, servo=alias)


class TestErrors:
    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_get_last_error(self, mc, alias, generate_drive_errors):
        # Axis 1 needs to be selected due to a bug in EVE-XCR. For more info check INGM-376.
        last_error, subnode, warning = mc.errors.get_last_error(servo=alias, axis=1)
        assert last_error == generate_drive_errors[0]
        mc.motion.fault_reset(servo=alias)
        last_error, subnode, warning = mc.errors.get_last_error(servo=alias, axis=1)
        assert last_error == 0
        assert subnode is None
        assert warning is None

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_get_last_buffer_error(self, mc, alias, generate_drive_errors):
        last_error, subnode, warning = mc.errors.get_last_buffer_error(servo=alias)
        assert last_error == generate_drive_errors[0]

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_get_buffer_error_by_index(self, mc, alias, generate_drive_errors):
        index_list = [2, 1, 3, 0]
        for i in index_list:
            last_error, subnode, warning = mc.errors.get_buffer_error_by_index(
                i, servo=alias, axis=1
            )
            assert last_error == generate_drive_errors[i]

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @pytest.mark.usefixtures("generate_drive_errors")
    def test_get_buffer_error_by_index_exception(self, mc, alias):
        with pytest.raises(ValueError):
            mc.errors.get_buffer_error_by_index(33, servo=alias)

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_get_number_total_errors(self, mc, alias, error_number, generate_drive_errors):
        test_error_number = mc.errors.get_number_total_errors(servo=alias)
        assert test_error_number == error_number + len(generate_drive_errors)

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    def test_get_all_errors(self, mc, alias, generate_drive_errors):
        test_all_errors = mc.errors.get_all_errors(servo=alias, axis=1)
        for i, code_error in enumerate(generate_drive_errors):
            test_code_error, axis, warning = test_all_errors[i]
            assert test_code_error == code_error

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @pytest.mark.usefixtures("generate_drive_errors")
    def test_is_fault_active(self, mc, alias):
        assert mc.errors.is_fault_active(servo=alias)
        mc.motion.fault_reset(servo=alias)
        assert not mc.errors.is_fault_active(servo=alias)

    @pytest.mark.ethernet
    @pytest.mark.soem
    @pytest.mark.canopen
    @pytest.mark.usefixtures("force_warning")
    def test_is_warning_active(self, mc, alias):
        assert mc.errors.is_warning_active(servo=alias)
        mc.communication.set_register(USER_UNDER_VOLTAGE_LEVEL_REGISTER, 10, servo=alias)
        assert not mc.errors.is_warning_active(servo=alias)

    @pytest.mark.virtual
    @pytest.mark.parametrize(
        "error_code, affected_module, error_type, error_msg",
        [
            (0x3241, "Power stage", "Cyclic", "User Under-voltage detected"),
            (0x4303, "Power stage", "Cyclic", "Over-temperature detected (user limit)"),
            (0x3231, "Power stage", "Cyclic", "User Over-voltage detected"),
            (0x4304, "Power stage", "Cyclic", "Under-temperature detected (user limit)"),
        ],
    )
    def test_get_error_data(self, mc, alias, error_code, affected_module, error_type, error_msg):
        test_id, test_aff_mod, test_type, test_msg = mc.errors.get_error_data(
            error_code, servo=alias
        )
        assert error_code == int(test_id, base=16)
        assert test_aff_mod == affected_module
        assert test_type == error_type
        assert test_msg == error_msg

    @pytest.mark.parametrize(
        "function",
        [
            "get_last_error",
            "get_buffer_error_by_index",
            "get_number_total_errors",
        ],
    )
    @pytest.mark.virtual
    def test_wrong_type_exception(self, mocker, mc, alias, function):
        mocker.patch.object(mc.communication, "get_register", return_value="invalid_value")
        with pytest.raises(TypeError):
            getattr(mc.errors, function)(servo=alias)

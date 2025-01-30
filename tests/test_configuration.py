import os

import pytest
from ingenialink import CanBaudrate
from ingenialink.ethercat.servo import EthercatServo

from ingeniamotion.configuration import TYPE_SUBNODES, MACAddressConverter
from ingeniamotion.enums import (
    CommutationMode,
    FilterNumber,
    FilterSignal,
    FilterType,
)
from ingeniamotion.exceptions import IMException

BRAKE_OVERRIDE_REGISTER = "MOT_BRAKE_OVERRIDE"
POSITION_SET_POINT_REGISTER = "CL_POS_SET_POINT_VALUE"
PROFILE_MAX_ACCELERATION_REGISTER = "PROF_MAX_ACC"
PROFILE_MAX_DECELERATION_REGISTER = "PROF_MAX_DEC"
PROFILE_MAX_VELOCITY_REGISTER = "PROF_MAX_VEL"
MAX_VELOCITY_REGISTER = "CL_VEL_REF_MAX"
POWER_STAGE_FREQUENCY_SELECTION_REGISTER = "DRV_PS_FREQ_SELECTION"
POSITION_AND_VELOCITY_LOOP_RATE_REGISTER = "DRV_POS_VEL_RATE"
CURRENT_LOOP_RATE_REGISTER = "CL_CUR_FREQ"
STATUS_WORD_REGISTER = "DRV_STATE_STATUS"
PHASING_MODE_REGISTER = "COMMU_PHASING_MODE"
GENERATOR_MODE_REGISTER = "FBK_GEN_MODE"
MOTOR_POLE_PAIRS_REGISTER = "MOT_PAIR_POLES"
STO_STATUS_REGISTER = "DRV_PROT_STO_STATUS"
VELOCITY_LOOP_KP_REGISTER = "CL_VEL_PID_KP"
VELOCITY_LOOP_KI_REGISTER = "CL_VEL_PID_KI"
VELOCITY_LOOP_KD_REGISTER = "CL_VEL_PID_KD"
POSITION_LOOP_KP_REGISTER = "CL_POS_PID_KP"
POSITION_LOOP_KI_REGISTER = "CL_POS_PID_KI"
POSITION_LOOP_KD_REGISTER = "CL_POS_PID_KD"
RATED_CURRENT_REGISTER = "MOT_RATED_CURRENT"
MAX_CURRENT_REGISTER = "CL_CUR_REF_MAX"
COMMUTATION_MODE_REGISTER = "MOT_COMMU_MOD"
BUS_VOLTAGE_REGISTER = "DRV_PROT_VBUS_VALUE"
POSITION_TO_VELOCITY_RATIO_REGISTER = "PROF_POS_VEL_RATIO"
FILTER_TYPE_REGISTER = "CL_{}_FILTER{}_TYPE"
FILTER_FREQ_REGISTER = "CL_{}_FILTER{}_FREQ"
FILTER_Q_REGISTER = "CL_{}_FILTER{}_Q"
FILTER_GAIN_REGISTER = "CL_{}_FILTER{}_GAIN"


@pytest.fixture
def teardown_brake_override(motion_controller):
    yield
    mc, alias, environment = motion_controller
    mc.configuration.default_brake(servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
def test_release_brake(motion_controller, teardown_brake_override):
    mc, alias, environment = motion_controller
    mc.configuration.release_brake(servo=alias)
    assert (
        mc.communication.get_register(BRAKE_OVERRIDE_REGISTER, servo=alias, axis=1)
        == mc.configuration.BrakeOverride.RELEASE_BRAKE
    )


@pytest.mark.virtual
@pytest.mark.smoke
def test_enable_brake(motion_controller, teardown_brake_override):
    mc, alias, environment = motion_controller
    mc.configuration.enable_brake(servo=alias)
    assert (
        mc.communication.get_register(BRAKE_OVERRIDE_REGISTER, servo=alias, axis=1)
        == mc.configuration.BrakeOverride.ENABLE_BRAKE
    )


@pytest.mark.virtual
@pytest.mark.smoke
def test_disable_brake_override(motion_controller, teardown_brake_override):
    mc, alias, environment = motion_controller
    mc.configuration.disable_brake_override(servo=alias)
    assert (
        mc.communication.get_register(BRAKE_OVERRIDE_REGISTER, servo=alias, axis=1)
        == mc.configuration.BrakeOverride.OVERRIDE_DISABLED
    )


@pytest.fixture
def remove_file_if_exist():
    yield
    file_path = "test_file.xcf"
    if os.path.isfile(file_path):
        os.remove(file_path)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.usefixtures("remove_file_if_exist")
def test_save_configuration_and_load_configuration(motion_controller):
    file_path = "test_file.xcf"
    mc, alias, environment = motion_controller
    old_value = mc.communication.get_register(PROFILE_MAX_VELOCITY_REGISTER, servo=alias)
    mc.communication.set_register(PROFILE_MAX_VELOCITY_REGISTER, 10, servo=alias)
    mc.configuration.save_configuration(file_path, servo=alias)
    assert os.path.isfile(file_path)
    mc.communication.set_register(PROFILE_MAX_VELOCITY_REGISTER, 20, servo=alias)
    mc.configuration.load_configuration(file_path, servo=alias)
    assert mc.communication.get_register(PROFILE_MAX_VELOCITY_REGISTER, servo=alias) == 10
    mc.communication.set_register(PROFILE_MAX_VELOCITY_REGISTER, old_value, servo=alias)


@pytest.mark.usefixtures("remove_file_if_exist")
@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.smoke
def test_save_configuration_and_load_configuration_nvm_none(motion_controller):
    file_path = "test_file.xcf"
    mc, alias, environment = motion_controller
    old_value = mc.communication.get_register(POSITION_SET_POINT_REGISTER, servo=alias)
    mc.communication.set_register(POSITION_SET_POINT_REGISTER, 10, servo=alias)
    mc.configuration.save_configuration(file_path, servo=alias)
    assert os.path.isfile(file_path)
    mc.communication.set_register(POSITION_SET_POINT_REGISTER, 20, servo=alias)
    mc.configuration.load_configuration(file_path, servo=alias)
    assert mc.communication.get_register(POSITION_SET_POINT_REGISTER, servo=alias) == 20
    mc.communication.set_register(POSITION_SET_POINT_REGISTER, old_value, servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_profiler_exception(motion_controller):
    mc, alias, environment = motion_controller

    with pytest.raises(TypeError):
        mc.configuration.set_profiler(None, None, None, servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "acceleration, deceleration, velocity",
    [(0, 0, 0), (15, 20, 25), (1, None, None), (None, 1, None), (None, None, 1)],
)
def test_set_profiler(motion_controller, acceleration, deceleration, velocity):
    mc, alias, environment = motion_controller
    register_dict = {
        "acc": PROFILE_MAX_ACCELERATION_REGISTER,
        "dec": PROFILE_MAX_DECELERATION_REGISTER,
        "vel": PROFILE_MAX_VELOCITY_REGISTER,
    }
    expected_values = {"acc": acceleration, "dec": deceleration, "vel": velocity}
    for key in [key for key, value in expected_values.items() if value is None]:
        expected_value = mc.communication.get_register(register_dict[key], servo=alias)
        expected_values[key] = expected_value
    mc.configuration.set_profiler(acceleration, deceleration, velocity, servo=alias)
    for key in expected_values:
        actual_value = mc.communication.get_register(register_dict[key], servo=alias)
        assert pytest.approx(expected_values[key]) == actual_value


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("acceleration", [0, 10, 25])
def test_set_max_profile_acceleration(motion_controller, acceleration):
    mc, alias, environment = motion_controller
    mc.configuration.set_max_profile_acceleration(acceleration, servo=alias)
    output_value = mc.communication.get_register(PROFILE_MAX_ACCELERATION_REGISTER, servo=alias)
    assert pytest.approx(acceleration) == output_value


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("deceleration", [0, 10, 25])
def test_set_max_deceleration(motion_controller, deceleration):
    mc, alias, environment = motion_controller
    mc.configuration.set_max_profile_deceleration(deceleration, servo=alias)
    output_value = mc.communication.get_register(PROFILE_MAX_DECELERATION_REGISTER, servo=alias)
    assert pytest.approx(output_value) == deceleration


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("velocity", [0, 10, 25])
def test_set_max_velocity(motion_controller, velocity):
    mc, alias, environment = motion_controller
    mc.configuration.set_max_velocity(velocity, servo=alias)
    output_value = mc.communication.get_register(MAX_VELOCITY_REGISTER, servo=alias)
    assert pytest.approx(velocity) == output_value


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("velocity", [0, 10, 25])
def test_set_max_profile_velocity(motion_controller, velocity):
    mc, alias, environment = motion_controller
    mc.configuration.set_max_profile_velocity(velocity, servo=alias)
    output_value = mc.communication.get_register(PROFILE_MAX_VELOCITY_REGISTER, servo=alias)
    assert pytest.approx(velocity) == output_value


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_position_and_velocity_loop_rate(motion_controller):
    mc, alias, environment = motion_controller
    test_value = mc.configuration.get_position_and_velocity_loop_rate(servo=alias)
    reg_value = mc.communication.get_register(POSITION_AND_VELOCITY_LOOP_RATE_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_current_loop_rate(motion_controller):
    mc, alias, environment = motion_controller
    test_value = mc.configuration.get_current_loop_rate(servo=alias)
    reg_value = mc.communication.get_register(CURRENT_LOOP_RATE_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_power_stage_frequency(motion_controller):
    mc, alias, environment = motion_controller
    mc.configuration.get_power_stage_frequency(servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_power_stage_frequency_raw(motion_controller):
    mc, alias, environment = motion_controller
    test_value = mc.configuration.get_power_stage_frequency(servo=alias, raw=True)
    pow_stg_freq = mc.communication.get_register(
        POWER_STAGE_FREQUENCY_SELECTION_REGISTER, servo=alias
    )
    assert test_value == pow_stg_freq


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_power_stage_frequency_enum(motion_controller):
    mc, alias, environment = motion_controller
    mc.configuration.get_power_stage_frequency_enum(servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("input_value", [0, 1, 2, 3])
def test_set_power_stage_frequency(motion_controller_teardown, input_value):
    input_value = 0
    mc, alias, environment = motion_controller_teardown
    mc.configuration.set_power_stage_frequency(input_value, servo=alias)
    output_value = mc.communication.get_register(
        POWER_STAGE_FREQUENCY_SELECTION_REGISTER, servo=alias
    )
    assert pytest.approx(input_value) == output_value


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_power_stage_frequency_exception(mocker, motion_controller):
    mc, alias, environment = motion_controller
    mocker.patch("ingeniamotion.communication.Communication.get_register", return_value=5)
    with pytest.raises(ValueError):
        mc.configuration.get_power_stage_frequency(servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_status_word(motion_controller):
    mc, alias, environment = motion_controller
    test_value = mc.configuration.get_status_word(servo=alias)
    reg_value = mc.communication.get_register(STATUS_WORD_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
def test_is_motor_enabled_1(motion_controller):
    mc, alias, environment = motion_controller
    mc.motion.motor_disable(alias)
    assert not mc.configuration.is_motor_enabled(servo=alias)
    mc.motion.motor_enable(servo=alias)
    assert mc.configuration.is_motor_enabled(servo=alias)
    mc.motion.motor_disable(servo=alias)
    assert not mc.configuration.is_motor_enabled(servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "status_word_value, expected_result",
    [
        (0xF29C, True),
        (0xF440, False),
        (0xD1A7, True),
        (0x86D7, True),
        (0x2A43, False),
        (0x33E6, True),
    ],
)
def test_is_motor_enabled_2(mocker, motion_controller, status_word_value, expected_result):
    mc, alias, environment = motion_controller
    mocker.patch(
        "ingeniamotion.configuration.Configuration.get_status_word", return_value=status_word_value
    )
    test_value = mc.configuration.is_motor_enabled(servo=alias)
    assert test_value == expected_result


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "status_word_value, expected_result",
    [
        (0xF29C, True),
        (0xF440, True),
        (0xD1A7, True),
        (0x86D7, False),
        (0x2A43, False),
        (0x33E6, False),
    ],
)
def test_is_commutation_feedback_aligned(
    mocker, motion_controller, status_word_value, expected_result
):
    mc, alias, environment = motion_controller
    mocker.patch(
        "ingeniamotion.configuration.Configuration.get_status_word", return_value=status_word_value
    )
    test_value = mc.configuration.is_commutation_feedback_aligned(servo=alias)
    assert test_value == expected_result


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_phasing_mode(motion_controller):
    input_value = 0
    mc, alias, environment = motion_controller
    mc.configuration.set_phasing_mode(input_value, servo=alias)
    output_value = mc.communication.get_register(PHASING_MODE_REGISTER, servo=alias)
    assert pytest.approx(input_value) == output_value


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_phasing_mode(motion_controller):
    mc, alias, environment = motion_controller
    test_value = mc.configuration.get_phasing_mode(servo=alias)
    reg_value = mc.communication.get_register(PHASING_MODE_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_generator_mode(motion_controller):
    input_value = 0
    mc, alias, environment = motion_controller
    mc.configuration.set_generator_mode(input_value, servo=alias)
    output_value = mc.communication.get_register(GENERATOR_MODE_REGISTER, servo=alias)
    assert pytest.approx(input_value) == output_value


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_motor_pair_poles(motion_controller_teardown):
    input_value = 0
    mc, alias, environment = motion_controller_teardown
    mc.configuration.set_motor_pair_poles(input_value, servo=alias)
    output_value = mc.communication.get_register(MOTOR_POLE_PAIRS_REGISTER, servo=alias)
    assert pytest.approx(input_value) == output_value


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_motor_pair_poles(motion_controller):
    mc, alias, environment = motion_controller
    test_value = mc.configuration.get_motor_pair_poles(servo=alias)
    reg_value = mc.communication.get_register(MOTOR_POLE_PAIRS_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_sto_status(motion_controller):
    mc, alias, environment = motion_controller
    test_value = mc.configuration.get_sto_status(servo=alias)
    reg_value = mc.communication.get_register(STO_STATUS_REGISTER, servo=alias)
    assert test_value == reg_value


def patch_get_sto_status(mocker, value):
    mocker.patch("ingeniamotion.configuration.Configuration.get_sto_status", return_value=value)


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result",
    [
        (0x4843, False),
        (0xF567, False),
        (0xFFFF, False),
        (0x0000, True),
        (0x4766, True),
        (0xF6A4, True),
    ],
)
def test_is_sto1_active(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias, environment = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto1_active(servo=alias)
    assert value is expected_result


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result",
    [
        (0xA187, False),
        (0x31BA, False),
        (0xD7DD, True),
        (0xFB8, True),
        (0xA8DE, False),
        (0x99A5, True),
    ],
)
def test_is_sto2_active(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias, environment = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto2_active(servo=alias)
    assert value is expected_result


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result",
    [(0xFAC4, 1), (0x1AE1, 0), (0xD9CA, 0), (0xEE94, 1), (0xAE9F, 1), (0x478B, 0)],
)
def test_check_sto_power_supply(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias, environment = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.check_sto_power_supply(servo=alias)
    assert value == expected_result


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result",
    [
        (0x1BAF, True),
        (0xD363, False),
        (0xAD9D, True),
        (0x8D14, False),
        (0x9AEE, True),
        (0x94A7, False),
    ],
)
def test_is_sto_abnormal_fault(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias, environment = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto_abnormal_fault(servo=alias)
    assert value == expected_result


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result",
    [(0xF29C, 1), (0xF440, 0), (0xD1A7, 0), (0x86D7, 1), (0x2A43, 0), (0x33E6, 0)],
)
def test_get_sto_report_bit(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias, environment = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.get_sto_report_bit(servo=alias)
    assert value == expected_result


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result", [(0x13A0, False), (0x7648, False), (0x4, True)]
)
def test_is_sto_active(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias, environment = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto_active(servo=alias)
    assert value == expected_result


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result", [(0xC18A, False), (0x742C, False), (0x17, True)]
)
def test_is_sto_inactive(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias, environment = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto_inactive(servo=alias)
    assert value == expected_result


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result", [(0x1BF3, False), (0x6B7, False), (0x1F, True)]
)
def test_is_sto_abnormal_latched(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias, environment = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto_abnormal_latched(servo=alias)
    assert value == expected_result


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
def test_store_configuration(motion_controller):
    mc, alias, environment = motion_controller
    mc.configuration.store_configuration(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
def test_restore_configuration(motion_controller):
    mc, alias, environment = motion_controller
    mc.configuration.restore_configuration(servo=alias)


@pytest.mark.virtual
def test_get_drive_info_coco_moco(motion_controller):
    expected_product_codes = [123456, 123456]
    expected_revision_numbers = [654321, 654321]
    expected_firmware_versions = ["0.1.0", "0.1.0"]
    expected_serial_numbers = [123456789, 123456789]

    mc, alias, environment = motion_controller
    prod_codes, rev_nums, fw_vers, ser_nums = mc.configuration.get_drive_info_coco_moco(alias)

    assert prod_codes == expected_product_codes
    assert rev_nums == expected_revision_numbers
    assert fw_vers == expected_firmware_versions
    assert ser_nums == expected_serial_numbers


@pytest.mark.virtual
def test_get_product_code(motion_controller):
    expected_product_code_0 = 123456
    expected_product_code_1 = 123456

    mc, alias, environment = motion_controller
    product_code_0 = mc.configuration.get_product_code(alias, 0)
    product_code_1 = mc.configuration.get_product_code(alias, 1)

    assert product_code_0 == expected_product_code_0
    assert product_code_1 == expected_product_code_1


@pytest.mark.virtual
def test_get_revision_number(motion_controller):
    expected_revision_number_0 = 654321
    expected_revision_number_1 = 654321

    mc, alias, environment = motion_controller
    revision_number_0 = mc.configuration.get_revision_number(alias, 0)
    revision_number_1 = mc.configuration.get_revision_number(alias, 1)

    assert revision_number_0 == expected_revision_number_0
    assert revision_number_1 == expected_revision_number_1


@pytest.mark.virtual
def test_get_serial_number(motion_controller):
    expected_serial_number_0 = 123456789
    expected_serial_number_1 = 123456789

    mc, alias, environment = motion_controller
    serial_number_0 = mc.configuration.get_serial_number(alias, 0)
    serial_number_1 = mc.configuration.get_serial_number(alias, 1)

    assert serial_number_0 == expected_serial_number_0
    assert serial_number_1 == expected_serial_number_1


@pytest.mark.virtual
def test_get_fw_version(motion_controller):
    expected_fw_version_0 = "0.1.0"
    expected_fw_version_1 = "0.1.0"

    mc, alias, environment = motion_controller
    firmware_version_0 = mc.configuration.get_fw_version(alias, 0)
    firmware_version_1 = mc.configuration.get_fw_version(alias, 1)

    assert firmware_version_0 == expected_fw_version_0
    assert firmware_version_1 == expected_fw_version_1


@pytest.mark.virtual
def test_change_baudrate_exception(motion_controller):
    mc, alias, environment = motion_controller
    with pytest.raises(ValueError):
        mc.configuration.change_baudrate(CanBaudrate.Baudrate_1M, alias)


@pytest.mark.virtual
def test_get_vendor_id(motion_controller):
    expected_vendor_id_0 = 987654321
    expected_vendor_id_1 = 987654321

    mc, alias, environment = motion_controller
    vendor_id_0 = mc.configuration.get_vendor_id(alias, axis=0)
    vendor_id_1 = mc.configuration.get_vendor_id(alias, axis=1)

    assert vendor_id_0 == expected_vendor_id_0
    assert vendor_id_1 == expected_vendor_id_1


@pytest.mark.virtual
def test_change_node_id_exception(motion_controller):
    mc, alias, environment = motion_controller
    with pytest.raises(ValueError):
        mc.configuration.change_node_id(32, alias)


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_velocity_pid(motion_controller_teardown):
    mc, alias, environment = motion_controller_teardown
    kp_test = 1
    ki_test = 2
    kd_test = 3
    mc.configuration.set_velocity_pid(kp_test, ki_test, kd_test, servo=alias)
    kp_reg = mc.communication.get_register(VELOCITY_LOOP_KP_REGISTER, servo=alias)
    ki_reg = mc.communication.get_register(VELOCITY_LOOP_KI_REGISTER, servo=alias)
    kd_reg = mc.communication.get_register(VELOCITY_LOOP_KD_REGISTER, servo=alias)
    assert kp_test == kp_reg
    assert ki_test == ki_reg
    assert kd_test == kd_reg


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_position_pid(motion_controller_teardown):
    mc, alias, environment = motion_controller_teardown
    kp_test = 1
    ki_test = 2
    kd_test = 3
    mc.configuration.set_position_pid(kp_test, ki_test, kd_test, servo=alias)
    kp_reg = mc.communication.get_register(POSITION_LOOP_KP_REGISTER, servo=alias)
    ki_reg = mc.communication.get_register(POSITION_LOOP_KI_REGISTER, servo=alias)
    kd_reg = mc.communication.get_register(POSITION_LOOP_KD_REGISTER, servo=alias)
    assert kp_test == kp_reg
    assert ki_test == ki_reg
    assert kd_test == kd_reg


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_set_rated_current(motion_controller):
    mc, alias, environment = motion_controller
    initial_rated_current = mc.communication.get_register(RATED_CURRENT_REGISTER, servo=alias)
    read_rated_current = mc.configuration.get_rated_current(alias)
    assert pytest.approx(initial_rated_current) == read_rated_current
    test_rated_current = 1.23
    mc.configuration.set_rated_current(test_rated_current, servo=alias)
    read_test_rated_current = mc.communication.get_register(RATED_CURRENT_REGISTER, servo=alias)
    assert pytest.approx(test_rated_current) == read_test_rated_current
    # Teardown
    mc.communication.set_register(RATED_CURRENT_REGISTER, initial_rated_current, servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_max_current(motion_controller):
    mc, alias, environment = motion_controller
    real_max_current = mc.communication.get_register(MAX_CURRENT_REGISTER, servo=alias)
    test_max_current = mc.configuration.get_max_current(alias)
    assert pytest.approx(real_max_current) == test_max_current


@pytest.mark.virtual
def test_set_commutation_mode(motion_controller):
    input_value = CommutationMode.SINUSOIDAL
    mc, alias, environment = motion_controller
    mc.configuration.set_commutation_mode(input_value, servo=alias)
    output_value = mc.communication.get_register(COMMUTATION_MODE_REGISTER, servo=alias)
    assert pytest.approx(input_value) == output_value


@pytest.mark.virtual
def test_get_commutation_mode(motion_controller):
    mc, alias, environment = motion_controller
    test_value = mc.configuration.get_commutation_mode(servo=alias)
    reg_value = mc.communication.get_register(COMMUTATION_MODE_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.virtual
def test_get_bus_voltage(motion_controller):
    mc, alias, environment = motion_controller
    test_value = mc.configuration.get_bus_voltage(servo=alias)
    reg_value = mc.communication.get_register(BUS_VOLTAGE_REGISTER, servo=alias)
    assert pytest.approx(test_value) == reg_value


@pytest.mark.virtual
def test_set_pos_to_vel_ratio(motion_controller):
    input_value = 1.0
    mc, alias, environment = motion_controller
    mc.configuration.set_pos_to_vel_ratio(input_value, servo=alias)
    output_value = mc.communication.get_register(POSITION_TO_VELOCITY_RATIO_REGISTER, servo=alias)
    assert pytest.approx(input_value) == output_value


@pytest.mark.virtual
def test_get_pos_to_vel_ratio(motion_controller):
    mc, alias, environment = motion_controller
    test_value = mc.configuration.get_pos_to_vel_ratio(servo=alias)
    reg_value = mc.communication.get_register(POSITION_TO_VELOCITY_RATIO_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.virtual
@pytest.mark.parametrize("filter_type", [FilterType.LOWPASS, FilterType.HIGHPASS])
@pytest.mark.parametrize("filter_number", [FilterNumber.FILTER1, FilterNumber.FILTER2])
@pytest.mark.parametrize(
    "filter_signal", [FilterSignal.CURRENT_FEEDBACK, FilterSignal.VELOCITY_REFERENCE]
)
def test_configure_filter(motion_controller, filter_type, filter_number, filter_signal):
    mc, alias, environment = motion_controller
    frequency = 10
    q_factor = 1.3
    gain = 1.2
    mc.configuration.configure_filter(
        filter_signal,
        filter_number,
        filter_type=filter_type,
        frequency=frequency,
        q_factor=q_factor,
        gain=gain,
        servo=alias,
    )

    reg_type = FILTER_TYPE_REGISTER.format(filter_signal.value, filter_number.value)
    read_type = mc.communication.get_register(reg_type, servo=alias)
    assert pytest.approx(read_type) == filter_type

    reg_freq = FILTER_FREQ_REGISTER.format(filter_signal.value, filter_number.value)
    read_freq = mc.communication.get_register(reg_freq, servo=alias)
    assert pytest.approx(read_freq) == frequency

    reg_q_factor = FILTER_Q_REGISTER.format(filter_signal.value, filter_number.value)
    read_q_factor = mc.communication.get_register(reg_q_factor, servo=alias)
    assert pytest.approx(read_q_factor) == q_factor

    reg_gain = FILTER_GAIN_REGISTER.format(filter_signal.value, filter_number.value)
    read_gain = mc.communication.get_register(reg_gain, servo=alias)
    assert pytest.approx(read_gain) == gain


@pytest.mark.virtual
def test_load_configuration_file_not_found(motion_controller):
    file_path = "test_file.xcf"
    mc, alias, environment = motion_controller
    with pytest.raises(FileNotFoundError):
        mc.configuration.load_configuration(file_path, servo=alias)


@pytest.mark.parametrize(
    "function, wrong_value",
    [
        ("get_max_velocity", 1),
        ("get_position_and_velocity_loop_rate", 1.0),
        ("get_current_loop_rate", 1.0),
        ("get_power_stage_frequency", 1.0),
        ("get_status_word", 1.0),
        ("get_phasing_mode", 1.0),
        ("get_motor_pair_poles", 1.0),
        ("get_sto_status", 1.0),
        ("get_rated_current", 1),
        ("get_max_current", 1),
        ("get_commutation_mode", 1.0),
        ("get_bus_voltage", 1),
        ("get_pos_to_vel_ratio", 1),
    ],
)
@pytest.mark.virtual
def test_wrong_type_exception(mocker, motion_controller, function, wrong_value):
    mc, alias, environment = motion_controller
    mocker.patch.object(mc.communication, "get_register", return_value=wrong_value)
    with pytest.raises(TypeError):
        getattr(mc.configuration, function)(servo=alias)


@pytest.mark.virtual
def test_get_phasing_mode_invalid(mocker, motion_controller):
    mc, alias, environment = motion_controller
    invalid_enum_value = 8
    mocker.patch.object(mc.communication, "get_register", return_value=invalid_enum_value)
    phasing_mode = mc.configuration.get_phasing_mode(servo=alias)
    assert phasing_mode == invalid_enum_value


@pytest.mark.virtual
def test_change_tcp_ip_parameters_exception(mocker, motion_controller):
    mc, alias, environment = motion_controller
    mocker.patch.object(mc, "_get_drive", return_value=EthercatServo)
    with pytest.raises(IMException):
        mc.configuration.change_tcp_ip_parameters(
            "192.168.2.22", "255.255.0.0", "192.168.2.1", servo=alias
        )


@pytest.mark.parametrize(
    "function",
    [
        "store_tcp_ip_parameters",
        "restore_tcp_ip_parameters",
    ],
)
@pytest.mark.virtual
def test_store_restore_tcp_ip_parameters_exception(mocker, motion_controller, function):
    mc, alias, environment = motion_controller
    mocker.patch.object(mc, "_get_drive", return_value=EthercatServo)
    with pytest.raises(IMException):
        getattr(mc.configuration, function)(servo=alias)


@pytest.mark.parametrize(
    "subnode, expected_result",
    [
        (0, TYPE_SUBNODES.COCO),
        (1, TYPE_SUBNODES.MOCO),
    ],
)
@pytest.mark.virtual
def test_get_subnode_type(motion_controller, subnode, expected_result):
    mc, alias, environment = motion_controller
    assert mc.configuration.get_subnode_type(subnode) == expected_result


@pytest.mark.virtual
def test_get_subnode_type_exception(motion_controller):
    mc, alias, environment = motion_controller
    with pytest.raises(ValueError):
        mc.configuration.get_subnode_type(-1)


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "mac_address_str, mac_address_int",
    [
        ("49:4e:47:03:02:01", 80600547656193),
        ("02:01:05:40:03:e9", 2203406304233),
    ],
)
def test_mac_address_convertion(mac_address_str, mac_address_int):
    assert MACAddressConverter.str_to_int(mac_address_str) == mac_address_int
    assert MACAddressConverter.int_to_str(mac_address_int) == mac_address_str


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "invalid_mac_address",
    [
        "mac_address",
        "49-4e-47-03-02-01",
    ],
)
def test_mac_address_str_to_int_convertion_exception(invalid_mac_address):
    with pytest.raises(ValueError) as excinfo:
        MACAddressConverter.str_to_int(invalid_mac_address)
    assert str(excinfo.value) == "The MAC address has an incorrect format."


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "invalid_mac_address",
    [
        125.0,
        "49:4e:47:03:02:01",
    ],
)
def test_mac_address_int_to_str_convertion_exception(invalid_mac_address):
    with pytest.raises(ValueError) as excinfo:
        MACAddressConverter.int_to_str(invalid_mac_address)
    assert (
        str(excinfo.value)
        == f"The MAC address has the wrong type. Expected an int, got {type(invalid_mac_address)}."
    )

import os
import pytest

from ingenialink.canopen.network import CAN_BAUDRATE

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


@pytest.fixture
def teardown_brake_override(motion_controller):
    yield
    mc, alias = motion_controller
    mc.configuration.default_brake(servo=alias)


@pytest.mark.smoke
def test_release_brake(motion_controller, teardown_brake_override):
    mc, alias = motion_controller
    mc.configuration.release_brake(servo=alias)
    assert (
        mc.communication.get_register(BRAKE_OVERRIDE_REGISTER, servo=alias, axis=1)
        == mc.configuration.BrakeOverride.RELEASE_BRAKE
    )


@pytest.mark.smoke
def test_enable_brake(motion_controller, teardown_brake_override):
    mc, alias = motion_controller
    mc.configuration.enable_brake(servo=alias)
    assert (
        mc.communication.get_register(BRAKE_OVERRIDE_REGISTER, servo=alias, axis=1)
        == mc.configuration.BrakeOverride.ENABLE_BRAKE
    )


@pytest.mark.smoke
def test_disable_brake_override(motion_controller, teardown_brake_override):
    mc, alias = motion_controller
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


@pytest.mark.usefixtures("remove_file_if_exist")
def test_save_configuration_and_load_configuration(motion_controller):
    file_path = "test_file.xcf"
    mc, alias = motion_controller
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
@pytest.mark.eoe
def test_save_configuration_and_load_configuration_nvm_none(motion_controller):
    file_path = "test_file.xcf"
    mc, alias = motion_controller
    old_value = mc.communication.get_register(POSITION_SET_POINT_REGISTER, servo=alias)
    mc.communication.set_register(POSITION_SET_POINT_REGISTER, 10, servo=alias)
    mc.configuration.save_configuration(file_path, servo=alias)
    assert os.path.isfile(file_path)
    mc.communication.set_register(POSITION_SET_POINT_REGISTER, 20, servo=alias)
    mc.configuration.load_configuration(file_path, servo=alias)
    assert mc.communication.get_register(POSITION_SET_POINT_REGISTER, servo=alias) == 20
    mc.communication.set_register(POSITION_SET_POINT_REGISTER, old_value, servo=alias)


def test_set_profiler_exception(motion_controller):
    mc, alias = motion_controller

    with pytest.raises(TypeError):
        mc.configuration.set_profiler(None, None, None, servo=alias)


@pytest.mark.smoke
@pytest.mark.parametrize(
    "acceleration, deceleration, velocity",
    [(0, 0, 0), (15, 20, 25), (1, None, None), (None, 1, None), (None, None, 1)],
)
def test_set_profiler(motion_controller, acceleration, deceleration, velocity):
    mc, alias = motion_controller
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
    for key, value in expected_values.items():
        actual_value = mc.communication.get_register(register_dict[key], servo=alias)
        assert pytest.approx(expected_values[key]) == actual_value


@pytest.mark.smoke
@pytest.mark.parametrize("acceleration", [0, 10, 25])
def test_set_max_acceleration(motion_controller, acceleration):
    mc, alias = motion_controller
    mc.configuration.set_max_acceleration(acceleration, servo=alias)
    output_value = mc.communication.get_register(PROFILE_MAX_ACCELERATION_REGISTER, servo=alias)
    assert pytest.approx(acceleration) == output_value


@pytest.mark.smoke
@pytest.mark.parametrize("acceleration", [0, 10, 25])
def test_set_max_profile_acceleration(motion_controller, acceleration):
    mc, alias = motion_controller
    mc.configuration.set_max_profile_acceleration(acceleration, servo=alias)
    output_value = mc.communication.get_register(PROFILE_MAX_ACCELERATION_REGISTER, servo=alias)
    assert pytest.approx(acceleration) == output_value


@pytest.mark.smoke
@pytest.mark.parametrize("deceleration", [0, 10, 25])
def test_set_max_deceleration(motion_controller, deceleration):
    mc, alias = motion_controller
    mc.configuration.set_max_profile_deceleration(deceleration, servo=alias)
    output_value = mc.communication.get_register(PROFILE_MAX_DECELERATION_REGISTER, servo=alias)
    assert pytest.approx(output_value) == deceleration


@pytest.mark.smoke
@pytest.mark.parametrize("velocity", [0, 10, 25])
def test_set_max_velocity(motion_controller, velocity):
    mc, alias = motion_controller
    mc.configuration.set_max_velocity(velocity, servo=alias)
    output_value = mc.communication.get_register(MAX_VELOCITY_REGISTER, servo=alias)
    assert pytest.approx(velocity) == output_value


@pytest.mark.smoke
@pytest.mark.parametrize("velocity", [0, 10, 25])
def test_set_max_profile_velocity(motion_controller, velocity):
    mc, alias = motion_controller
    mc.configuration.set_max_profile_velocity(velocity, servo=alias)
    output_value = mc.communication.get_register(PROFILE_MAX_VELOCITY_REGISTER, servo=alias)
    assert pytest.approx(velocity) == output_value


@pytest.mark.smoke
def test_get_position_and_velocity_loop_rate(motion_controller):
    mc, alias = motion_controller
    test_value = mc.configuration.get_position_and_velocity_loop_rate(servo=alias)
    reg_value = mc.communication.get_register(POSITION_AND_VELOCITY_LOOP_RATE_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.smoke
def test_get_current_loop_rate(motion_controller):
    mc, alias = motion_controller
    test_value = mc.configuration.get_current_loop_rate(servo=alias)
    reg_value = mc.communication.get_register(CURRENT_LOOP_RATE_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.smoke
def test_get_power_stage_frequency(motion_controller):
    mc, alias = motion_controller
    mc.configuration.get_power_stage_frequency(servo=alias)


@pytest.mark.smoke
def test_get_power_stage_frequency_raw(motion_controller):
    mc, alias = motion_controller
    test_value = mc.configuration.get_power_stage_frequency(servo=alias, raw=True)
    pow_stg_freq = mc.communication.get_register(
        POWER_STAGE_FREQUENCY_SELECTION_REGISTER, servo=alias
    )
    assert test_value == pow_stg_freq


@pytest.mark.smoke
def test_get_power_stage_frequency_enum(motion_controller):
    mc, alias = motion_controller
    mc.configuration.get_power_stage_frequency_enum(servo=alias)


@pytest.mark.smoke
@pytest.mark.parametrize("input_value", [0, 1, 2, 3])
def test_set_power_stage_frequency(motion_controller_teardown, input_value):
    input_value = 0
    mc, alias = motion_controller_teardown
    mc.configuration.set_power_stage_frequency(input_value, servo=alias)
    output_value = mc.communication.get_register(
        POWER_STAGE_FREQUENCY_SELECTION_REGISTER, servo=alias
    )
    assert pytest.approx(input_value) == output_value


@pytest.mark.smoke
def test_get_power_stage_frequency_exception(mocker, motion_controller):
    mc, alias = motion_controller
    mocker.patch("ingeniamotion.communication.Communication.get_register", return_value=5)
    with pytest.raises(ValueError):
        mc.configuration.get_power_stage_frequency(servo=alias)


@pytest.mark.smoke
def test_get_status_word(motion_controller):
    mc, alias = motion_controller
    test_value = mc.configuration.get_status_word(servo=alias)
    reg_value = mc.communication.get_register(STATUS_WORD_REGISTER, servo=alias)
    assert test_value == reg_value


def test_is_motor_enabled_1(motion_controller):
    mc, alias = motion_controller
    mc.motion.motor_disable(alias)
    assert not mc.configuration.is_motor_enabled(servo=alias)
    mc.motion.motor_enable(servo=alias)
    assert mc.configuration.is_motor_enabled(servo=alias)
    mc.motion.motor_disable(servo=alias)
    assert not mc.configuration.is_motor_enabled(servo=alias)


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
    mc, alias = motion_controller
    mocker.patch(
        "ingeniamotion.configuration.Configuration.get_status_word", return_value=status_word_value
    )
    test_value = mc.configuration.is_motor_enabled(servo=alias)
    assert test_value == expected_result


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
    mc, alias = motion_controller
    mocker.patch(
        "ingeniamotion.configuration.Configuration.get_status_word", return_value=status_word_value
    )
    test_value = mc.configuration.is_commutation_feedback_aligned(servo=alias)
    assert test_value == expected_result


def test_set_phasing_mode(motion_controller):
    input_value = 0
    mc, alias = motion_controller
    mc.configuration.set_phasing_mode(input_value, servo=alias)
    output_value = mc.communication.get_register(PHASING_MODE_REGISTER, servo=alias)
    assert pytest.approx(input_value) == output_value


@pytest.mark.smoke
def test_get_phasing_mode(motion_controller):
    mc, alias = motion_controller
    test_value = mc.configuration.get_phasing_mode(servo=alias)
    reg_value = mc.communication.get_register(PHASING_MODE_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.smoke
def test_set_generator_mode(motion_controller):
    input_value = 0
    mc, alias = motion_controller
    mc.configuration.set_generator_mode(input_value, servo=alias)
    output_value = mc.communication.get_register(GENERATOR_MODE_REGISTER, servo=alias)
    assert pytest.approx(input_value) == output_value


def test_set_motor_pair_poles(motion_controller_teardown):
    input_value = 0
    mc, alias = motion_controller_teardown
    mc.configuration.set_motor_pair_poles(input_value, servo=alias)
    output_value = mc.communication.get_register(MOTOR_POLE_PAIRS_REGISTER, servo=alias)
    assert pytest.approx(input_value) == output_value


@pytest.mark.smoke
def test_get_motor_pair_poles(motion_controller):
    mc, alias = motion_controller
    test_value = mc.configuration.get_motor_pair_poles(servo=alias)
    reg_value = mc.communication.get_register(MOTOR_POLE_PAIRS_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.smoke
def test_get_sto_status(motion_controller):
    mc, alias = motion_controller
    test_value = mc.configuration.get_sto_status(servo=alias)
    reg_value = mc.communication.get_register(STO_STATUS_REGISTER, servo=alias)
    assert test_value == reg_value


def patch_get_sto_status(mocker, value):
    mocker.patch("ingeniamotion.configuration.Configuration.get_sto_status", return_value=value)


@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result",
    [
        (0x4843, 1),
        (0xF567, 1),
        (0xFFFF, 1),
        (0x0000, 0),
        (0x4766, 0),
        (0xF6A4, 0),
    ],
)
def test_is_sto1_active(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto1_active(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result",
    [(0xA187, 1), (0x31BA, 1), (0xD7DD, 0), (0xFB8, 0), (0xA8DE, 1), (0x99A5, 0)],
)
def test_is_sto2_active(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto2_active(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result",
    [(0xFAC4, 1), (0x1AE1, 0), (0xD9CA, 0), (0xEE94, 1), (0xAE9F, 1), (0x478B, 0)],
)
def test_check_sto_power_supply(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.check_sto_power_supply(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result",
    [(0x1BAF, 1), (0xD363, 0), (0xAD9D, 1), (0x8D14, 0), (0x9AEE, 1), (0x94A7, 0)],
)
def test_check_sto_abnormal_fault(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.check_sto_abnormal_fault(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result",
    [(0xF29C, 1), (0xF440, 0), (0xD1A7, 0), (0x86D7, 1), (0x2A43, 0), (0x33E6, 0)],
)
def test_get_sto_report_bit(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.get_sto_report_bit(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result", [(0x13A0, False), (0x7648, False), (0x4, True)]
)
def test_is_sto_active(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto_active(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result", [(0xC18A, False), (0x742C, False), (0x17, True)]
)
def test_is_sto_inactive(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto_inactive(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize(
    "sto_status_value, expected_result", [(0x1BF3, False), (0x6B7, False), (0x1F, True)]
)
def test_is_sto_abnormal_latched(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto_abnormal_latched(servo=alias)
    assert value == expected_result


def test_store_configuration(motion_controller):
    mc, alias = motion_controller
    mc.configuration.store_configuration(servo=alias)


def test_restore_configuration(motion_controller):
    mc, alias = motion_controller
    mc.configuration.restore_configuration(servo=alias)


@pytest.mark.no_connection
def test_get_drive_info_coco_moco(motion_controller):
    expected_product_codes = [12, 21]
    expected_revision_numbers = [123, 321]
    expected_firmware_versions = ["4.3.2", "2.3.4"]
    expected_serial_numbers = [3456, 6543]

    mc, alias = motion_controller
    prod_codes, rev_nums, fw_vers, ser_nums = mc.configuration.get_drive_info_coco_moco(alias)

    assert prod_codes == expected_product_codes
    assert rev_nums == expected_revision_numbers
    assert fw_vers == expected_firmware_versions
    assert ser_nums == expected_serial_numbers


@pytest.mark.no_connection
def test_get_product_code(motion_controller):
    expected_product_code_0 = 12
    expected_product_code_1 = 21

    mc, alias = motion_controller
    product_code_0 = mc.configuration.get_product_code(alias, 0)
    product_code_1 = mc.configuration.get_product_code(alias, 1)

    assert product_code_0 == expected_product_code_0
    assert product_code_1 == expected_product_code_1


@pytest.mark.no_connection
def test_get_revision_number(motion_controller):
    expected_revision_number_0 = 123
    expected_revision_number_1 = 321

    mc, alias = motion_controller
    revision_number_0 = mc.configuration.get_revision_number(alias, 0)
    revision_number_1 = mc.configuration.get_revision_number(alias, 1)

    assert revision_number_0 == expected_revision_number_0
    assert revision_number_1 == expected_revision_number_1


@pytest.mark.no_connection
def test_get_serial_number(motion_controller):
    expected_serial_number_0 = 3456
    expected_serial_number_1 = 6543

    mc, alias = motion_controller
    serial_number_0 = mc.configuration.get_serial_number(alias, 0)
    serial_number_1 = mc.configuration.get_serial_number(alias, 1)

    assert serial_number_0 == expected_serial_number_0
    assert serial_number_1 == expected_serial_number_1


@pytest.mark.no_connection
def test_get_fw_version(motion_controller):
    expected_fw_version_0 = "4.3.2"
    expected_fw_version_1 = "2.3.4"

    mc, alias = motion_controller
    firmware_version_0 = mc.configuration.get_fw_version(alias, 0)
    firmware_version_1 = mc.configuration.get_fw_version(alias, 1)

    assert firmware_version_0 == expected_fw_version_0
    assert firmware_version_1 == expected_fw_version_1


@pytest.mark.no_connection
def test_change_baudrate_exception(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(ValueError):
        mc.configuration.change_baudrate(CAN_BAUDRATE.Baudrate_1M, alias)


@pytest.mark.no_connection
def test_get_vendor_id(motion_controller):
    expected_vendor_id = 123456789

    mc, alias = motion_controller
    vendor_id = mc.configuration.get_vendor_id(alias)

    assert vendor_id == expected_vendor_id


@pytest.mark.no_connection
def test_change_node_id_exception(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(ValueError):
        mc.configuration.change_node_id(32, alias)


@pytest.mark.develop
def test_set_velocity_pid(motion_controller_teardown):
    mc, alias = motion_controller_teardown
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


@pytest.mark.develop
def test_set_position_pid(motion_controller_teardown):
    mc, alias = motion_controller_teardown
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


@pytest.mark.develop
@pytest.mark.smoke
def test_get_set_rated_current(motion_controller):
    mc, alias = motion_controller
    initial_rated_current = mc.communication.get_register(RATED_CURRENT_REGISTER, servo=alias)
    read_rated_current = mc.configuration.get_rated_current(alias)
    assert pytest.approx(initial_rated_current) == read_rated_current
    test_rated_current = 1.23
    mc.configuration.set_rated_current(test_rated_current, servo=alias)
    read_test_rated_current = mc.communication.get_register(RATED_CURRENT_REGISTER, servo=alias)
    assert pytest.approx(test_rated_current) == read_test_rated_current
    # Teardown
    mc.communication.set_register(RATED_CURRENT_REGISTER, initial_rated_current, servo=alias)


@pytest.mark.develop
@pytest.mark.smoke
def test_get_max_current(motion_controller):
    mc, alias = motion_controller
    real_max_current = mc.communication.get_register(MAX_CURRENT_REGISTER, servo=alias)
    test_max_current = mc.configuration.get_max_current(alias)
    assert pytest.approx(real_max_current) == test_max_current

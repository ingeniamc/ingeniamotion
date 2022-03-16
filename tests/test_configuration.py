import os
import pytest

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


@pytest.fixture
def teardown_brake_override(motion_controller):
    yield
    mc, alias = motion_controller
    mc.configuration.default_brake(servo=alias)


@pytest.mark.smoke
def test_release_brake(motion_controller, teardown_brake_override):
    mc, alias = motion_controller
    mc.configuration.release_brake(servo=alias)
    assert mc.communication.get_register(
        BRAKE_OVERRIDE_REGISTER, servo=alias, axis=1
    ) == mc.configuration.BrakeOverride.RELEASE_BRAKE


@pytest.mark.smoke
def test_enable_brake(motion_controller, teardown_brake_override):
    mc, alias = motion_controller
    mc.configuration.enable_brake(servo=alias)
    assert mc.communication.get_register(
        BRAKE_OVERRIDE_REGISTER, servo=alias, axis=1
    ) == mc.configuration.BrakeOverride.ENABLE_BRAKE


@pytest.mark.smoke
def test_disable_brake_override(motion_controller, teardown_brake_override):
    mc, alias = motion_controller
    mc.configuration.disable_brake_override(servo=alias)
    assert mc.communication.get_register(
        BRAKE_OVERRIDE_REGISTER, servo=alias, axis=1
    ) == mc.configuration.BrakeOverride.OVERRIDE_DISABLED


@pytest.fixture
def remove_file_if_exist():
    yield
    file_path = "test_file"
    if os.path.isfile(file_path):
        os.remove(file_path)


@pytest.mark.usefixtures("remove_file_if_exist")
def test_save_configuration_and_load_configuration(motion_controller):
    file_path = "test_file"
    mc, alias = motion_controller
    mc.communication.set_register(POSITION_SET_POINT_REGISTER, 0, servo=alias)
    mc.configuration.save_configuration("test_file", servo=alias)
    assert os.path.isfile(file_path)
    mc.communication.set_register(POSITION_SET_POINT_REGISTER, 1000, servo=alias)
    mc.configuration.load_configuration("test_file", servo=alias)
    assert mc.communication.get_register(
        POSITION_SET_POINT_REGISTER, servo=alias) == 0


def test_set_profiler_exception(motion_controller):
    mc, alias = motion_controller

    with pytest.raises(TypeError):
        mc.configuration.set_profiler(
            None, None, None, servo=alias)


@pytest.mark.smoke
@pytest.mark.parametrize("acceleration, deceleration, velocity", [
    (0, 0, 0),
    (15, 20, 25),
    (1, None, None),
    (None, 1, None),
    (None, None, 1)
])
def test_set_profiler(motion_controller, acceleration, deceleration, velocity):
    mc, alias = motion_controller
    expected_acceleration = acceleration
    if acceleration is None:
        expected_acceleration = mc.communication.get_register(
            PROFILE_MAX_ACCELERATION_REGISTER, servo=alias)
    expected_deceleration = deceleration
    if deceleration is None:
        expected_deceleration = mc.communication.get_register(
            PROFILE_MAX_DECELERATION_REGISTER, servo=alias)
    expected_velocity = velocity
    if velocity is None:
        expected_velocity = mc.communication.get_register(
            PROFILE_MAX_VELOCITY_REGISTER, servo=alias)

    mc.configuration.set_profiler(
        acceleration, deceleration, velocity, servo=alias)
    acceleration_value = mc.communication.get_register(
        PROFILE_MAX_ACCELERATION_REGISTER, servo=alias)
    assert pytest.approx(acceleration_value) == expected_acceleration
    deceleration_value = mc.communication.get_register(
        PROFILE_MAX_DECELERATION_REGISTER, servo=alias)
    assert pytest.approx(deceleration_value) == expected_deceleration
    velocity_value = mc.communication.get_register(
        PROFILE_MAX_VELOCITY_REGISTER, servo=alias)
    assert pytest.approx(velocity_value) == expected_velocity


@pytest.mark.smoke
@pytest.mark.parametrize("acceleration", [0, 10, 25])
def test_set_max_acceleration(motion_controller, acceleration):
    mc, alias = motion_controller
    mc.configuration.set_max_acceleration(
        acceleration, servo=alias)
    output_value = mc.communication.get_register(
        PROFILE_MAX_ACCELERATION_REGISTER, servo=alias)
    assert pytest.approx(output_value) == acceleration


@pytest.mark.smoke
@pytest.mark.parametrize("acceleration", [0, 10, 25])
def test_set_max_profile_acceleration(motion_controller, acceleration):
    mc, alias = motion_controller
    mc.configuration.set_max_profile_acceleration(
        acceleration, servo=alias)
    output_value = mc.communication.get_register(
        PROFILE_MAX_ACCELERATION_REGISTER, servo=alias)
    assert pytest.approx(output_value) == acceleration


@pytest.mark.smoke
@pytest.mark.parametrize("deceleration", [0, 10, 25])
def test_set_max_deceleration(motion_controller, deceleration):
    mc, alias = motion_controller
    mc.configuration.set_max_profile_deceleration(
        deceleration, servo=alias)
    output_value = mc.communication.get_register(
        PROFILE_MAX_DECELERATION_REGISTER, servo=alias)
    assert pytest.approx(output_value) == deceleration


@pytest.mark.smoke
@pytest.mark.parametrize("velocity", [0, 10, 25])
def test_set_max_velocity(motion_controller, velocity):
    mc, alias = motion_controller
    mc.configuration.set_max_velocity(
        velocity, servo=alias)
    output_value = mc.communication.get_register(
        MAX_VELOCITY_REGISTER, servo=alias)
    assert pytest.approx(output_value) == velocity


@pytest.mark.smoke
@pytest.mark.parametrize("velocity", [0, 10, 25])
def test_set_max_profile_velocity(motion_controller, velocity):
    mc, alias = motion_controller
    mc.configuration.set_max_profile_velocity(
        velocity, servo=alias)
    output_value = mc.communication.get_register(
        PROFILE_MAX_VELOCITY_REGISTER, servo=alias)
    assert pytest.approx(output_value) == velocity


@pytest.mark.smoke
def test_get_position_and_velocity_loop_rate(motion_controller):
    mc, alias = motion_controller
    test_value = mc.configuration.get_position_and_velocity_loop_rate(servo=alias)
    reg_value = mc.communication.get_register(
        POSITION_AND_VELOCITY_LOOP_RATE_REGISTER, servo=alias)
    assert test_value == reg_value


@pytest.mark.smoke
def test_get_current_loop_rate(motion_controller):
    mc, alias = motion_controller
    test_value = mc.configuration.get_current_loop_rate(servo=alias)
    reg_value = mc.communication.get_register(
        CURRENT_LOOP_RATE_REGISTER, servo=alias)
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
        POWER_STAGE_FREQUENCY_SELECTION_REGISTER, servo=alias)
    assert test_value == pow_stg_freq


@pytest.mark.smoke
def test_get_power_stage_frequency_enum(motion_controller):
    mc, alias = motion_controller
    mc.configuration.get_power_stage_frequency_enum(servo=alias)


@pytest.mark.smoke
@pytest.mark.parametrize("input_value", [
    0, 1, 2, 3
])
def test_set_power_stage_frequency(motion_controller, input_value):
    input_value = 0
    mc, alias = motion_controller
    mc.configuration.set_power_stage_frequency(
        input_value, servo=alias)
    output_value = mc.communication.get_register(
        POWER_STAGE_FREQUENCY_SELECTION_REGISTER, servo=alias)
    assert pytest.approx(output_value) == input_value


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
@pytest.mark.parametrize("status_word_value, expected_result", [
    (0xf29c, True), (0xf440, False), (0xd1a7, True),
    (0x86d7, True), (0x2a43, False), (0x33e6, True)
])
def test_is_motor_enabled_2(mocker, motion_controller,
                            status_word_value, expected_result):
    mc, alias = motion_controller
    mocker.patch('ingeniamotion.configuration.Configuration.get_status_word',
                 return_value=status_word_value)
    test_value = mc.configuration.is_motor_enabled(servo=alias)
    assert test_value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize("status_word_value, expected_result", [
    (0xf29c, True), (0xf440, True), (0xd1a7, True),
    (0x86d7, False), (0x2a43, False), (0x33e6, False)
])
def test_is_commutation_feedback_aligned(mocker, motion_controller,
                                         status_word_value, expected_result):
    mc, alias = motion_controller
    mocker.patch('ingeniamotion.configuration.Configuration.get_status_word',
                 return_value=status_word_value)
    test_value = mc.configuration.is_commutation_feedback_aligned(servo=alias)
    assert test_value == expected_result


def test_set_phasing_mode(motion_controller):
    input_value = 0
    mc, alias = motion_controller
    mc.configuration.set_phasing_mode(
        input_value, servo=alias)
    output_value = mc.communication.get_register(
        PHASING_MODE_REGISTER, servo=alias)
    assert pytest.approx(output_value) == input_value


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
    mc.configuration.set_generator_mode(
        input_value, servo=alias)
    output_value = mc.communication.get_register(
        GENERATOR_MODE_REGISTER, servo=alias)
    assert pytest.approx(output_value) == input_value


def test_set_motor_pair_poles(motion_controller_teardown):
    input_value = 0
    mc, alias = motion_controller_teardown
    mc.configuration.set_motor_pair_poles(
        input_value, servo=alias)
    output_value = mc.communication.get_register(
        MOTOR_POLE_PAIRS_REGISTER, servo=alias)
    assert pytest.approx(output_value) == input_value


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
    mocker.patch('ingeniamotion.configuration.Configuration.get_sto_status',
                 return_value=value)


@pytest.mark.smoke
@pytest.mark.parametrize("sto_status_value, expected_result", [
    (0x4843, 1), (0xf567, 1), (0xffff, 1), (0x0000, 0), (0x4766, 0), (0xf6a4, 0),
])
def test_is_sto1_active(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto1_active(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize("sto_status_value, expected_result", [
    (0xa187, 1), (0x31ba, 1), (0xd7dd, 0), (0xfb8, 0), (0xa8de, 1), (0x99a5, 0)
])
def test_is_sto2_active(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto2_active(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize("sto_status_value, expected_result", [
    (0xfac4, 1), (0x1ae1, 0), (0xd9ca, 0),
    (0xee94, 1), (0xae9f, 1), (0x478b, 0)
])
def test_check_sto_power_supply(mocker, motion_controller,
                                sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.check_sto_power_supply(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize("sto_status_value, expected_result", [
    (0x1baf, 1), (0xd363, 0), (0xad9d, 1),
    (0x8d14, 0), (0x9aee, 1), (0x94a7, 0)
])
def test_check_sto_abnormal_fault(mocker, motion_controller,
                                  sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.check_sto_abnormal_fault(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize("sto_status_value, expected_result", [
    (0xf29c, 1), (0xf440, 0), (0xd1a7, 0), (0x86d7, 1), (0x2a43, 0), (0x33e6, 0)
])
def test_get_sto_report_bit(mocker, motion_controller,
                            sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.get_sto_report_bit(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize("sto_status_value, expected_result", [
    (0x13a0, False), (0x7648, False), (0x4, True)
])
def test_is_sto_active(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto_active(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize("sto_status_value, expected_result", [
    (0xc18a, False), (0x742c, False), (0x17, True)
])
def test_is_sto_inactive(mocker, motion_controller, sto_status_value, expected_result):
    mc, alias = motion_controller
    patch_get_sto_status(mocker, sto_status_value)
    value = mc.configuration.is_sto_inactive(servo=alias)
    assert value == expected_result


@pytest.mark.smoke
@pytest.mark.parametrize("sto_status_value, expected_result", [
    (0x1bf3, False), (0x6b7, False), (0x1F, True)
])
def test_is_sto_abnormal_latched(mocker, motion_controller,
                                 sto_status_value, expected_result):
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

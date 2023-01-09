import time

import pytest

from ingeniamotion.enums import HomingMode, SensorType, OperationMode
from .conftest import mean_actual_velocity_position

HOMING_MODE_REGISTER = "HOM_MODE"
HOMING_OFFSET_REGISTER = "HOM_OFFSET"
HOMING_TIMEOUT_REGISTER = "HOM_SEQ_TIMEOUT"
HOMING_ZERO_VELOCITY_REGISTER = "HOM_SPEED_ZERO"
HOMING_SEARCH_VELOCITY_REGISTER = "HOM_SPEED_SEARCH"
HOMING_INDEX_PULSE_SOURCE_REGISTER = "HOM_IDX_PULSE_SRC"
POSITIVE_HOMING_SWITCH_REGISTER = "IO_IN_POS_HOM_SWITCH"
NEGATIVE_HOMING_SWITCH_REGISTER = "IO_IN_NEG_HOM_SWITCH"
VELOCITY_SET_POINT_REGISTER = "CL_VEL_SET_POINT_VALUE"

STATUS_WORD_HOMING_ERROR_BIT = 0x2000
STATUS_WORD_HOMING_ATTAINED_BIT = 0x1000
STATUS_WORD_TARGET_REACHED_BIT = 0x400

RELATIVE_ERROR_ALLOWED = 3e-2


@pytest.fixture
def initial_position(motion_controller):
    mc, alias = motion_controller
    mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION, servo=alias)
    mc.motion.motor_enable(servo=alias)
    last_pos = mc.motion.get_actual_position(servo=alias)
    position = mc.configuration.get_position_feedback_resolution(servo=alias)//2
    mc.motion.move_to_position(position+last_pos, servo=alias, blocking=True, timeout=5)
    mc.motion.motor_disable(servo=alias)
    return position


@pytest.mark.smoke
@pytest.mark.parametrize("homing_mode", list(HomingMode))
def test_set_homing_mode(motion_controller, homing_mode):
    mc, alias = motion_controller
    mc.configuration.set_homing_mode(homing_mode, servo=alias)
    test_homing_mode = mc.communication.get_register(
        HOMING_MODE_REGISTER, servo=alias)
    assert test_homing_mode == homing_mode


@pytest.mark.smoke
@pytest.mark.parametrize("homing_offset", [0, 10, 500, -12, -100, 1000])
def test_set_homing_offset(motion_controller, homing_offset):
    mc, alias = motion_controller
    mc.configuration.set_homing_offset(homing_offset, servo=alias)
    test_homing_offset = mc.communication.get_register(
        HOMING_OFFSET_REGISTER, servo=alias)
    assert test_homing_offset == homing_offset


@pytest.mark.smoke
@pytest.mark.parametrize("homing_timeout", [0, 10, 500, 1000, 5000, 10000])
def test_set_homing_timeout(motion_controller, homing_timeout):
    mc, alias = motion_controller
    mc.configuration.set_homing_timeout(homing_timeout, servo=alias)
    test_homing_timeout = mc.communication.get_register(
        HOMING_TIMEOUT_REGISTER, servo=alias)
    assert test_homing_timeout == homing_timeout


@pytest.mark.smoke
@pytest.mark.parametrize("homing_offset", [0, 1000])
@pytest.mark.usefixtures("initial_position")
def test_homing_on_current_position(motion_controller, homing_offset):
    mc, alias = motion_controller
    mc.configuration.homing_on_current_position(homing_offset, servo=alias)
    feedback_resolution = mc.configuration.get_position_feedback_resolution(servo=alias)
    assert pytest.approx(
        mc.motion.get_actual_position(servo=alias),
        abs=feedback_resolution*RELATIVE_ERROR_ALLOWED) == homing_offset


@pytest.mark.smoke
@pytest.mark.usefixtures("initial_position")
@pytest.mark.parametrize("direction", [1, 0])
def test_homing_on_switch_limit(motion_controller, direction):
    mc, alias = motion_controller
    homing_offset = 10
    homing_timeout = 5000
    search_vel = 10.0
    zero_vel = 1.0
    switch = 2
    mc.configuration.homing_on_switch_limit(homing_offset, direction,
                                            switch, homing_timeout,
                                            search_vel, zero_vel,
                                            servo=alias, motor_enable=False)
    test_offset = mc.communication.get_register(HOMING_OFFSET_REGISTER, servo=alias)
    test_timeout = mc.communication.get_register(HOMING_TIMEOUT_REGISTER, servo=alias)
    test_hom_mode = mc.communication.get_register(HOMING_MODE_REGISTER, servo=alias)
    test_op_mode = mc.motion.get_operation_mode(servo=alias)
    test_search_vel = mc.communication.get_register(
        HOMING_SEARCH_VELOCITY_REGISTER, servo=alias)
    test_zero_vel = mc.communication.get_register(
        HOMING_ZERO_VELOCITY_REGISTER, servo=alias)
    switch_register = POSITIVE_HOMING_SWITCH_REGISTER if direction == 1 else \
        NEGATIVE_HOMING_SWITCH_REGISTER
    test_switch = mc.communication.get_register(switch_register, servo=alias)
    assert test_offset == homing_offset
    assert test_timeout == homing_timeout
    if direction == 1:
        assert test_hom_mode == HomingMode.POSITIVE_LIMIT_SWITCH
    elif direction == 0:
        assert test_hom_mode == HomingMode.NEGATIVE_LIMIT_SWITCH
    assert test_op_mode == OperationMode.HOMING
    assert pytest.approx(test_zero_vel) == zero_vel
    assert pytest.approx(test_search_vel) == search_vel
    assert test_switch == switch


@pytest.mark.usefixtures("initial_position")
def test_homing_on_switch_limit_timeout(motion_controller):
    mc, alias = motion_controller
    homing_offset = 10
    homing_timeout = 5000
    search_vel = 10.0
    zero_vel = 1.0
    switch = 2
    direction = 1
    mc.configuration.homing_on_switch_limit(
        homing_offset, direction, switch, homing_timeout,
        search_vel, zero_vel, servo=alias, motor_enable=False)
    time.sleep(homing_timeout/1000)
    assert pytest.approx(0, abs=0.05) == mean_actual_velocity_position(mc, alias, velocity=True)
    mc.motion.motor_enable(servo=alias)
    mc.motion.target_latch(servo=alias)
    time.sleep(1)
    assert mean_actual_velocity_position(mc, alias, velocity=True) > 0.05
    time.sleep(homing_timeout/1000)
    assert pytest.approx(0, abs=0.05) == mean_actual_velocity_position(mc, alias, velocity=True)


def __check_index_pulse_is_allowed(feedback_list):
    motor_enable = True
    if SensorType.QEI in feedback_list:
        sensor_index = 0
    elif SensorType.QEI2 in feedback_list:
        sensor_index = 1
    else:
        sensor_index = 1
        motor_enable = False
    return motor_enable, sensor_index


def __check_homing_was_successful(mc, alias, timeout_ms):
    init_time = time.time()
    while init_time + timeout_ms/1000 > time.time():
        status_word = mc.configuration.get_status_word(servo=alias)
        homing_error = bool(status_word & STATUS_WORD_HOMING_ERROR_BIT)
        homing_attained = bool(status_word & STATUS_WORD_HOMING_ATTAINED_BIT)
        if (not homing_error) & homing_attained:
            return True
    return False


@pytest.mark.usefixtures("initial_position")
@pytest.mark.parametrize("direction", [1, 0])
def test_homing_on_index_pulse(motion_controller, feedback_list, direction):
    mc, alias = motion_controller
    homing_offset = 1000
    homing_timeout = 10000
    zero_vel = 0.1
    motor_enable, sensor_index = __check_index_pulse_is_allowed(feedback_list)
    mc.configuration.homing_on_index_pulse(homing_offset, direction,
                                           sensor_index, homing_timeout,
                                           zero_vel, servo=alias,
                                           motor_enable=motor_enable)
    if motor_enable:
        assert __check_homing_was_successful(mc, alias, homing_timeout)
    test_offset = mc.communication.get_register(HOMING_OFFSET_REGISTER, servo=alias)
    test_timeout = mc.communication.get_register(HOMING_TIMEOUT_REGISTER, servo=alias)
    test_hom_mode = mc.communication.get_register(HOMING_MODE_REGISTER, servo=alias)
    test_op_mode = mc.motion.get_operation_mode(servo=alias)
    test_zero_vel = mc.communication.get_register(
        HOMING_ZERO_VELOCITY_REGISTER, servo=alias)
    test_sensor_index = mc.communication.get_register(
        HOMING_INDEX_PULSE_SOURCE_REGISTER, servo=alias)
    assert test_offset == homing_offset
    assert test_timeout == homing_timeout
    if direction == 1:
        assert test_hom_mode == HomingMode.POSITIVE_IDX_PULSE
    elif direction == 0:
        assert test_hom_mode == HomingMode.NEGATIVE_IDX_PULSE
    assert test_op_mode == OperationMode.HOMING
    assert pytest.approx(test_zero_vel) == zero_vel
    assert test_sensor_index == sensor_index
    if motor_enable:
        resolution = mc.configuration.get_position_feedback_resolution(servo=alias)
        actual_position = mc.motion.get_actual_position(servo=alias)
        assert pytest.approx(
            actual_position,
            abs=resolution*RELATIVE_ERROR_ALLOWED
        ) == homing_offset


@pytest.mark.smoke
@pytest.mark.usefixtures("initial_position")
@pytest.mark.parametrize("direction", [1, 0])
def test_homing_on_switch_limit_and_index_pulse(motion_controller, direction):
    mc, alias = motion_controller
    homing_offset = 300
    homing_timeout = 3000
    search_vel = 5.0
    zero_vel = 7.0
    switch = 3
    sensor_index = 1
    mc.configuration.homing_on_switch_limit_and_index_pulse(
        homing_offset, direction, switch, sensor_index, homing_timeout,
        search_vel, zero_vel, servo=alias, motor_enable=False)
    test_offset = mc.communication.get_register(HOMING_OFFSET_REGISTER, servo=alias)
    test_timeout = mc.communication.get_register(HOMING_TIMEOUT_REGISTER, servo=alias)
    test_hom_mode = mc.communication.get_register(HOMING_MODE_REGISTER, servo=alias)
    test_op_mode = mc.motion.get_operation_mode(servo=alias)
    test_search_vel = mc.communication.get_register(
        HOMING_SEARCH_VELOCITY_REGISTER, servo=alias)
    test_zero_vel = mc.communication.get_register(
        HOMING_ZERO_VELOCITY_REGISTER, servo=alias)
    switch_register = POSITIVE_HOMING_SWITCH_REGISTER if direction == 1 else \
        NEGATIVE_HOMING_SWITCH_REGISTER
    test_switch = mc.communication.get_register(switch_register, servo=alias)
    test_sensor_index = mc.communication.get_register(
        HOMING_INDEX_PULSE_SOURCE_REGISTER, servo=alias)
    assert test_offset == homing_offset
    assert test_timeout == homing_timeout
    if direction == 1:
        assert test_hom_mode == HomingMode.POSITIVE_LIMIT_SWITCH_IDX_PULSE
    elif direction == 0:
        assert test_hom_mode == HomingMode.NEGATIVE_LIMIT_SWITCH_IDX_PULSE
    assert test_op_mode == OperationMode.HOMING
    assert pytest.approx(test_zero_vel) == zero_vel
    assert pytest.approx(test_search_vel) == search_vel
    assert test_switch == switch
    assert test_sensor_index == sensor_index

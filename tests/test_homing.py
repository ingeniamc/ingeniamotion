import time

import pytest

from ingeniamotion.enums import HomingMode, SensorType, OperationMode

HOMING_MODE_REGISTER = "HOM_MODE"
HOMING_OFFSET_REGISTER = "HOM_OFFSET"
HOMING_TIMEOUT_REGISTER = "HOM_SEQ_TIMEOUT"
HOMING_ZERO_VELOCITY_REGISTER = "HOM_SPEED_ZERO"
HOMING_SEARCH_VELOCITY_REGISTER = "HOM_SPEED_SEARCH"
HOMING_INDEX_PULSE_SOURCE_REGISTER = "HOM_IDX_PULSE_SRC"
POSITIVE_HOMING_SWITCH_REGISTER = "IO_IN_POS_HOM_SWITCH"
NEGATIVE_HOMING_SWITCH_REGISTER = "IO_IN_NEG_HOM_SWITCH"
VELOCITY_SET_POINT_REGISTER = "CL_VEL_SET_POINT_VALUE"


@pytest.fixture
def initial_position(motion_controller):
    mc, alias = motion_controller
    mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION, servo=alias)
    mc.motion.motor_enable(servo=alias)
    position = mc.configuration.get_position_feedback_resolution(servo=alias)//2
    mc.motion.move_to_position(position, servo=alias, blocking=True)
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
    assert mc.motion.get_actual_position(servo=alias) == homing_offset


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
    assert mc.motion.get_actual_velocity(servo=alias) == 0
    mc.motion.motor_enable(servo=alias)
    mc.motion.target_latch(servo=alias)
    assert mc.motion.get_actual_velocity(servo=alias) != 0
    time.sleep(homing_timeout/1000+1)
    assert mc.motion.get_actual_velocity(servo=alias) == 0


@pytest.mark.usefixtures("initial_position")
@pytest.mark.parametrize("direction", [1, 0])
def test_homing_on_index_pulse(motion_controller, feedback_list, direction):
    mc, alias = motion_controller
    homing_offset = 1000
    homing_timeout = 10000
    zero_vel = 0.3
    motor_enable = True
    if SensorType.QEI in feedback_list:
        sensor_index = 0
    elif SensorType.QEI2 in feedback_list:
        sensor_index = 1
    else:
        sensor_index = 1
        motor_enable = False
    mc.configuration.homing_on_index_pulse(homing_offset, direction,
                                           sensor_index, homing_timeout,
                                           zero_vel, servo=alias,
                                           motor_enable=motor_enable)
    if motor_enable:
        time.sleep(5)
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
        assert pytest.approx(actual_position, abs=resolution/20.) == homing_offset


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

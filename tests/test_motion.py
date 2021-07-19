import time
import pytest
import numpy as np

from ingeniamotion.enums import OperationMode

POS_PID_KP_VALUE = 0.1
POSITION_PERCENTAGE_ERROR_ALLOWED = 5


# def test_target_latch():
#     assert False


@pytest.mark.parametrize("operation_mode", list(OperationMode))
def test_set_operation_mode(motion_controller, operation_mode):
    mc, alias = motion_controller
    mc.motion.set_operation_mode(operation_mode, servo=alias)
    test_op = mc.communication.get_register("DRV_OP_CMD", servo=alias)
    assert operation_mode.value == test_op


@pytest.mark.parametrize("operation_mode", list(OperationMode))
def test_get_operation_mode(motion_controller, operation_mode):
    mc, alias = motion_controller
    mc.communication.set_register("DRV_OP_CMD", operation_mode, servo=alias)
    test_op = mc.motion.get_operation_mode(servo=alias)
    assert test_op == operation_mode.value


def test_motor_enable(motion_controller):
    mc, alias = motion_controller
    mc.motion.motor_enable(servo=alias)
    assert mc.configuration.is_motor_enabled(servo=alias)


def test_motor_disable(motion_controller):
    mc, alias = motion_controller
    mc.motion.motor_enable(servo=alias)
    mc.motion.motor_disable(servo=alias)
    assert not mc.configuration.is_motor_enabled(servo=alias)


@pytest.mark.parametrize("position_value", [
    1000, 0, -1000, 4000
])
def test_set_position(motion_controller, position_value):
    mc, alias = motion_controller
    mc.motion.move_to_position(position_value, servo=alias,
                               target_latch=False, blocking=False)
    test_position = mc.communication.get_register(
        "CL_POS_SET_POINT_VALUE", servo=alias)
    assert test_position == position_value


@pytest.mark.parametrize("position_value", [
    1000, 0, -1000, 4000
])
def test_move_position(motion_controller, position_value):
    mc, alias = motion_controller
    pos_res = mc.configuration.get_position_feedback_resolution(servo=alias)
    mc.motion.set_operation_mode(
        OperationMode.PROFILE_POSITION, servo=alias)
    mc.motion.motor_enable(servo=alias)
    mc.motion.move_to_position(
        position_value, servo=alias, blocking=True)
    test_position = mc.communication.get_register(
        "CL_POS_FBK_VALUE", servo=alias)
    assert pytest.approx(
        test_position, abs=pos_res * POSITION_PERCENTAGE_ERROR_ALLOWED / 100
    ) == position_value


@pytest.mark.parametrize("velocity_value", [
    0.5, 1, 0, -0.5
])
def test_set_velocity(motion_controller, velocity_value):
    mc, alias = motion_controller
    mc.motion.set_velocity(
        velocity_value, servo=alias, target_latch=False)
    test_vel = mc.communication.get_register(
        "CL_VEL_SET_POINT_VALUE", servo=alias)
    assert test_vel == velocity_value


# TODO Update approx error. Well tuned motor is needed.
@pytest.mark.parametrize("velocity_value", [
    0.5, 1, 0, -0.5
])
def test_set_velocity_blocking(motion_controller, velocity_value):
    mc, alias = motion_controller
    mc.motion.set_operation_mode(
        OperationMode.PROFILE_VELOCITY, servo=alias)
    mc.motion.motor_enable(servo=alias)
    mc.motion.set_velocity(
        velocity_value, servo=alias, blocking=True)
    time.sleep(1)
    test_vel = mc.communication.get_register(
        "CL_VEL_FBK_VALUE", servo=alias)
    assert pytest.approx(test_vel, abs=0.1) == velocity_value


@pytest.mark.parametrize("current_value", [
    0.5, 1, 0, -0.5
])
def test_set_current_quadrature(motion_controller, current_value):
    mc, alias = motion_controller
    mc.motion.set_current_quadrature(
        current_value, servo=alias)
    test_current = mc.communication.get_register(
        "CL_CUR_Q_SET_POINT", servo=alias)
    assert pytest.approx(test_current) == current_value


@pytest.mark.parametrize("current_value", [
    0.5, 1, 0, -0.5
])
def test_set_current_direct(motion_controller, current_value):
    mc, alias = motion_controller
    mc.motion.set_current_direct(
        current_value, servo=alias)
    test_current = mc.communication.get_register(
        "CL_CUR_D_SET_POINT", servo=alias)
    assert pytest.approx(test_current) == current_value


@pytest.mark.parametrize("voltage_value", [
    0.5, 1, 0, -0.5
])
def test_set_voltage_quadrature(motion_controller, voltage_value):
    mc, alias = motion_controller
    mc.motion.set_voltage_quadrature(
        voltage_value, servo=alias)
    test_voltage = mc.communication.get_register(
        "CL_VOL_Q_SET_POINT", servo=alias)
    assert pytest.approx(test_voltage) == voltage_value


@pytest.mark.parametrize("voltage_value", [
    0.5, 1, 0, -0.5
])
def test_set_voltage_direct(motion_controller, voltage_value):
    mc, alias = motion_controller
    mc.motion.set_voltage_direct(
        voltage_value, servo=alias)
    test_voltage = mc.communication.get_register(
        "CL_VOL_D_SET_POINT", servo=alias)
    assert pytest.approx(test_voltage) == voltage_value


# def test_current_quadrature_ramp():
#     assert False
#
#
# def test_current_direct_ramp():
#     assert False
#
#
# def test_voltage_quadrature_ramp():
#     assert False
#
#
# def test_voltage_direct_ramp():
#     assert False
#
#
# def test_ramp_generator():
#     assert False


@pytest.mark.parametrize("position_value", [
    1000, 0, -1000, 4000
])
def test_get_actual_position(motion_controller, position_value):
    mc, alias = motion_controller
    mc.motion.set_operation_mode(
        OperationMode.PROFILE_POSITION, servo=alias)
    mc.motion.motor_enable(servo=alias)
    mc.motion.move_to_position(
        position_value, servo=alias, blocking=True)
    test_position = mc.motion.get_actual_position(servo=alias)
    assert abs(test_position - position_value) < 10


# def test_wait_for_position():
#     assert False
#
#
# def test_wait_for_velocity():
#     assert False


@pytest.mark.parametrize("op_mode", [
    OperationMode.VOLTAGE, OperationMode.CURRENT
])
def test_set_internal_generator_configuration(motion_controller_teardown, op_mode):
    mc, alias = motion_controller_teardown
    mc.motion.set_internal_generator_configuration(
        op_mode, servo=alias)
    assert op_mode == mc.motion.get_operation_mode(servo=alias)
    assert 1 == mc.configuration.get_motor_pair_poles(servo=alias)


@pytest.mark.parametrize("op_mode", [
    OperationMode.VOLTAGE, OperationMode.CURRENT
])
@pytest.mark.parametrize("direction", [
    -1, 1
])
def test_internal_generator_saw_tooth_move(
        motion_controller_teardown, op_mode, direction):
    mc, alias = motion_controller_teardown
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)
    pos_resolution = mc.configuration.get_position_feedback_resolution(servo=alias)
    initial_position = mc.motion.get_actual_position(servo=alias)
    mc.motion.set_internal_generator_configuration(op_mode, servo=alias)
    mc.motion.motor_enable(servo=alias)
    if op_mode == OperationMode.CURRENT:
        mc.motion.current_quadrature_ramp(1, 1, servo=alias)
        mc.motion.current_direct_ramp(1, 1, servo=alias)
    else:
        mc.motion.voltage_quadrature_ramp(1, 1, servo=alias)
        mc.motion.voltage_direct_ramp(1, 1, servo=alias)
    time.sleep(1)
    mc.motion.internal_generator_saw_tooth_move(
        direction, pair_poles, 1, servo=alias)
    time.sleep(pair_poles)
    time.sleep(1)
    final_position = mc.motion.get_actual_position(servo=alias)
    total_movement = final_position - initial_position
    expected_movement = pos_resolution * direction
    assert abs(total_movement - expected_movement) < \
           pos_resolution * POSITION_PERCENTAGE_ERROR_ALLOWED / 100


@pytest.mark.parametrize("op_mode", [
    OperationMode.VOLTAGE, OperationMode.CURRENT
])
@pytest.mark.parametrize("direction", [
    -1, 1
])
def test_internal_generator_constant_move(
        motion_controller_teardown, op_mode, direction):
    mc, alias = motion_controller_teardown
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)
    pos_resolution = mc.configuration.get_position_feedback_resolution(servo=alias)
    cycle_pos = pos_resolution / pair_poles
    mc.motion.set_internal_generator_configuration(op_mode, servo=alias)
    mc.motion.motor_enable(servo=alias)
    if op_mode == OperationMode.CURRENT:
        mc.motion.current_quadrature_ramp(1, 2, servo=alias)
        mc.motion.current_direct_ramp(1, 2, servo=alias)
    else:
        mc.motion.voltage_quadrature_ramp(1, 2, servo=alias)
        mc.motion.voltage_direct_ramp(1, 2, servo=alias)
    time.sleep(1)
    mc.motion.internal_generator_constant_move(
        0, servo=alias)
    initial_position = mc.motion.get_actual_position(servo=alias)
    list_values = np.linspace(0, 1, 5) if direction > 0 else \
        np.linspace(1, 0, 5)
    for value in list_values:
        mc.motion.internal_generator_constant_move(
            value, servo=alias)
        time.sleep(1)
        final_position = mc.motion.get_actual_position(servo=alias)
        total_movement = final_position - initial_position
        expected_movement = cycle_pos * value if direction > 0 else \
            cycle_pos * (value - 1)
        assert abs(total_movement - expected_movement) < \
               pos_resolution * POSITION_PERCENTAGE_ERROR_ALLOWED / 100

import time
import pytest
import numpy as np
from ingenialink import exceptions
import logging

from ingeniamotion.enums import OperationMode
from ingeniamotion.motion import Motion
from ingeniamotion.exceptions import IMTimeoutError

POS_PID_KP_VALUE = 0.1
POSITION_PERCENTAGE_ERROR_ALLOWED = 5

PROFILER_LATCHING_MODE_REGISTER = "PROF_LATCH_MODE"
OPERATION_MODE_REGISTER = "DRV_OP_CMD"
POSITION_SET_POINT_REGISTER = "CL_POS_SET_POINT_VALUE"
ACTUAL_POSITION_REGISTER = "CL_POS_FBK_VALUE"
VELOCITY_SET_POINT_REGISTER = "CL_VEL_SET_POINT_VALUE"
ACTUAL_VELOCITY_REGISTER = "CL_VEL_FBK_VALUE"
CURRENT_QUADRATURE_SET_POINT_REGISTER = "CL_CUR_Q_SET_POINT"
ACTUAL_QUADRATURE_CURRENT_REGISTER = "CL_CUR_Q_VALUE"
CURRENT_DIRECT_SET_POINT_REGISTER = "CL_CUR_D_SET_POINT"
ACTUAL_DIRECT_CURRENT_REGISTER = "CL_CUR_D_VALUE"
VOLTAGE_QUADRATURE_SET_POINT_REGISTER = "CL_VOL_Q_SET_POINT"
VOLTAGE_DIRECT_SET_POINT_REGISTER = "CL_VOL_D_SET_POINT"


def test_target_latch(motion_controller):
    mc, alias = motion_controller
    mc.communication.set_register(PROFILER_LATCHING_MODE_REGISTER,
                                  0x40, servo=alias)
    mc.motion.motor_enable(servo=alias)
    pos_res = mc.configuration.get_position_feedback_resolution(servo=alias)
    init_pos = mc.motion.get_actual_position(servo=alias)
    mc.motion.move_to_position(init_pos + pos_res, servo=alias, target_latch=False)
    test_act_pos = mc.motion.get_actual_position(servo=alias)
    time.sleep(1)
    assert pytest.approx(
        test_act_pos, pos_res * POSITION_PERCENTAGE_ERROR_ALLOWED/100
    ) == init_pos
    mc.motion.target_latch(servo=alias)
    time.sleep(1)
    test_act_pos = mc.motion.get_actual_position(servo=alias)
    assert pytest.approx(
        test_act_pos, pos_res * POSITION_PERCENTAGE_ERROR_ALLOWED / 100
    ) == init_pos + pos_res


@pytest.mark.smoke
@pytest.mark.parametrize("operation_mode", list(OperationMode))
def test_set_operation_mode(motion_controller, operation_mode):
    mc, alias = motion_controller
    mc.motion.set_operation_mode(operation_mode, servo=alias)
    test_op = mc.communication.get_register(OPERATION_MODE_REGISTER,
                                            servo=alias)
    assert operation_mode.value == test_op


@pytest.mark.smoke
@pytest.mark.parametrize("operation_mode", list(OperationMode))
def test_get_operation_mode(motion_controller, operation_mode):
    mc, alias = motion_controller
    mc.communication.set_register(OPERATION_MODE_REGISTER,
                                  operation_mode, servo=alias)
    test_op = mc.motion.get_operation_mode(servo=alias)
    assert test_op == operation_mode.value


@pytest.mark.smoke
def test_motor_enable(motion_controller):
    mc, alias = motion_controller
    mc.motion.motor_enable(servo=alias)
    assert mc.configuration.is_motor_enabled(servo=alias)


@pytest.mark.parametrize("uid, value, exception_type, message", [
    ("DRV_PROT_USER_UNDER_VOLT", 100, exceptions.ILStateError,
     "User Under-voltage detected"),
    ("DRV_PROT_USER_OVER_TEMP", 1, exceptions.ILStateError,
     "Over-temperature detected (user limit)"),
    ("DRV_PROT_USER_OVER_VOLT", 1, exceptions.ILStateError,
     "User Over-voltage detected")
])
def test_motor_enable_error(motion_controller_teardown,
                            uid, value, exception_type, message):
    mc, alias = motion_controller_teardown
    mc.communication.set_register(uid, value, alias)
    with pytest.raises(exception_type) as excinfo:
        mc.motion.motor_enable(servo=alias)
    assert str(excinfo.value) == \
           "An error occurred enabling motor. Reason: {}" \
           .format(message)


def test_motor_enable_with_fault(motion_controller_teardown):
    uid = "DRV_PROT_USER_UNDER_VOLT"
    value = 100
    exception_type = exceptions.ILStateError
    message = "User Under-voltage detected"
    mc, alias = motion_controller_teardown
    mc.communication.set_register(uid, value, alias)
    with pytest.raises(exception_type) as excinfo_1:
        mc.motion.motor_enable(servo=alias)
    assert str(excinfo_1.value) == \
           "An error occurred enabling motor. Reason: {}" \
           .format(message)
    with pytest.raises(exception_type) as excinfo_2:
        mc.motion.motor_enable(servo=alias)
    assert str(excinfo_2.value) == \
           "An error occurred enabling motor. Reason: {}" \
           .format(message)


@pytest.mark.smoke
@pytest.mark.parametrize("enable_motor", [True, False])
def test_motor_disable(motion_controller, enable_motor):
    mc, alias = motion_controller
    if enable_motor:
        mc.motion.motor_enable(servo=alias)
    mc.motion.motor_disable(servo=alias)
    assert not mc.configuration.is_motor_enabled(servo=alias)


def test_motor_disable_with_fault(motion_controller_teardown):
    uid = "DRV_PROT_USER_UNDER_VOLT"
    value = 100
    exception_type = exceptions.ILStateError
    mc, alias = motion_controller_teardown
    mc.communication.set_register(uid, value, alias)
    with pytest.raises(exception_type):
        mc.motion.motor_enable(servo=alias)
    mc.motion.motor_disable(servo=alias)
    assert not mc.configuration.is_motor_enabled(servo=alias)


def test_fault_reset(motion_controller_teardown):
    mc, alias = motion_controller_teardown
    uid = "DRV_PROT_USER_UNDER_VOLT"
    value = 100
    mc.communication.set_register(uid, value, alias)
    assert not mc.errors.is_fault_active(servo=alias)
    with pytest.raises(exceptions.ILStateError):
        mc.motion.motor_enable(servo=alias)
    assert mc.errors.is_fault_active(servo=alias)
    mc.motion.fault_reset(servo=alias)
    assert not mc.errors.is_fault_active(servo=alias)


@pytest.mark.smoke
@pytest.mark.parametrize("position_value", [
    1000, 0, -1000, 4000
])
def test_set_position(motion_controller, position_value):
    mc, alias = motion_controller
    mc.motion.move_to_position(position_value, servo=alias,
                               target_latch=False, blocking=False)
    test_position = mc.communication.get_register(
        POSITION_SET_POINT_REGISTER, servo=alias)
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
        ACTUAL_POSITION_REGISTER, servo=alias)
    assert pytest.approx(
        test_position, abs=pos_res * POSITION_PERCENTAGE_ERROR_ALLOWED / 100
    ) == position_value


@pytest.mark.smoke
@pytest.mark.parametrize("velocity_value", [
    0.5, 1, 0, -0.5
])
def test_set_velocity(motion_controller, velocity_value):
    mc, alias = motion_controller
    mc.motion.set_velocity(
        velocity_value, servo=alias, target_latch=False)
    test_vel = mc.communication.get_register(
        VELOCITY_SET_POINT_REGISTER, servo=alias)
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
        ACTUAL_VELOCITY_REGISTER, servo=alias)
    assert pytest.approx(test_vel, abs=0.1) == velocity_value


@pytest.mark.smoke
@pytest.mark.parametrize("current_value", [
    0.5, 1, 0, -0.5
])
def test_set_current_quadrature(motion_controller, current_value):
    mc, alias = motion_controller
    mc.motion.set_current_quadrature(
        current_value, servo=alias)
    test_current = mc.communication.get_register(
        CURRENT_QUADRATURE_SET_POINT_REGISTER, servo=alias)
    assert pytest.approx(test_current) == current_value


@pytest.mark.smoke
@pytest.mark.parametrize("current_value", [
    0.5, 1, 0, -0.5
])
def test_set_current_direct(motion_controller, current_value):
    mc, alias = motion_controller
    mc.motion.set_current_direct(
        current_value, servo=alias)
    test_current = mc.communication.get_register(
        CURRENT_DIRECT_SET_POINT_REGISTER, servo=alias)
    assert pytest.approx(test_current) == current_value


@pytest.mark.smoke
@pytest.mark.parametrize("voltage_value", [
    0.5, 1, 0, -0.5
])
def test_set_voltage_quadrature(motion_controller, voltage_value):
    mc, alias = motion_controller
    mc.motion.set_voltage_quadrature(
        voltage_value, servo=alias)
    test_voltage = mc.communication.get_register(
        VOLTAGE_QUADRATURE_SET_POINT_REGISTER, servo=alias)
    assert pytest.approx(test_voltage) == voltage_value


@pytest.mark.smoke
@pytest.mark.parametrize("voltage_value", [
    0.5, 1, 0, -0.5
])
def test_set_voltage_direct(motion_controller, voltage_value):
    mc, alias = motion_controller
    mc.motion.set_voltage_direct(
        voltage_value, servo=alias)
    test_voltage = mc.communication.get_register(
        VOLTAGE_DIRECT_SET_POINT_REGISTER, servo=alias)
    assert pytest.approx(test_voltage) == voltage_value


@pytest.mark.smoke
@pytest.mark.parametrize("init_v, final_v, total_t, t, result", [
    (0, 1, 2, [1], [0.5]),
    (0, -2, 2, [1], [-1]),
    (-2, -4, 2, [1, 2], [-3, -4]),
    (-1, 1, 10, [2.5, 5, 7.5], [-0.5, 0, 0.5]),
    (0, 10, 10, [1, 2, 3], [1, 2, 3]),
    (0, 10, 10, [20], [10]),
    (-2.54, 23.45, 34, [2, 16.7, 44], [-1.01117647, 10.2256764, 23.45]),
])
def test_ramp_generator(mocker, init_v, final_v, total_t, t, result):
    mocker.patch('time.time', side_effect=[0, *t])
    generator = Motion.ramp_generator(init_v, final_v, total_t)
    first_val = next(generator)
    assert pytest.approx(first_val) == init_v
    for result_v in result:
        test_result = next(generator)
        assert pytest.approx(test_result) == result_v


@pytest.mark.parametrize("position_value", [
    1000, 0, -1000, 4000
])
def test_get_actual_position(motion_controller, position_value):
    mc, alias = motion_controller
    pos_res = mc.configuration.get_position_feedback_resolution(servo=alias)
    mc.motion.set_operation_mode(
        OperationMode.PROFILE_POSITION, servo=alias)
    mc.motion.motor_enable(servo=alias)
    mc.motion.move_to_position(
        position_value, servo=alias, blocking=True)
    test_position = mc.motion.get_actual_position(servo=alias)
    assert pytest.approx(
        test_position, abs=pos_res * POSITION_PERCENTAGE_ERROR_ALLOWED/100
    ) == position_value


@pytest.mark.parametrize("velocity_value", [
    1, 0, -1
])
def test_get_actual_velocity(motion_controller, velocity_value):
    mc, alias = motion_controller
    mc.motion.set_operation_mode(
        OperationMode.PROFILE_VELOCITY, servo=alias)
    mc.motion.motor_enable(servo=alias)
    mc.motion.set_velocity(
        velocity_value, servo=alias, blocking=True)
    time.sleep(1)
    test_velocity = mc.motion.get_actual_velocity(servo=alias)
    reg_value = mc.communication.get_register(ACTUAL_VELOCITY_REGISTER,
                                              servo=alias)
    assert pytest.approx(test_velocity, 0.1) == reg_value


@pytest.mark.smoke
def test_get_actual_current_direct(mocker, motion_controller):
    mc, alias = motion_controller
    patch_get_register = mocker.patch(
        'ingeniamotion.communication.Communication.get_register')
    mc.motion.get_actual_current_direct(servo=alias)
    patch_get_register.assert_called_once_with(ACTUAL_DIRECT_CURRENT_REGISTER, servo=alias, axis=1)


@pytest.mark.smoke
def test_get_actual_current_quadrature(mocker, motion_controller):
    mc, alias = motion_controller
    patch_get_register = mocker.patch(
        'ingeniamotion.communication.Communication.get_register')
    mc.motion.get_actual_current_quadrature(servo=alias)
    patch_get_register.assert_called_once_with(ACTUAL_QUADRATURE_CURRENT_REGISTER, servo=alias, axis=1)


@pytest.mark.smoke
def test_wait_for_position_timeout(motion_controller):
    timeout_value = 2
    mc, alias = motion_controller
    init_time = time.time()
    with pytest.raises(IMTimeoutError):
        mc.motion.wait_for_position(10000, servo=alias, timeout=timeout_value)
    final_time = time.time()
    assert pytest.approx(final_time-init_time, abs=0.1) == timeout_value


@pytest.mark.smoke
def test_wait_for_velocity_timeout(motion_controller):
    timeout_value = 2
    mc, alias = motion_controller
    init_time = time.time()
    with pytest.raises(IMTimeoutError):
        mc.motion.wait_for_velocity(10000, servo=alias, timeout=timeout_value)
    final_time = time.time()
    assert pytest.approx(final_time-init_time, abs=0.1) == timeout_value


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
    mc.motion.set_internal_generator_configuration(op_mode, servo=alias)
    mc.motion.motor_enable(servo=alias)
    if op_mode == OperationMode.CURRENT:
        mc.motion.current_quadrature_ramp(1, 1, servo=alias)
        mc.motion.current_direct_ramp(1, 1, servo=alias)
    else:
        mc.motion.voltage_quadrature_ramp(1, 1, servo=alias)
        mc.motion.voltage_direct_ramp(1, 1, servo=alias)
    time.sleep(1)
    initial_position = mc.motion.get_actual_position(servo=alias)
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

import time
from typing import Any

import numpy as np
import pytest
from ingenialink import exceptions

from ingeniamotion.enums import OperationMode
from ingeniamotion.exceptions import IMTimeoutError
from ingeniamotion.motion import Motion
from tests.conftest import mean_actual_velocity_position

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


def delayed_function_return(delay_s: int, first_response: Any, delayed_response: Any):
    """Generates two different returns, second one after a delay.

    Args:
        delay_s: Delay for second return in seconds.
        first_response: Return before delay.
        delayed_response: Return after delay.

    Yields:
        Any: Return specified as an argument.
    """
    start_time = time.time()
    while True:
        if time.time() - start_time < delay_s:
            yield first_response
        else:
            yield delayed_response


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_target_latch(mc, alias):
    mc.communication.set_register(PROFILER_LATCHING_MODE_REGISTER, 0x40, servo=alias)
    mc.motion.motor_enable(servo=alias)
    pos_res = mc.configuration.get_position_feedback_resolution(servo=alias)
    init_pos = int(mean_actual_velocity_position(mc, alias))
    mc.motion.move_to_position(init_pos + pos_res, servo=alias, target_latch=False)
    test_act_pos = mean_actual_velocity_position(mc, alias)
    time.sleep(1)
    rel_tolerance = pos_res * POSITION_PERCENTAGE_ERROR_ALLOWED / 100
    assert pytest.approx(init_pos, rel_tolerance) == test_act_pos
    mc.motion.target_latch(servo=alias)
    time.sleep(1)
    test_act_pos = mean_actual_velocity_position(mc, alias)
    assert pytest.approx(init_pos + pos_res, rel_tolerance) == test_act_pos


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("operation_mode", list(OperationMode))
def test_set_operation_mode(mc, alias, operation_mode):
    mc.motion.set_operation_mode(operation_mode, servo=alias)
    test_op = mc.communication.get_register(OPERATION_MODE_REGISTER, servo=alias)
    assert operation_mode.value == test_op


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("operation_mode", list(OperationMode))
def test_get_operation_mode(mc, alias, operation_mode):
    mc.communication.set_register(OPERATION_MODE_REGISTER, operation_mode, servo=alias)
    test_op = mc.motion.get_operation_mode(servo=alias)
    assert test_op == operation_mode.value


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
def test_motor_enable(mc, alias):
    mc.motion.motor_enable(servo=alias)
    assert mc.configuration.is_motor_enabled(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize(
    "uid, value, exception_type, message",
    [
        ("DRV_PROT_USER_UNDER_VOLT", 100, exceptions.ILError, "User Under-voltage detected"),
        (
            "DRV_PROT_USER_OVER_TEMP",
            1,
            exceptions.ILError,
            "Over-temperature detected (user limit)",
        ),
        ("DRV_PROT_USER_OVER_VOLT", 1, exceptions.ILError, "User Over-voltage detected"),
    ],
)
def test_motor_enable_with_fault(
    motion_controller_teardown, alias, uid, value, exception_type, message
):
    mc = motion_controller_teardown
    mc.communication.set_register(uid, value, alias)
    with pytest.raises(exception_type) as excinfo:
        mc.motion.motor_enable(servo=alias)
    if excinfo.type is exceptions.ILIOError:
        # Retrieving the error code failed. Check INGM-522.
        with pytest.raises(exception_type) as excinfo:
            mc.motion.motor_enable(servo=alias)
    assert str(excinfo.value) == f"An error occurred enabling motor. Reason: {message}"


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize(
    "uid, value, exception_type, message, timeout",
    [
        # Under-Voltage Error is not triggered due to timeout error
        (
            "DRV_PROT_USER_UNDER_VOLT",
            100,
            exceptions.ILTimeoutError,
            "Error trigger timeout exceeded.",
            2,
        ),
        # Under-Voltage Error is triggered successfully
        ("DRV_PROT_USER_UNDER_VOLT", 100, exceptions.ILError, "User Under-voltage detected", 6),
    ],
)
def test_motor_enable_with_delayed_fault(
    mocker, motion_controller_teardown, alias, uid, value, exception_type, message, timeout
):
    mc = motion_controller_teardown
    # Mock function response with delay
    num_errors_before_test = mc.errors.get_number_total_errors(servo=alias, axis=1)
    patch_get_number_total_errors = mocker.patch(
        "ingeniamotion.errors.Errors.get_number_total_errors"
    )
    patch_get_number_total_errors.side_effect = delayed_function_return(
        4, num_errors_before_test, num_errors_before_test + 1
    )

    mc.communication.set_register(uid, value, alias)
    with pytest.raises(exception_type) as excinfo:
        mc.motion.motor_enable(servo=alias, error_timeout=timeout)
    assert str(excinfo.value) == f"An error occurred enabling motor. Reason: {message}"


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("enable_motor", [True, False])
def test_motor_disable(mc, alias, enable_motor):
    if enable_motor:
        mc.motion.motor_enable(servo=alias)
    mc.motion.motor_disable(servo=alias)
    assert not mc.configuration.is_motor_enabled(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
def test_motor_disable_with_fault(motion_controller_teardown, alias):
    uid = "DRV_PROT_USER_UNDER_VOLT"
    value = 100
    exception_type = exceptions.ILError
    mc = motion_controller_teardown
    mc.communication.set_register(uid, value, alias)
    with pytest.raises(exception_type):
        mc.motion.motor_enable(servo=alias)
    mc.motion.motor_disable(servo=alias)
    assert not mc.configuration.is_motor_enabled(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
def test_fault_reset(motion_controller_teardown, alias):
    mc = motion_controller_teardown
    uid = "DRV_PROT_USER_UNDER_VOLT"
    value = 100
    mc.communication.set_register(uid, value, alias)
    assert not mc.errors.is_fault_active(servo=alias)
    with pytest.raises(exceptions.ILError):
        mc.motion.motor_enable(servo=alias)
    try:
        is_fault_active = mc.errors.is_fault_active(servo=alias)
    except exceptions.ILIOError:
        # Reading the status word failed. Check INGM-526.
        is_fault_active = mc.errors.is_fault_active(servo=alias)
    assert is_fault_active
    mc.motion.fault_reset(servo=alias)
    assert not mc.errors.is_fault_active(servo=alias)


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("position_value", [1000, 0, -1000, 4000])
def test_set_position(mc, alias, position_value):
    mc.motion.move_to_position(position_value, servo=alias, target_latch=False, blocking=False)
    test_position = mc.communication.get_register(POSITION_SET_POINT_REGISTER, servo=alias)
    assert test_position == position_value


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("position_value", [1000, 0, -1000, 4000])
def test_move_position(mc, alias, position_value):
    pos_res = mc.configuration.get_position_feedback_resolution(servo=alias)
    mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION, servo=alias)
    mc.motion.motor_enable(servo=alias)
    mc.motion.move_to_position(position_value, servo=alias, blocking=True, timeout=10)
    test_position = mean_actual_velocity_position(mc, alias)
    pos_tolerance = pos_res * POSITION_PERCENTAGE_ERROR_ALLOWED / 100
    assert pytest.approx(position_value, abs=pos_tolerance) == test_position


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("velocity_value", [0.5, 1, 0, -0.5])
def test_set_velocity(mc, alias, velocity_value):
    mc.motion.set_velocity(velocity_value, servo=alias, target_latch=False)
    test_vel = mc.communication.get_register(VELOCITY_SET_POINT_REGISTER, servo=alias)
    assert test_vel == velocity_value


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("velocity_value", [0.5, 1, 0, -0.5])
def test_set_velocity_blocking(mc, alias, velocity_value):
    mc.motion.set_operation_mode(OperationMode.PROFILE_VELOCITY, servo=alias)
    mc.motion.motor_enable(servo=alias)
    mc.motion.set_velocity(velocity_value, servo=alias, blocking=True, timeout=10)
    time.sleep(1)
    test_vel = mean_actual_velocity_position(mc, alias, velocity=True)
    assert pytest.approx(velocity_value, abs=0.1) == test_vel


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("current_value", [0.5, 1, 0, -0.5])
def test_set_current_quadrature(mc, alias, current_value):
    mc.motion.set_current_quadrature(current_value, servo=alias)
    test_current = mc.communication.get_register(CURRENT_QUADRATURE_SET_POINT_REGISTER, servo=alias)
    assert pytest.approx(current_value) == test_current


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("current_value", [0.5, 1, 0, -0.5])
def test_set_current_direct(mc, alias, current_value):
    mc.motion.set_current_direct(current_value, servo=alias)
    test_current = mc.communication.get_register(CURRENT_DIRECT_SET_POINT_REGISTER, servo=alias)
    assert pytest.approx(current_value) == test_current


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("voltage_value", [0.5, 1, 0, -0.5])
def test_set_voltage_quadrature(mc, alias, voltage_value):
    mc.motion.set_voltage_quadrature(voltage_value, servo=alias)
    test_voltage = mc.communication.get_register(VOLTAGE_QUADRATURE_SET_POINT_REGISTER, servo=alias)
    assert pytest.approx(voltage_value) == test_voltage


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize("voltage_value", [0.5, 1, 0, -0.5])
def test_set_voltage_direct(mc, alias, voltage_value):
    mc.motion.set_voltage_direct(voltage_value, servo=alias)
    test_voltage = mc.communication.get_register(VOLTAGE_DIRECT_SET_POINT_REGISTER, servo=alias)
    assert pytest.approx(voltage_value) == test_voltage


@pytest.mark.virtual
@pytest.mark.smoke
@pytest.mark.parametrize(
    "init_v, final_v, total_t, t, result",
    [
        (0, 1, 2, [1], [0.5]),
        (0, -2, 2, [1], [-1]),
        (-2, -4, 2, [1, 2], [-3, -4]),
        (-1, 1, 10, [2.5, 5, 7.5], [-0.5, 0, 0.5]),
        (0, 10, 10, [1, 2, 3], [1, 2, 3]),
        (0, 10, 10, [20], [10]),
        (-2.54, 23.45, 34, [2, 16.7, 44], [-1.01117647, 10.2256764, 23.45]),
    ],
)
def test_ramp_generator(mocker, init_v, final_v, total_t, t, result):
    mocker.patch("time.time", side_effect=[0, *t])
    generator = Motion.ramp_generator(init_v, final_v, total_t)
    first_val = next(generator)
    assert pytest.approx(init_v) == first_val
    for result_v in result:
        test_result = next(generator)
        assert pytest.approx(result_v) == test_result


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("position_value", [-4000, -1000, 1000, 4000])
def test_get_actual_position(mc, alias, position_value):
    mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION, servo=alias)
    mc.motion.motor_enable(servo=alias)
    mc.motion.move_to_position(position_value, servo=alias, blocking=True, timeout=10)
    n_samples = 200
    test_position = np.zeros(n_samples)
    reg_value = np.zeros(n_samples)
    for sample_ix in range(n_samples):
        test_position[sample_ix] = mc.motion.get_actual_position(servo=alias)
        reg_value[sample_ix] = mc.communication.get_register(ACTUAL_POSITION_REGISTER, servo=alias)
    assert np.abs(np.mean(test_position) - np.mean(reg_value)) < 0.5


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.parametrize("velocity_value", [1, 0, -1])
def test_get_actual_velocity(mc, alias, velocity_value):
    mc.motion.set_operation_mode(OperationMode.PROFILE_VELOCITY, servo=alias)
    mc.motion.motor_enable(servo=alias)
    mc.motion.set_velocity(velocity_value, servo=alias, blocking=True, timeout=10)
    time.sleep(2)
    n_samples = 200
    test_velocity = np.zeros(n_samples)
    reg_value = np.zeros(n_samples)
    for sample_ix in range(n_samples):
        test_velocity[sample_ix] = mc.motion.get_actual_velocity(servo=alias)
        reg_value[sample_ix] = mc.communication.get_register(ACTUAL_VELOCITY_REGISTER, servo=alias)
    assert np.abs(np.mean(test_velocity) - np.mean(reg_value)) < 0.1


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_actual_current_direct(mocker, mc, alias):
    patch_get_register = mocker.patch("ingeniamotion.communication.Communication.get_register")
    patch_get_register.return_value = 2.0
    mc.motion.get_actual_current_direct(servo=alias)
    patch_get_register.assert_called_once_with(ACTUAL_DIRECT_CURRENT_REGISTER, servo=alias, axis=1)


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_actual_current_quadrature(mocker, mc, alias):
    patch_get_register = mocker.patch("ingeniamotion.communication.Communication.get_register")
    patch_get_register.return_value = 2.0
    mc.motion.get_actual_current_quadrature(servo=alias)
    patch_get_register.assert_called_once_with(
        ACTUAL_QUADRATURE_CURRENT_REGISTER, servo=alias, axis=1
    )


@pytest.mark.parametrize(
    "function",
    [
        "wait_for_position",
        "wait_for_velocity",
    ],
)
@pytest.mark.virtual
def test_wait_for_function_timeout(mc, alias, function):
    timeout_value = 2
    init_time = time.time()
    with pytest.raises(IMTimeoutError):
        getattr(mc.motion, function)(1000, servo=alias, timeout=timeout_value)
    final_time = time.time()
    assert pytest.approx(timeout_value, abs=0.1) == final_time - init_time


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.smoke
@pytest.mark.parametrize("op_mode", [OperationMode.VOLTAGE, OperationMode.CURRENT])
def test_set_internal_generator_configuration(motion_controller_teardown, alias, op_mode):
    mc = motion_controller_teardown
    mc.motion.set_internal_generator_configuration(op_mode, servo=alias)
    assert op_mode == mc.motion.get_operation_mode(servo=alias)
    assert mc.configuration.get_motor_pair_poles(servo=alias) == 1


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.parametrize("op_mode", [OperationMode.VOLTAGE, OperationMode.CURRENT])
@pytest.mark.parametrize("direction", [-1, 1])
def test_internal_generator_saw_tooth_move(motion_controller_teardown, alias, op_mode, direction):
    mc = motion_controller_teardown
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)
    pos_resolution = mc.configuration.get_position_feedback_resolution(servo=alias)
    mc.motion.set_internal_generator_configuration(op_mode, servo=alias)
    mc.motion.motor_enable(servo=alias)
    if op_mode == OperationMode.CURRENT:
        mc.motion.current_quadrature_ramp(1, 1, servo=alias)
    else:
        mc.motion.voltage_quadrature_ramp(1, 1, servo=alias)
    time.sleep(1)
    initial_position = mc.motion.get_actual_position(servo=alias)
    mc.motion.internal_generator_saw_tooth_move(direction, 1, 1, servo=alias)
    time.sleep(2)
    final_position = mc.motion.get_actual_position(servo=alias)
    total_movement = final_position - initial_position
    expected_movement = pos_resolution * direction / pair_poles
    assert (
        abs(total_movement - expected_movement)
        < pos_resolution * POSITION_PERCENTAGE_ERROR_ALLOWED / 100
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.parametrize("op_mode", [OperationMode.VOLTAGE, OperationMode.CURRENT])
@pytest.mark.parametrize("direction", [-1, 1])
def test_internal_generator_constant_move(motion_controller_teardown, alias, op_mode, direction):
    mc = motion_controller_teardown
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)
    pos_resolution = mc.configuration.get_position_feedback_resolution(servo=alias)
    cycle_pos = pos_resolution / pair_poles
    mc.motion.set_internal_generator_configuration(op_mode, servo=alias)
    mc.motion.motor_enable(servo=alias)
    if op_mode == OperationMode.CURRENT:
        mc.motion.current_quadrature_ramp(1, 2, servo=alias)
    else:
        mc.motion.voltage_quadrature_ramp(1, 2, servo=alias)
    time.sleep(1)
    mc.motion.internal_generator_constant_move(0, servo=alias)
    initial_position = mc.motion.get_actual_position(servo=alias)
    list_values = np.linspace(0, 1, 5) if direction > 0 else np.linspace(1, 0, 5)
    for value in list_values:
        mc.motion.internal_generator_constant_move(value, servo=alias)
        time.sleep(1)
        final_position = mc.motion.get_actual_position(servo=alias)
        total_movement = final_position - initial_position
        expected_movement = cycle_pos * value if direction > 0 else cycle_pos * (value - 1)
        assert (
            abs(total_movement - expected_movement)
            < pos_resolution * POSITION_PERCENTAGE_ERROR_ALLOWED / 100
        )


@pytest.mark.parametrize(
    "function",
    [
        "target_latch",
        "get_operation_mode",
        "get_actual_position",
        "get_actual_velocity",
        "get_actual_current_direct",
        "get_actual_current_quadrature",
    ],
)
@pytest.mark.virtual
def test_wrong_type_exception(mocker, mc, alias, function):
    mocker.patch.object(mc.communication, "get_register", return_value="invalid_value")
    with pytest.raises(TypeError):
        getattr(mc.motion, function)(servo=alias)


@pytest.mark.virtual
def test_set_internal_generator_configuration_exception(mc, alias):
    with pytest.raises(ValueError):
        mc.motion.set_internal_generator_configuration(OperationMode.VELOCITY, servo=alias)

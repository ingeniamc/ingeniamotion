import pytest

from ingeniamotion.enums import OperationMode

POS_PID_KP_VALUE = 0.1


# def test_target_latch():
#     assert False


@pytest.mark.parametrize("operation_mode", list(OperationMode))
def test_set_operation_mode(servo_default, operation_mode):
    mc = servo_default
    mc.motion.set_operation_mode(operation_mode)
    test_op = mc.communication.get_register("DRV_OP_CMD")
    assert operation_mode.value == test_op


@pytest.mark.parametrize("operation_mode", list(OperationMode))
def test_get_operation_mode(servo_default, operation_mode):
    mc = servo_default
    mc.communication.set_register("DRV_OP_CMD", operation_mode)
    test_op = mc.motion.get_operation_mode()
    assert test_op == operation_mode.value


def test_motor_enable(servo_default):
    mc = servo_default
    mc.motion.motor_enable()
    assert mc.configuration.is_motor_enabled()
    mc.motion.motor_disable()


def test_motor_disable(servo_default):
    mc = servo_default
    mc.motion.motor_enable()
    mc.motion.motor_disable()
    assert not mc.configuration.is_motor_enabled()


@pytest.mark.parametrize("position_value", [
    1000, 0, -1000, 4000
])
def test_set_position(servo_default, position_value):
    mc = servo_default
    mc.motion.move_to_position(position_value, target_latch=False, blocking=False)
    test_position = mc.communication.get_register("CL_POS_SET_POINT_VALUE")
    assert test_position == position_value


@pytest.mark.parametrize("position_value", [
    1000, 0, -1000, 4000
])
def test_move_position(servo_default, position_value):
    mc = servo_default
    mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION)
    mc.motion.motor_enable()
    mc.motion.move_to_position(position_value, blocking=True)
    test_position = mc.communication.get_register("CL_POS_SET_POINT_VALUE")
    assert test_position == position_value
    mc.motion.motor_disable()


@pytest.mark.parametrize("velocity_value", [
    0.5, 1, 0, -0.5
])
def test_set_velocity(servo_default, velocity_value):
    mc = servo_default
    mc.motion.set_velocity(velocity_value, target_latch=False)
    test_vel = mc.communication.get_register("CL_VEL_SET_POINT_VALUE")
    assert test_vel == velocity_value


@pytest.mark.parametrize("current_value", [
    0.5, 1, 0, -0.5
])
def test_set_current_quadrature(servo_default, current_value):
    mc = servo_default
    mc.motion.set_current_quadrature(current_value)
    test_current = mc.communication.get_register("CL_CUR_Q_SET_POINT")
    assert test_current == current_value


@pytest.mark.parametrize("current_value", [
    0.5, 1, 0, -0.5
])
def test_set_current_direct(servo_default, current_value):
    mc = servo_default
    mc.motion.set_current_direct(current_value)
    test_current = mc.communication.get_register("CL_CUR_D_SET_POINT")
    assert test_current == current_value


@pytest.mark.parametrize("voltage_value", [
    0.5, 1, 0, -0.5
])
def test_set_voltage_quadrature(servo_default, voltage_value):
    mc = servo_default
    mc.motion.set_voltage_quadrature(voltage_value)
    test_current = mc.communication.get_register("CL_VOL_Q_SET_POINT")
    assert test_current == voltage_value


@pytest.mark.parametrize("voltage_value", [
    0.5, 1, 0, -0.5
])
def test_set_voltage_direct(servo_default, voltage_value):
    mc = servo_default
    mc.motion.set_voltage_direct(voltage_value)
    test_current = mc.communication.get_register("CL_VOL_D_SET_POINT")
    assert test_current == voltage_value


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

@pytest.mark.develop
def test_ramp_generator():

    assert False


@pytest.mark.parametrize("position_value", [
    1000, 0, -1000, 4000
])
def test_get_actual_position(servo_default, position_value):
    mc = servo_default
    mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION)
    mc.motion.motor_enable()
    mc.motion.move_to_position(position_value, blocking=True)
    test_position = mc.motion.get_actual_position()
    assert abs(test_position - position_value) < 10
    mc.motion.motor_disable()


# def test_wait_for_position():
#     assert False
#
#
# def test_wait_for_velocity():
#     assert False


@pytest.mark.parametrize("op_mode", [
    OperationMode.VOLTAGE, OperationMode.CURRENT
])
def test_set_internal_generator_configuration(servo_default, op_mode):
    mc = servo_default
    mc.motion.set_internal_generator_configuration(op_mode)
    assert op_mode == mc.motion.get_operation_mode()
    assert 1 == mc.configuration.get_motor_pair_poles()
    assert


@pytest.mark.parametrize("op_mode", [
    OperationMode.VOLTAGE, OperationMode.CURRENT
])
def test_internal_generator_saw_tooth_move(servo_default, op_mode):
    mc = servo_default

    mc.motion.set_internal_generator_configuration(op_mode)


def test_internal_generator_constant_move():
    assert False

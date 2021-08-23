import pytest

from ingeniamotion.enums import HomingMode


HOMING_MODE_REGISTER = "HOM_MODE"
HOMING_OFFSET_REGISTER = "HOM_OFFSET"
HOMING_TIMEOUT_REGISTER = "HOM_SEQ_TIMEOUT"


@pytest.fixture
def initial_position(motion_controller):
    mc, alias = motion_controller
    mc.motion.motor_enable(servo=alias)
    position = 5000
    mc.motion.move_to_position(position, servo=alias, blocking=True)
    mc.motion.motor_disable(servo=alias)
    return position


@pytest.mark.develop
@pytest.mark.parametrize("homing_mode", list(HomingMode))
def test_set_homing_mode(motion_controller, homing_mode):
    mc, alias = motion_controller
    mc.configuration.set_homing_mode(homing_mode, servo=alias)
    test_homing_mode = mc.communication.get_register(
        HOMING_MODE_REGISTER, servo=alias)
    assert test_homing_mode == homing_mode


@pytest.mark.develop
@pytest.mark.parametrize("homing_offset", [0, 10, 500, -12, -100, 1000])
def test_set_homing_offset(motion_controller, homing_offset):
    mc, alias = motion_controller
    mc.configuration.set_homing_offset(homing_offset, servo=alias)
    test_homing_offset = mc.communication.get_register(
        HOMING_OFFSET_REGISTER, servo=alias)
    assert test_homing_offset == homing_offset


@pytest.mark.develop
@pytest.mark.parametrize("homing_timeout", [0, 10, 500, 1000, 5000, 10000])
def test_set_homing_timeout(motion_controller, homing_timeout):
    mc, alias = motion_controller
    mc.configuration.set_homing_timeout(homing_timeout, servo=alias)
    test_homing_timeout = mc.communication.get_register(
        HOMING_TIMEOUT_REGISTER, servo=alias)
    assert test_homing_timeout == homing_timeout


@pytest.mark.develop
@pytest.mark.parametrize("homing_offset", [0, 1000])
def test_homing_on_current_position(motion_controller, initial_position, homing_offset):
    mc, alias = motion_controller
    mc.configuration.homing_on_current_position(homing_offset, servo=alias)
    assert mc.motion.get_actual_position(servo=alias) == homing_offset


def test_homing_on_switch_limit():
    assert False


def test_homing_on_index_pulse():
    assert False


def test_homing_on_switch_limit_and_index_pulse():
    assert False

import logging
import time
from collections.abc import Callable

import pytest

from ingeniamotion.enums import HomingMode, OperationMode, SensorType
from tests.conftest import mean_actual_velocity_position, refresh_registers_for_test_rollback

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
HOMING_STATUS_POLL_INTERVAL_S = 0.01

RELATIVE_ERROR_ALLOWED = 3e-2

logger = logging.getLogger(__name__)


def _log_initial_position_state(mc, alias, stage):
    try:
        status_word = mc.configuration.get_status_word(servo=alias)
    except Exception as error:
        status_word = f"unavailable ({type(error).__name__}: {error})"
    try:
        actual_position = mc.motion.get_actual_position(servo=alias)
    except Exception as error:
        actual_position = f"unavailable ({type(error).__name__}: {error})"
    logger.info(
        "initial_position %s: status_word=%s, actual_position=%s",
        stage,
        status_word,
        actual_position,
    )


def _run_initial_position_stage(mc, alias, stage: str, action: Callable[[], object]):
    logger.info("initial_position: starting %s", stage)
    try:
        result = action()
    except Exception:
        _log_initial_position_state(mc, alias, f"{stage} failed")
        raise
    logger.info("initial_position: completed %s with result=%r", stage, result)
    return result


@pytest.fixture
def initial_position(mc, alias):
    _run_initial_position_stage(
        mc,
        alias,
        "set profile-position mode",
        lambda: mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION, servo=alias),
    )
    position_resolution = _run_initial_position_stage(
        mc,
        alias,
        "read position-feedback resolution",
        lambda: mc.configuration.get_position_feedback_resolution(servo=alias),
    )
    position = position_resolution // 2
    _log_initial_position_state(mc, alias, "before motor enable")
    try:
        _run_initial_position_stage(
            mc,
            alias,
            "motor enable",
            lambda: mc.motion.motor_enable(servo=alias),
        )
        _run_initial_position_stage(
            mc,
            alias,
            "blocking move",
            lambda: mc.motion.move_to_position(position, servo=alias, blocking=True, timeout=5),
        )
    finally:
        _run_initial_position_stage(
            mc,
            alias,
            "motor disable",
            lambda: mc.motion.motor_disable(servo=alias),
        )
    return position


@pytest.mark.virtual
@pytest.mark.parametrize("homing_mode", list(HomingMode))
def test_set_homing_mode(mc, alias, homing_mode):
    mc.configuration.set_homing_mode(homing_mode, servo=alias)
    test_homing_mode = mc.communication.get_register(HOMING_MODE_REGISTER, servo=alias)
    assert test_homing_mode == homing_mode


@pytest.mark.virtual
@pytest.mark.parametrize("homing_offset", [0, 10, 500, -12, -100, 1000])
def test_set_homing_offset(mc, alias, homing_offset):
    mc.configuration.set_homing_offset(homing_offset, servo=alias)
    test_homing_offset = mc.communication.get_register(HOMING_OFFSET_REGISTER, servo=alias)
    assert test_homing_offset == homing_offset


@pytest.mark.virtual
@pytest.mark.parametrize("homing_timeout", [0, 10, 500, 1000, 5000, 10000])
def test_set_homing_timeout(mc, alias, homing_timeout):
    mc.configuration.set_homing_timeout(homing_timeout, servo=alias)
    test_homing_timeout = mc.communication.get_register(HOMING_TIMEOUT_REGISTER, servo=alias)
    assert test_homing_timeout == homing_timeout


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.parametrize("homing_offset", [0, 1000])
@pytest.mark.usefixtures("initial_position")
# https://novantamotion.atlassian.net/browse/INGM-773
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
@pytest.mark.not_valid_for_product(part_number="EVE-*")
def test_homing_on_current_position(servo, mc, alias, homing_offset):
    with refresh_registers_for_test_rollback(
        servo,
        [
            "COMMU_ANGLE_OFFSET",
        ],
    ):
        mc.configuration.homing_on_current_position(homing_offset, servo=alias)
        feedback_resolution = mc.configuration.get_position_feedback_resolution(servo=alias)
        assert pytest.approx(
            homing_offset,
            abs=feedback_resolution * RELATIVE_ERROR_ALLOWED,
        ) == mc.motion.get_actual_position(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("initial_position")
@pytest.mark.parametrize("direction", [1, 0])
# https://novantamotion.atlassian.net/browse/INGM-775
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
@pytest.mark.not_valid_for_product(part_number="EVE-*")
def test_homing_on_switch_limit(servo, mc, alias, direction):
    with refresh_registers_for_test_rollback(
        servo,
        [
            "COMMU_ANGLE_OFFSET",
        ],
    ):
        homing_offset = 10
        homing_timeout = 5000
        search_vel = 10.0
        zero_vel = 1.0
        switch = 2
        mc.configuration.homing_on_switch_limit(
            homing_offset,
            direction,
            switch,
            homing_timeout,
            search_vel,
            zero_vel,
            servo=alias,
            motor_enable=False,
        )
        test_offset = mc.communication.get_register(HOMING_OFFSET_REGISTER, servo=alias)
        test_timeout = mc.communication.get_register(HOMING_TIMEOUT_REGISTER, servo=alias)
        test_hom_mode = mc.communication.get_register(HOMING_MODE_REGISTER, servo=alias)
        test_op_mode = mc.motion.get_operation_mode(servo=alias)
        test_search_vel = mc.communication.get_register(
            HOMING_SEARCH_VELOCITY_REGISTER, servo=alias
        )
        test_zero_vel = mc.communication.get_register(HOMING_ZERO_VELOCITY_REGISTER, servo=alias)
        switch_register = (
            POSITIVE_HOMING_SWITCH_REGISTER if direction == 1 else NEGATIVE_HOMING_SWITCH_REGISTER
        )
        test_switch = mc.communication.get_register(switch_register, servo=alias)
        assert test_offset == homing_offset
        assert test_timeout == homing_timeout
        if direction == 1:
            assert test_hom_mode == HomingMode.POSITIVE_LIMIT_SWITCH
        elif direction == 0:
            assert test_hom_mode == HomingMode.NEGATIVE_LIMIT_SWITCH
        assert test_op_mode == OperationMode.HOMING
        assert pytest.approx(zero_vel) == test_zero_vel
        assert pytest.approx(search_vel) == test_search_vel
        assert test_switch == switch


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("initial_position")
# https://novantamotion.atlassian.net/browse/INGM-776
@pytest.mark.not_valid_for_product(part_number="CAP-*")
@pytest.mark.not_valid_for_product(part_number="EVE-*")
def test_homing_on_switch_limit_timeout(servo, mc, alias):
    with refresh_registers_for_test_rollback(
        servo,
        [
            "COMMU_ANGLE_OFFSET",
        ],
    ):
        homing_offset = 10
        homing_timeout = 5000
        search_vel = 10.0
        zero_vel = 1.0
        switch = 2
        direction = 1
        mc.configuration.homing_on_switch_limit(
            homing_offset,
            direction,
            switch,
            homing_timeout,
            search_vel,
            zero_vel,
            servo=alias,
            motor_enable=False,
        )
        time.sleep(homing_timeout / 1000)
        assert pytest.approx(0, abs=0.05) == mean_actual_velocity_position(mc, alias, velocity=True)
        mc.motion.motor_enable(servo=alias)
        mc.motion.target_latch(servo=alias)
        time.sleep(1)
        assert abs(mean_actual_velocity_position(mc, alias, velocity=True)) > 0.05
        time.sleep(homing_timeout / 1000)
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


def _format_homing_status_sequence(status_sequence: list[tuple[float, int]]) -> str:
    if not status_sequence:
        return "no status samples"
    return " -> ".join(
        f"{elapsed:.3f}s: {status_word:#06x}" for elapsed, status_word in status_sequence
    )


def __check_homing_was_successful(mc, alias, timeout_ms) -> tuple[bool, str]:
    start_time = time.monotonic()
    deadline = start_time + timeout_ms / 1000
    homing_started = False
    homing_error_seen = False
    status_sequence = []
    last_status_word = None
    while time.monotonic() < deadline:
        status_word = mc.configuration.get_status_word(servo=alias)
        if status_word != last_status_word:
            status_sequence.append((time.monotonic() - start_time, status_word))
            last_status_word = status_word
        homing_error = bool(status_word & STATUS_WORD_HOMING_ERROR_BIT)
        homing_attained = bool(status_word & STATUS_WORD_HOMING_ATTAINED_BIT)
        homing_error_seen |= homing_error
        if not homing_attained:
            homing_started = True
        elif homing_started and not homing_error:
            return True, ""
        time.sleep(HOMING_STATUS_POLL_INTERVAL_S)
    status_sequence_text = _format_homing_status_sequence(status_sequence)
    if homing_error_seen:
        failure_reason = "Homing error bit was set"
    elif not homing_started and last_status_word & STATUS_WORD_HOMING_ATTAINED_BIT:
        failure_reason = "Homing attained bit was already set and never cleared"
    else:
        failure_reason = "Homing attained bit was not observed after homing started"
    diagnostic = f"{failure_reason}. Status sequence: {status_sequence_text}"
    logger.error(diagnostic)
    return False, diagnostic


@pytest.mark.virtual
def test_homing_status_checker_accepts_clear_then_attained(mocker):
    mc = mocker.Mock()
    mc.configuration.get_status_word.side_effect = [0x4237, 0x5237]
    mocker.patch("tests.test_homing.time.sleep")
    mocker.patch(
        "tests.test_homing.time.monotonic",
        side_effect=[0.0, 0.001, 0.002, 0.003, 0.004],
    )

    successful, diagnostic = __check_homing_was_successful(mc, "default", timeout_ms=10)

    assert successful
    assert diagnostic == ""


@pytest.mark.virtual
def test_homing_status_checker_reports_stale_attained_bit(mocker):
    mc = mocker.Mock()
    mc.configuration.get_status_word.return_value = 0x5237
    mocker.patch("tests.test_homing.time.sleep")
    mocker.patch("tests.test_homing.time.monotonic", side_effect=[0.0, 0.001, 0.002, 0.003])

    successful, diagnostic = __check_homing_was_successful(mc, "default", timeout_ms=2)

    assert not successful
    assert "Homing attained bit was already set and never cleared" in diagnostic
    assert "Status sequence:" in diagnostic
    assert "0x5237" in diagnostic


@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("initial_position")
@pytest.mark.parametrize("direction", [1, 0])
@pytest.mark.repeat(100)
def test_homing_on_index_pulse(servo, mc, alias, feedback_list, direction):
    with refresh_registers_for_test_rollback(
        servo,
        [
            "COMMU_ANGLE_OFFSET",
        ],
    ):
        homing_offset = 1000
        homing_timeout = 10000
        zero_vel = 0.1
        motor_enable, sensor_index = __check_index_pulse_is_allowed(feedback_list)
        mc.configuration.homing_on_index_pulse(
            homing_offset,
            direction,
            sensor_index,
            homing_timeout,
            zero_vel,
            servo=alias,
            motor_enable=motor_enable,
        )
        if motor_enable:
            homing_successful, homing_diagnostic = __check_homing_was_successful(
                mc, alias, homing_timeout
            )
            assert homing_successful, homing_diagnostic
        test_offset = mc.communication.get_register(HOMING_OFFSET_REGISTER, servo=alias)
        test_timeout = mc.communication.get_register(HOMING_TIMEOUT_REGISTER, servo=alias)
        test_hom_mode = mc.communication.get_register(HOMING_MODE_REGISTER, servo=alias)
        test_op_mode = mc.motion.get_operation_mode(servo=alias)
        test_zero_vel = mc.communication.get_register(HOMING_ZERO_VELOCITY_REGISTER, servo=alias)
        test_sensor_index = mc.communication.get_register(
            HOMING_INDEX_PULSE_SOURCE_REGISTER, servo=alias
        )
        assert test_offset == homing_offset
        assert test_timeout == homing_timeout
        if direction == 1:
            assert test_hom_mode == HomingMode.POSITIVE_IDX_PULSE
        elif direction == 0:
            assert test_hom_mode == HomingMode.NEGATIVE_IDX_PULSE
        assert test_op_mode == OperationMode.HOMING
        assert pytest.approx(zero_vel) == test_zero_vel
        assert test_sensor_index == sensor_index
        if motor_enable:
            resolution = mc.configuration.get_position_feedback_resolution(servo=alias)
            actual_position = mc.motion.get_actual_position(servo=alias)
            assert (
                pytest.approx(homing_offset, abs=resolution * RELATIVE_ERROR_ALLOWED)
                == actual_position
            )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("initial_position")
@pytest.mark.parametrize("direction", [1, 0])
# https://novantamotion.atlassian.net/browse/INGM-777
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
@pytest.mark.not_valid_for_product(part_number="EVE-*")
def test_homing_on_switch_limit_and_index_pulse(servo, mc, alias, direction):
    with refresh_registers_for_test_rollback(
        servo,
        [
            "COMMU_ANGLE_OFFSET",
        ],
    ):
        homing_offset = 300
        homing_timeout = 3000
        search_vel = 5.0
        zero_vel = 7.0
        switch = 3
        sensor_index = 1
        mc.configuration.homing_on_switch_limit_and_index_pulse(
            homing_offset,
            direction,
            switch,
            sensor_index,
            homing_timeout,
            search_vel,
            zero_vel,
            servo=alias,
            motor_enable=False,
        )
        test_offset = mc.communication.get_register(HOMING_OFFSET_REGISTER, servo=alias)
        test_timeout = mc.communication.get_register(HOMING_TIMEOUT_REGISTER, servo=alias)
        test_hom_mode = mc.communication.get_register(HOMING_MODE_REGISTER, servo=alias)
        test_op_mode = mc.motion.get_operation_mode(servo=alias)
        test_search_vel = mc.communication.get_register(
            HOMING_SEARCH_VELOCITY_REGISTER, servo=alias
        )
        test_zero_vel = mc.communication.get_register(HOMING_ZERO_VELOCITY_REGISTER, servo=alias)
        switch_register = (
            POSITIVE_HOMING_SWITCH_REGISTER if direction == 1 else NEGATIVE_HOMING_SWITCH_REGISTER
        )
        test_switch = mc.communication.get_register(switch_register, servo=alias)
        test_sensor_index = mc.communication.get_register(
            HOMING_INDEX_PULSE_SOURCE_REGISTER, servo=alias
        )
        assert test_offset == homing_offset
        assert test_timeout == homing_timeout
        if direction == 1:
            assert test_hom_mode == HomingMode.POSITIVE_LIMIT_SWITCH_IDX_PULSE
        elif direction == 0:
            assert test_hom_mode == HomingMode.NEGATIVE_LIMIT_SWITCH_IDX_PULSE
        assert test_op_mode == OperationMode.HOMING
        assert pytest.approx(zero_vel) == test_zero_vel
        assert pytest.approx(search_vel) == test_search_vel
        assert test_switch == switch
        assert test_sensor_index == sensor_index

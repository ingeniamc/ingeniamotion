import logging
import random
from collections.abc import Iterator
from itertools import product
from types import TracebackType
from typing import Optional

import pytest
from ingenialink.register import Register
from ingenialink.servo import Servo
from ingenialink.utils._utils import REG_VALUE

from ingeniamotion.enums import SensorType
from ingeniamotion.motion_controller import MotionController
from ingeniamotion.wizard_tests.base_test import TestConfigurationError
from ingeniamotion.wizard_tests.feedbacks_tests.dc_feedback_polarity_test import (
    DCFeedbacksPolarityTest,
)
from ingeniamotion.wizard_tests.feedbacks_tests.dc_feedback_resolution_test import (
    DCFeedbacksResolutionTest,
)
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental1_test import (
    DigitalIncremental1Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.feedback_test import (
    MAX_SIMULTANEOUS_FEEDBACKS,
    _feedback_replacement_order,
)
from tests.conftest import slice_configurations

# Record stop opportunities for every wizard-test integration case in this module.
pytestmark = pytest.mark.usefixtures("stoppable_trace_recorder")
logger = logging.getLogger(__name__)

INCREMENTAL_ENCODER_1_RESOLUTION_REGISTER = "FBK_DIGENC1_RESOLUTION"

COMMUTATION_FEEDBACK_REGISTER = "COMMU_ANGLE_SENSOR"
REFERENCE_FEEDBACK_REGISTER = "COMMU_ANGLE_REF_SENSOR"
VELOCITY_FEEDBACK_REGISTER = "CL_VEL_FBK_SENSOR"
POSITION_FEEDBACK_REGISTER = "CL_POS_FBK_SENSOR"
AUXILIAR_FEEDBACK_REGISTER = "CL_AUX_FBK_SENSOR"

FEEDBACK_SELECTOR_REGISTERS = (
    COMMUTATION_FEEDBACK_REGISTER,
    REFERENCE_FEEDBACK_REGISTER,
    VELOCITY_FEEDBACK_REGISTER,
    POSITION_FEEDBACK_REGISTER,
    AUXILIAR_FEEDBACK_REGISTER,
)


@pytest.mark.virtual
def test_bldc_feedback_setting_raises_on_zero_resolution(mc, alias):
    """BLDC feedback setup must raise TestConfigurationError when resolution is zero."""
    axis = 1
    mc.communication.set_register(
        INCREMENTAL_ENCODER_1_RESOLUTION_REGISTER, 0, servo=alias, axis=axis
    )
    feedback_test = DigitalIncremental1Test(mc, alias, axis)
    with pytest.raises(TestConfigurationError, match="resolution must be greater than 0"):
        feedback_test.setup()


@pytest.mark.virtual
def test_dc_resolution_test_raises_on_zero_resolution(mc, alias):
    """DC resolution test setup must raise TestConfigurationError when resolution is zero."""
    axis = 1
    mc.communication.set_register(
        INCREMENTAL_ENCODER_1_RESOLUTION_REGISTER, 0, servo=alias, axis=axis
    )
    dc_test = DCFeedbacksResolutionTest(mc, SensorType.QEI, alias, axis)
    with pytest.raises(TestConfigurationError, match="resolution must be greater than 0"):
        dc_test.setup()


@pytest.mark.virtual
def test_dc_polarity_test_raises_on_zero_resolution(mc, alias):
    """DC polarity test setup must raise TestConfigurationError when resolution is zero."""
    axis = 1
    mc.communication.set_register(
        INCREMENTAL_ENCODER_1_RESOLUTION_REGISTER, 0, servo=alias, axis=axis
    )
    dc_test = DCFeedbacksPolarityTest(mc, SensorType.QEI, alias, axis)
    with pytest.raises(TestConfigurationError, match="resolution must be greater than 0"):
        dc_test.setup()


@pytest.mark.virtual
@pytest.mark.parametrize(
    "positive_displacement, negative_displacement, expected_output",
    [
        (100.0, -100.0, DigitalIncremental1Test.ResultType.SUCCESS),
        (-100.0, 100.0, DigitalIncremental1Test.ResultType.SUCCESS),
        (100.0, -50.0, DigitalIncremental1Test.ResultType.SYMMETRY_ERROR),
        (-100.0, 50.0, DigitalIncremental1Test.ResultType.SYMMETRY_ERROR),
        (-100.0, -100.0, DigitalIncremental1Test.ResultType.SYMMETRY_ERROR),
        (100.0, 100.0, DigitalIncremental1Test.ResultType.SYMMETRY_ERROR),
        (50.0, -50.0, DigitalIncremental1Test.ResultType.RESOLUTION_ERROR),
        (500.0, -500.0, DigitalIncremental1Test.ResultType.RESOLUTION_ERROR),
        (-50.0, 50.0, DigitalIncremental1Test.ResultType.RESOLUTION_ERROR),
    ],
)
def test_generate_output_different_cases(
    mc, alias, positive_displacement, negative_displacement, expected_output
):
    """Test generate_output returns correct result types for different scenarios."""
    axis = 1
    feedback_test = DigitalIncremental1Test(mc, alias, axis)
    feedback_test.feedback_resolution = 100
    feedback_test.pair_poles = 4
    result = feedback_test.generate_output(positive_displacement, negative_displacement)

    assert result == expected_output


class FeedbackSelectorTracker:
    """Record the drive feedback selectors after every register access.

    Subscribing to the servo register updates makes every intermediate state visible,
    so a sequence of writes that momentarily exceeds the drive feedback limit can be
    detected even if the initial and final states are valid.
    """

    def __init__(self, mc: MotionController, servo: Servo, alias: str, axis: int) -> None:
        self._servo = servo
        self._axis = axis
        self._state = {
            uid: int(mc.communication.get_register(uid, servo=alias, axis=axis))
            for uid in FEEDBACK_SELECTOR_REGISTERS
        }
        self.history = [dict(self._state)]

    def __enter__(self) -> "FeedbackSelectorTracker":
        self._servo.register_update_subscribe(self._on_register_update)
        logger.info("Feedback selector tracking started: %s", self._state)
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self._servo.register_update_unsubscribe(self._on_register_update)
        exception_name = exc_type.__name__ if exc_type is not None else "none"
        logger.info(
            "Feedback selector tracking stopped (exception=%s):\n%s",
            exception_name,
            self.format_history(),
        )

    def _on_register_update(self, servo: Servo, register: Register, value: REG_VALUE) -> None:  # noqa: ARG002
        if register.subnode != self._axis or register.identifier not in self._state:
            return
        sensor = int(value)
        if self._state[register.identifier] == sensor:
            return
        self._state[register.identifier] = sensor
        self.history.append(dict(self._state))
        logger.info(
            "Feedback selector updated: register=%s sensor=%s state=%s",
            register.identifier,
            SensorType(sensor).name if sensor else "DISABLED",
            self._state,
        )

    @property
    def initial_state(self) -> dict[str, int]:
        return self.history[0]

    @property
    def final_state(self) -> dict[str, int]:
        return self.history[-1]

    @property
    def max_simultaneous_feedbacks(self) -> int:
        return max(len(set(state.values())) for state in self.history)

    def format_history(self) -> str:
        return "\n".join(
            f"{len(set(state.values()))} feedbacks: "
            + ", ".join(f"{uid}={SensorType(sensor).name}" for uid, sensor in state.items())
            for state in self.history
        )


def _configuration_shape(
    combination: tuple[SensorType, ...],
) -> tuple[tuple[int, ...], Optional[int]]:
    """Reduce a sensor combination to the scenario it tests, ignoring decoy identity.

    Two combinations that only differ in *which* literal decoy sensor fills a
    non-target register are testing the same scenario, so they should map to the
    same shape: each register's value becomes the index at which its sensor was
    first seen (so the shape only reflects which registers share a sensor), and
    the shape also records which of those indices, if any, is the target sensor
    (QEI) - since "target in this group" and "target absent" are different
    scenarios even when the grouping of registers is otherwise identical.

    Args:
        combination: One sensor per feedback selector register.

    Returns:
        A key that's equal for every combination testing the same scenario.
    """
    first_seen_at: dict[SensorType, int] = {}
    positions = []
    for sensor in combination:
        if sensor not in first_seen_at:
            first_seen_at[sensor] = len(first_seen_at)
        positions.append(first_seen_at[sensor])
    return tuple(positions), first_seen_at.get(SensorType.QEI)


def _feedback_sensor_pool(mc: MotionController, alias: str, axis: int) -> tuple[SensorType, ...]:
    """Read the decoy sensor pool from the registers' own dictionary enums.

    A sensor value can be numerically valid for a register while meaning something
    the drive can't actually satisfy on its own (e.g. feedback relayed from a
    daisy-chained second slave) - the dictionary enum is per-register, so a value
    only goes in the pool if every feedback selector register declares it. The
    internal generator is excluded since the wizard test assigns it to commutation
    itself; including it as a decoy would be redundant and could conflict with
    that assignment.

    Args:
        mc: MotionController instance.
        alias: servo alias to query.
        axis: axis to query.

    Returns:
        The sensor values usable interchangeably across all feedback registers.
    """
    common_values: Optional[set[int]] = None
    for uid in FEEDBACK_SELECTOR_REGISTERS:
        register_values = set(mc.info.register_info(uid, axis=axis, servo=alias).enums.values())
        common_values = (
            register_values if common_values is None else common_values & register_values
        )
    assert common_values is not None
    return tuple(
        SensorType(value)
        for value in sorted(common_values)
        if value in SensorType and SensorType(value) != SensorType.INTGEN
    )


def _feedback_configurations(
    mc: MotionController,
    alias: str,
    axis: int,
) -> Iterator[dict[str, SensorType]]:
    """Generate every selector value combination allowed by the four-feedback limit.

    Each register independently takes one of the sensors the drive's dictionary
    reports as valid across every feedback selector register. Combinations using
    more than MAX_SIMULTANEOUS_FEEDBACKS distinct sensors at once are skipped,
    since the drive doesn't support them, and combinations testing a scenario an
    earlier combination already covered (same register grouping, same target
    placement, different decoy sensor) are skipped too.

    Args:
        mc: MotionController instance.
        alias: servo alias to query.
        axis: axis to query.

    Yields:
        Feedback selector configurations, one per distinct scenario.
    """
    sensors = _feedback_sensor_pool(mc, alias, axis)
    seen_shapes = set()
    configurations = []
    for combination in product(sensors, repeat=len(FEEDBACK_SELECTOR_REGISTERS)):
        if len(set(combination)) > MAX_SIMULTANEOUS_FEEDBACKS:
            continue
        shape = _configuration_shape(combination)
        if shape in seen_shapes:
            continue
        seen_shapes.add(shape)
        configurations.append(dict(zip(FEEDBACK_SELECTOR_REGISTERS, combination)))

    random.shuffle(configurations)
    yield from configurations


def test_feedback_replacement_order_emits_safe_register_values():
    """The emitted writes reach the target without exceeding four sensors."""
    current_feedbacks = dict(
        zip(
            FEEDBACK_SELECTOR_REGISTERS,
            (
                SensorType.QEI,
                SensorType.HALLS,
                SensorType.SINCOS,
                SensorType.SINCOS,
                SensorType.QEI,
            ),
        )
    )
    target_feedbacks = dict(
        zip(
            FEEDBACK_SELECTOR_REGISTERS,
            (
                SensorType.HALLS,
                SensorType.QEI,
                SensorType.INTGEN,
                SensorType.SINCOS,
                SensorType.QEI,
            ),
        )
    )

    state = current_feedbacks.copy()
    writes = list(_feedback_replacement_order(current_feedbacks, target_feedbacks))
    for register, sensor in writes:
        state[register] = sensor
        assert len(set(state.values())) <= MAX_SIMULTANEOUS_FEEDBACKS

    assert state == target_feedbacks
    assert all(register in FEEDBACK_SELECTOR_REGISTERS for register, _sensor in writes)


def test_feedback_replacement_order_reuses_slot_before_new_source():
    """Reuse an active source before selecting a previously inactive source."""
    current_feedbacks = {
        FEEDBACK_SELECTOR_REGISTERS[0]: SensorType.QEI,
        FEEDBACK_SELECTOR_REGISTERS[1]: SensorType.HALLS,
        FEEDBACK_SELECTOR_REGISTERS[2]: SensorType.SINCOS,
        FEEDBACK_SELECTOR_REGISTERS[3]: SensorType.ABS1,
        FEEDBACK_SELECTOR_REGISTERS[4]: SensorType.HALLS,
    }
    target_feedbacks = current_feedbacks.copy()
    target_feedbacks[FEEDBACK_SELECTOR_REGISTERS[0]] = SensorType.SSI2

    assert list(_feedback_replacement_order(current_feedbacks, target_feedbacks)) == [
        (FEEDBACK_SELECTOR_REGISTERS[0], SensorType.HALLS),
        (FEEDBACK_SELECTOR_REGISTERS[0], SensorType.SSI2),
    ]


def test_feedback_replacement_order_is_empty_for_an_unchanged_configuration():
    """No writes are emitted when current and target configurations match."""
    configuration = dict.fromkeys(FEEDBACK_SELECTOR_REGISTERS, SensorType.QEI)

    assert list(_feedback_replacement_order(configuration, configuration)) == []


def test_feedback_replacement_order_rejects_unknown_registers():
    """Only the supported feedback selector registers may be transitioned."""
    configuration = dict.fromkeys(FEEDBACK_SELECTOR_REGISTERS, SensorType.QEI)
    invalid_configuration = {**configuration, "UNKNOWN_REGISTER": SensorType.QEI}

    with pytest.raises(ValueError, match="selector registers"):
        list(_feedback_replacement_order(configuration, invalid_configuration))


@pytest.mark.virtual
@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_feedback_test_respects_the_drive_feedback_limit_across_configurations(
    mc, alias, servo, mocker, subtests, setup_specifier
):
    """The feedback test must never exceed the drive feedback limit.

    The drive rejects a fifth feedback, so neither the setup writes nor the rollback
    performed by the drive context manager may go through such a transient state.
    Both properties are checked from a single run per configuration - running the
    wizard test twice per configuration, once per property, would double this
    test's runtime without adding coverage, since both checks read from the same
    execution trace.
    """
    axis = 1
    mocker.patch.object(
        DigitalIncremental1Test, "loop", return_value=DigitalIncremental1Test.ResultType.SUCCESS
    )

    configurations = list(_feedback_configurations(mc, alias, axis))
    for configuration in slice_configurations(configurations, setup_specifier):
        msg = "_".join(sensor.name for sensor in configuration.values())
        with subtests.test(msg=msg):
            current_feedbacks = {
                uid: SensorType(mc.communication.get_register(uid, servo=alias, axis=axis))
                for uid in FEEDBACK_SELECTOR_REGISTERS
            }
            state = current_feedbacks.copy()
            for uid, sensor in _feedback_replacement_order(state, configuration):
                mc.communication.set_register(uid, sensor, servo=alias, axis=axis)
                state[uid] = sensor
                assert len(set(state.values())) <= MAX_SIMULTANEOUS_FEEDBACKS, (
                    f"Applying {uid} configured more than "
                    f"{MAX_SIMULTANEOUS_FEEDBACKS} feedbacks: {state}"
                )

            feedback_test = DigitalIncremental1Test(mc, alias, axis)
            with FeedbackSelectorTracker(mc, servo, alias, axis) as tracker:
                feedback_test.run()

            assert tracker.initial_state == configuration
            assert tracker.max_simultaneous_feedbacks <= MAX_SIMULTANEOUS_FEEDBACKS, (
                "The feedback test configured more than "
                f"{MAX_SIMULTANEOUS_FEEDBACKS} feedbacks at the same time:\n"
                f"{tracker.format_history()}"
            )
            assert tracker.final_state == configuration

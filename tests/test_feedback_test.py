import logging
import random
from collections.abc import Iterator, Sequence
from itertools import product
from types import TracebackType
from typing import Optional

import pytest
from ingenialink.register import Register
from ingenialink.servo import Servo
from ingenialink.utils._utils import REG_VALUE

from ingeniamotion.enums import SensorType
from ingeniamotion.feedbacks import (
    FEEDBACK_SELECTOR_REGISTERS,
    MAX_SIMULTANEOUS_FEEDBACKS,
    AxisFeedbacks,
    FeedbacksConfiguration,
)
from ingeniamotion.motion_controller import MotionController
from ingeniamotion.wizard_tests.base_test import TestConfigurationError
from ingeniamotion.wizard_tests.feedbacks_tests import feedback_test
from ingeniamotion.wizard_tests.feedbacks_tests.dc_feedback_polarity_test import (
    DCFeedbacksPolarityTest,
)
from ingeniamotion.wizard_tests.feedbacks_tests.dc_feedback_resolution_test import (
    DCFeedbacksResolutionTest,
)
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental1_test import (
    DigitalIncremental1Test,
)
from tests.conftest import slice_configurations

# Record stop opportunities for every wizard-test integration case in this module.
pytestmark = pytest.mark.usefixtures("stoppable_trace_recorder")
logger = logging.getLogger(__name__)

INCREMENTAL_ENCODER_1_RESOLUTION_REGISTER = "FBK_DIGENC1_RESOLUTION"
FEEDBACK_TRANSITION_SAMPLE_SIZE = 10_000


def test_legacy_feedbacks_base_name_warns() -> None:
    """The old feedback-test base name remains available with a warning."""
    with pytest.warns(
        DeprecationWarning, match="^Feedbacks is deprecated, use FeedbacksTest instead$"
    ):
        legacy_feedbacks = feedback_test.Feedbacks

    assert legacy_feedbacks is feedback_test.FeedbacksTest


@pytest.mark.virtual
def test_bldc_feedback_setting_raises_on_zero_resolution(mc, alias):
    """BLDC feedback setup must raise TestConfigurationError when resolution is zero."""
    axis = 1
    mc.communication.set_register(
        INCREMENTAL_ENCODER_1_RESOLUTION_REGISTER, 0, servo=alias, axis=axis
    )
    feedback_test = DigitalIncremental1Test(mc, alias, axis)
    with pytest.raises(TestConfigurationError) as exc_info:
        feedback_test.setup()

    assert (
        str(exc_info.value)
        == "The feedback resolution must be greater than 0. Please adjust it accordingly."
    )


@pytest.mark.virtual
def test_dc_resolution_test_raises_on_zero_resolution(mc, alias):
    """DC resolution test setup must raise TestConfigurationError when resolution is zero."""
    axis = 1
    mc.communication.set_register(
        INCREMENTAL_ENCODER_1_RESOLUTION_REGISTER, 0, servo=alias, axis=axis
    )
    dc_test = DCFeedbacksResolutionTest(mc, SensorType.QEI, alias, axis)
    with pytest.raises(TestConfigurationError) as exc_info:
        dc_test.setup()

    assert (
        str(exc_info.value)
        == "The feedback resolution must be greater than 0. Please adjust it accordingly."
    )


@pytest.mark.virtual
def test_dc_polarity_test_raises_on_zero_resolution(mc, alias):
    """DC polarity test setup must raise TestConfigurationError when resolution is zero."""
    axis = 1
    mc.communication.set_register(
        INCREMENTAL_ENCODER_1_RESOLUTION_REGISTER, 0, servo=alias, axis=axis
    )
    dc_test = DCFeedbacksPolarityTest(mc, SensorType.QEI, alias, axis)
    with pytest.raises(TestConfigurationError) as exc_info:
        dc_test.setup()

    assert (
        str(exc_info.value)
        == "The feedback resolution must be greater than 0. Please adjust it accordingly."
    )


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
        self._feedbacks = mc.motion_nodes[alias].get_axis(axis).feedbacks
        self._state = FeedbacksConfiguration.from_axis_feedbacks(self._feedbacks)
        self.history = [self._state]

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

    def _on_register_update(self, _servo: Servo, register: Register, value: REG_VALUE) -> None:
        if register.subnode != self._axis or register.identifier not in FEEDBACK_SELECTOR_REGISTERS:
            return
        sensor = int(value)
        slot = next(
            slot for slot in self._feedbacks._slots if slot.register_uid == register.identifier
        )
        encoder = self._feedbacks.get_sensor(SensorType(sensor))
        if self._state.encoder_at(slot) == encoder:
            return
        self._state = self._state.with_encoder_at(slot, encoder)
        self.history.append(self._state)
        logger.info(
            "Feedback selector updated: register=%s sensor=%s state=%s",
            register.identifier,
            SensorType(sensor).name if sensor else "DISABLED",
            self._state,
        )

    @property
    def initial_state(self) -> FeedbacksConfiguration:
        return self.history[0]

    @property
    def final_state(self) -> FeedbacksConfiguration:
        return self.history[-1]

    @property
    def max_simultaneous_feedbacks(self) -> int:
        return max(len(state.active_sensors()) for state in self.history)

    def format_history(self) -> str:
        return "\n".join(
            f"{len(state.active_sensors())} feedbacks: "
            + ", ".join(
                f"{uid}={sensor.name}"
                for uid, sensor in zip(
                    FEEDBACK_SELECTOR_REGISTERS, _configuration_sensor_types(state, self._feedbacks)
                )
            )
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
    sensors = []
    for value in sorted(common_values):
        try:
            sensor = SensorType(value)
        except ValueError:
            continue
        if sensor != SensorType.INTGEN:
            sensors.append(sensor)
    return tuple(sensors)


def _feedback_configurations(
    mc: MotionController,
    alias: str,
    axis: int,
) -> Iterator[FeedbacksConfiguration]:
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
    feedbacks = mc.motion_nodes[alias].get_axis(axis).feedbacks
    seen_shapes = set()
    configurations = []
    for combination in product(sensors, repeat=len(FEEDBACK_SELECTOR_REGISTERS)):
        if len(set(combination)) > MAX_SIMULTANEOUS_FEEDBACKS:
            continue
        shape = _configuration_shape(combination)
        if shape in seen_shapes:
            continue
        seen_shapes.add(shape)
        configurations.append(
            FeedbacksConfiguration.from_sensor_types(
                feedbacks,
                commutation=combination[0],
                reference=combination[1],
                velocity=combination[2],
                position=combination[3],
                auxiliary=combination[4],
            )
        )

    random.shuffle(configurations)
    yield from configurations


def _configuration_sensor_types(
    configuration: FeedbacksConfiguration,
    feedbacks: AxisFeedbacks,
) -> tuple[SensorType, ...]:
    """Return configuration sensor types in feedback slot order."""
    return tuple(configuration.encoder_at(slot).SENSOR_TYPE for slot in feedbacks._slots)


def _all_feedback_configurations(
    feedbacks: AxisFeedbacks,
) -> list[FeedbacksConfiguration]:
    """Return every valid assignment of encoders to the feedback slots."""
    slots = feedbacks._slots
    encoders = tuple(feedbacks.get_sensor(sensor) for sensor in SensorType)
    return [
        FeedbacksConfiguration(dict(zip(slots, encoder_combination)))
        for encoder_combination in product(encoders, repeat=len(slots))
        if len({encoder.SENSOR_TYPE for encoder in encoder_combination})
        <= MAX_SIMULTANEOUS_FEEDBACKS
    ]


def _configuration_matches(
    actual: FeedbacksConfiguration,
    expected: FeedbacksConfiguration,
    feedbacks: AxisFeedbacks,
) -> bool:
    """Return whether two configurations assign equal encoders to every slot."""
    return all(actual.encoder_at(slot) == expected.encoder_at(slot) for slot in feedbacks._slots)


def _feedback_transition_pair_indices(
    pair_count: int,
    seed: int,
    setup_specifier,
) -> Sequence[int]:
    """Return the randomized pair slice selected by the active test setup."""
    configuration_slice = setup_specifier.extra_data.get("random_combinations_slice")
    sample_size = (
        FEEDBACK_TRANSITION_SAMPLE_SIZE
        if configuration_slice is None
        else max(1, int(pair_count * configuration_slice))
    )
    if sample_size >= pair_count:
        return range(pair_count)
    return random.Random(seed).sample(range(pair_count), sample_size)


def _feedback_transition_seed(setup_specifier) -> int:
    """Return the configured seed or generate a fresh seed for this run."""
    configured_seed = setup_specifier.extra_data.get("random_combinations_seed")
    if configured_seed is not None:
        return int(configured_seed)
    return random.SystemRandom().getrandbits(64)


def test_feedback_transition_emits_safe_register_values():
    """The emitted writes reach the target without exceeding four sensors."""
    feedbacks = AxisFeedbacks(object())
    current_configuration = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=SensorType.QEI,
        reference=SensorType.HALLS,
        velocity=SensorType.ABS1,
        position=SensorType.ABS1,
        auxiliary=SensorType.QEI,
    )
    target_configuration = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=SensorType.HALLS,
        reference=SensorType.QEI,
        velocity=SensorType.INTGEN,
        position=SensorType.ABS1,
        auxiliary=SensorType.QEI,
    )

    state = current_configuration
    writes = list(feedbacks.transition_order(current_configuration, target_configuration))
    for slot, encoder in writes:
        assert state.can_execute_transition(slot, encoder)
        state = state.with_encoder_at(slot, encoder)
        assert len(state.active_sensors()) <= MAX_SIMULTANEOUS_FEEDBACKS

    assert _configuration_sensor_types(state, feedbacks) == _configuration_sensor_types(
        target_configuration, feedbacks
    )


def test_feedback_transition_reuses_slot_before_new_source():
    """Reuse an active source before selecting a previously inactive source."""
    feedbacks = AxisFeedbacks(object())
    current_configuration = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=SensorType.QEI,
        reference=SensorType.HALLS,
        velocity=SensorType.INTGEN,
        position=SensorType.ABS1,
        auxiliary=SensorType.HALLS,
    )
    target_configuration = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=SensorType.SSI2,
        reference=SensorType.HALLS,
        velocity=SensorType.INTGEN,
        position=SensorType.ABS1,
        auxiliary=SensorType.HALLS,
    )

    assert list(feedbacks.transition_order(current_configuration, target_configuration)) == [
        (feedbacks.commutation, feedbacks.get_sensor(SensorType.HALLS)),
        (feedbacks.commutation, feedbacks.get_sensor(SensorType.SSI2)),
    ]


def test_feedback_transition_is_empty_for_an_unchanged_configuration():
    """No writes are emitted when current and target configurations match."""
    feedbacks = AxisFeedbacks(object())
    configuration = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=SensorType.QEI,
        reference=SensorType.QEI,
        velocity=SensorType.QEI,
        position=SensorType.QEI,
        auxiliary=SensorType.QEI,
    )

    assert list(feedbacks.transition_order(configuration, configuration)) == []


def test_set_configuration_uses_supplied_current_configuration():
    """A supplied current snapshot avoids rereading the feedback selectors."""
    feedbacks = AxisFeedbacks(object())
    configuration = FeedbacksConfiguration.from_sensor_types(
        feedbacks,
        commutation=SensorType.QEI,
        reference=SensorType.QEI,
        velocity=SensorType.QEI,
        position=SensorType.QEI,
        auxiliary=SensorType.QEI,
    )

    feedbacks.set_configuration(configuration, current=configuration)


def test_update_configuration_reads_feedback_selectors_once():
    """The convenience update method does not reread its current configuration."""

    class ReadCountingAxis:
        def __init__(self) -> None:
            self.read_registers: list[str] = []

        def read(self, register_uid: str) -> int:
            self.read_registers.append(register_uid)
            return SensorType.QEI.value

    axis = ReadCountingAxis()
    feedbacks = AxisFeedbacks(axis)

    feedbacks.update_configuration({})

    assert axis.read_registers == list(FEEDBACK_SELECTOR_REGISTERS)


def test_all_feedback_transitions_stay_within_limit_and_reach_target(
    subtests, setup_specifier
) -> None:
    """Verify setup-selected ordered feedback transitions are safe and complete.

    The default run samples 10,000 ordered pairs. Set
    ``random_combinations_slice`` to ``1.0`` in the active Summit setup's
    ``extra_data`` to run all 204,118,369 ordered pairs. Full mode streams pair
    indices and therefore does not allocate the complete pair list. Set
    ``random_combinations_seed`` to reproduce a sampled run exactly.
    """
    feedbacks = AxisFeedbacks(object())
    configurations = _all_feedback_configurations(feedbacks)
    pair_count = len(configurations) ** 2
    seed = _feedback_transition_seed(setup_specifier)
    selected_pair_indices = _feedback_transition_pair_indices(pair_count, seed, setup_specifier)

    for pair_index in selected_pair_indices:
        current_index, target_index = divmod(pair_index, len(configurations))
        current = configurations[current_index]
        target = configurations[target_index]
        state = current

        with subtests.test(
            pair_index=pair_index,
            current_index=current_index,
            target_index=target_index,
            seed=seed,
        ):
            try:
                writes = list(feedbacks.transition_order(current, target))
            except ValueError:
                continue

            for slot, encoder in writes:
                assert state.can_execute_transition(slot, encoder), (
                    f"seed={seed}, pair_index={pair_index}"
                )
                state = state.with_encoder_at(slot, encoder)
                assert len(state.active_sensors()) <= MAX_SIMULTANEOUS_FEEDBACKS, (
                    f"seed={seed}, pair_index={pair_index}"
                )

            assert _configuration_matches(state, target, feedbacks), (
                f"seed={seed}, pair_index={pair_index}"
            )

    assert selected_pair_indices, f"seed={seed}, pair_count={pair_count}"
    assert len(configurations) == 14_287


@pytest.mark.virtual
@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_feedback_test_respects_the_drive_feedback_limit_across_configurations(
    mc, alias, servo, mocker, subtests, setup_specifier
):
    """The feedback test must never exceed the drive feedback limit.

    The drive rejects a fifth feedback, so neither applying the target configuration
    nor the wizard test may go through such a transient state.
    """
    axis = 1
    mocker.patch.object(
        DigitalIncremental1Test, "loop", return_value=DigitalIncremental1Test.ResultType.SUCCESS
    )

    configurations = list(_feedback_configurations(mc, alias, axis))
    for configuration in slice_configurations(configurations, setup_specifier):
        feedbacks = mc.motion_nodes[alias].get_axis(axis).feedbacks
        msg = "_".join(
            sensor.name for sensor in _configuration_sensor_types(configuration, feedbacks)
        )
        with subtests.test(msg=msg):
            feedback_test = DigitalIncremental1Test(mc, alias, axis)
            with FeedbackSelectorTracker(mc, servo, alias, axis) as tracker:
                feedbacks.set_configuration(configuration)
                assert _configuration_sensor_types(tracker.final_state, feedbacks) == (
                    _configuration_sensor_types(configuration, feedbacks)
                )
                feedback_test.run()

            assert tracker.max_simultaneous_feedbacks <= MAX_SIMULTANEOUS_FEEDBACKS, (
                "The feedback test configured more than "
                f"{MAX_SIMULTANEOUS_FEEDBACKS} feedbacks at the same time:\n"
                f"{tracker.format_history()}"
            )
            assert _configuration_sensor_types(tracker.final_state, feedbacks) == (
                _configuration_sensor_types(configuration, feedbacks)
            )

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

# Record stop opportunities for every wizard-test integration case in this module.
pytestmark = pytest.mark.usefixtures("stoppable_trace_recorder")

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


# The drives cannot hold more than four different feedbacks configured at the same time.
MAX_SIMULTANEOUS_FEEDBACKS = 4


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
            uid: SensorType(mc.communication.get_register(uid, servo=alias, axis=axis))
            for uid in FEEDBACK_SELECTOR_REGISTERS
        }
        self.history = [dict(self._state)]

    def __enter__(self) -> "FeedbackSelectorTracker":
        self._servo.register_update_subscribe(self._on_register_update)
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self._servo.register_update_unsubscribe(self._on_register_update)

    def _on_register_update(self, servo: Servo, register: Register, value: REG_VALUE) -> None:  # noqa: ARG002
        if register.subnode != self._axis or register.identifier not in self._state:
            return
        sensor = SensorType(value)
        if self._state[register.identifier] == sensor:
            return
        self._state[register.identifier] = sensor
        self.history.append(dict(self._state))

    @property
    def initial_state(self) -> dict[str, SensorType]:
        return self.history[0]

    @property
    def final_state(self) -> dict[str, SensorType]:
        return self.history[-1]

    @property
    def max_simultaneous_feedbacks(self) -> int:
        return max(len(set(state.values())) for state in self.history)

    def format_history(self) -> str:
        return "\n".join(
            f"{len(set(state.values()))} feedbacks: "
            + ", ".join(f"{uid}={sensor.name}" for uid, sensor in state.items())
            for state in self.history
        )


def _feedback_configurations():
    """Generate every selector equality pattern allowed by the four-feedback limit.

    Yields:
        Parametrized feedback selector configurations.
    """
    non_target_sensors = (SensorType.HALLS, SensorType.ABS1, SensorType.BISSC2, SensorType.SSI2)
    for pattern in product(range(5), repeat=len(FEEDBACK_SELECTOR_REGISTERS)):
        if pattern[0] != 0 or len(set(pattern)) > MAX_SIMULTANEOUS_FEEDBACKS:
            continue
        if any(label > max(pattern[:index]) + 1 for index, label in enumerate(pattern[1:], 1)):
            continue

        labels = sorted(set(pattern))
        for target_label in [None, *labels]:
            sensor_by_label = {}
            non_target_sensor_iter = iter(non_target_sensors)
            for label in labels:
                sensor_by_label[label] = (
                    SensorType.QEI
                    if label == target_label
                    else next(non_target_sensor_iter)
                )
            configuration = dict(
                zip(
                    FEEDBACK_SELECTOR_REGISTERS,
                    (sensor_by_label[label] for label in pattern),
                )
            )
            target_name = "absent" if target_label is None else f"group_{target_label}"
            pattern_name = "".join(map(str, pattern))
            yield pytest.param(configuration, id=f"pattern_{pattern_name}_{target_name}")


FEEDBACK_CONFIGURATIONS = list(_feedback_configurations())


@pytest.mark.virtual
@pytest.mark.parametrize("initial_configuration", FEEDBACK_CONFIGURATIONS)
def test_feedback_test_never_exceeds_the_drive_feedback_limit(
    mc, alias, servo, mocker, initial_configuration
):
    """The feedback test must never configure more than four feedbacks at once.

    The drive rejects a fifth feedback, so neither the setup writes nor the rollback
    performed by the drive context manager may go through such a transient state.
    """
    axis = 1
    for uid, sensor in initial_configuration.items():
        mc.communication.set_register(uid, sensor, servo=alias, axis=axis)

    mocker.patch.object(
        DigitalIncremental1Test, "loop", return_value=DigitalIncremental1Test.ResultType.SUCCESS
    )
    feedback_test = DigitalIncremental1Test(mc, alias, axis)

    with FeedbackSelectorTracker(mc, servo, alias, axis) as tracker:
        feedback_test.run()

    assert tracker.initial_state == initial_configuration
    assert tracker.max_simultaneous_feedbacks <= MAX_SIMULTANEOUS_FEEDBACKS, (
        "The feedback test configured more than "
        f"{MAX_SIMULTANEOUS_FEEDBACKS} feedbacks at the same time:\n{tracker.format_history()}"
    )


@pytest.mark.virtual
@pytest.mark.parametrize("initial_configuration", FEEDBACK_CONFIGURATIONS)
def test_feedback_test_restores_the_initial_feedback_configuration(
    mc, alias, servo, mocker, initial_configuration
):
    """The feedback test must leave the feedback selectors as it found them."""
    axis = 1
    for uid, sensor in initial_configuration.items():
        mc.communication.set_register(uid, sensor, servo=alias, axis=axis)

    mocker.patch.object(
        DigitalIncremental1Test, "loop", return_value=DigitalIncremental1Test.ResultType.SUCCESS
    )
    feedback_test = DigitalIncremental1Test(mc, alias, axis)

    with FeedbackSelectorTracker(mc, servo, alias, axis) as tracker:
        feedback_test.run()

    assert tracker.final_state == initial_configuration

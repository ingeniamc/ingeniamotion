import pytest

from ingeniamotion.enums import SensorType
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

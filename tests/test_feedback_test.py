import pytest

from ingeniamotion.enums import SensorType
from ingeniamotion.wizard_tests.base_test import TestConfigurationError
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder1_test import (
    AbsoluteEncoder1Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder2_test import (
    AbsoluteEncoder2Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.dc_feedback_polarity_test import (
    DCFeedbacksPolarityTest,
)
from ingeniamotion.wizard_tests.feedbacks_tests.dc_feedback_resolution_test import (
    DCFeedbacksResolutionTest,
)
from ingeniamotion.wizard_tests.feedbacks_tests.digital_hall_test import DigitalHallTest
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental1_test import (
    DigitalIncremental1Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental2_test import (
    DigitalIncremental2Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.secondary_ssi_test import (
    SecondarySSITest,
)

INCREMENTAL_ENCODER_1_RESOLUTION_REGISTER = "FBK_DIGENC1_RESOLUTION"


@pytest.mark.virtual
@pytest.mark.parametrize(
    "feedback_test_type, expected_total_mandatory",
    [
        (DigitalIncremental1Test, 25),
        (DigitalIncremental2Test, 25),
        (AbsoluteEncoder1Test, 25),
        (AbsoluteEncoder2Test, 25),
        (SecondarySSITest, 24),
        (DigitalHallTest, 27),
    ],
)
def test_feedback_test_initialization(mc, alias, feedback_test_type, expected_total_mandatory):
    expected_total_optional = 5
    expected_total_backup_registers = expected_total_mandatory + expected_total_optional

    axis = 1
    feedback_test = feedback_test_type(mc, alias, axis)

    feedback_test = feedback_test_type(mc, alias, 1)
    total_mandatory = len(feedback_test.backup_registers_names)
    total_optional = len(feedback_test.optional_backup_registers_names)
    total_backup_register = total_mandatory + total_optional

    assert total_mandatory == expected_total_mandatory
    assert total_optional == expected_total_optional
    assert total_backup_register == expected_total_backup_registers


@pytest.mark.virtual
@pytest.mark.parametrize(
    "feedback_test_type",
    [
        DigitalIncremental1Test,
        DigitalIncremental2Test,
        AbsoluteEncoder1Test,
        AbsoluteEncoder2Test,
        SecondarySSITest,
        DigitalHallTest,
    ],
)
def test_save_backup_registers(mc, alias, feedback_test_type):
    axis = 1
    feedback_test = feedback_test_type(mc, alias, axis)
    mandatory_backup_registers = feedback_test.backup_registers_names

    expected_total_mandatory = len(mandatory_backup_registers)
    expected_total_optional = 3
    expected_total_backup_registers = expected_total_mandatory + expected_total_optional

    feedback_test.save_backup_registers()
    saved_backup_registers = feedback_test.backup_registers[axis]
    total_backup_registers = len(saved_backup_registers)

    assert total_backup_registers == expected_total_backup_registers
    for expected_register in feedback_test.backup_registers_names:
        assert expected_register in saved_backup_registers
    assert "COMMU_ANGLE_INTEGRITY1_OPTION" not in saved_backup_registers
    assert "COMMU_ANGLE_INTEGRITY2_OPTION" not in saved_backup_registers
    assert "PROF_POS_OPTION_CODE" in saved_backup_registers
    assert "CL_POS_REF_MAX_RANGE" in saved_backup_registers
    assert "CL_POS_REF_MIN_RANGE" in saved_backup_registers


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

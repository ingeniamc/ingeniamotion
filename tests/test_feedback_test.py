import pytest

from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder1_test import (
    AbsoluteEncoder1Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder2_test import (
    AbsoluteEncoder2Test,
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
def test_feedback_test_initialization(
    motion_controller, alias, feedback_test_type, expected_total_mandatory
):
    expected_total_optional = 5
    expected_total_backup_registers = expected_total_mandatory + expected_total_optional

    mc = motion_controller
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
def test_save_backup_registers(motion_controller, alias, feedback_test_type):
    mc = motion_controller
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

import pytest
from ingenialink import exceptions

from ingeniamotion.enums import SensorType
from ingeniamotion.wizard_tests.base_test import BaseTest, TestError


@pytest.fixture
def force_fault(motion_controller):
    mc, alias = motion_controller
    uid = "DRV_PROT_USER_UNDER_VOLT"
    mc.communication.set_register(uid, 100, alias)
    yield exceptions.ILStateError
    mc.communication.set_register(uid, 10, alias)


@pytest.fixture(scope="session")
def feedback_list(motion_controller):
    mc, alias = motion_controller
    fdbk_lst = [mc.configuration.get_commutation_feedback(servo=alias),
                mc.configuration.get_reference_feedback(servo=alias),
                mc.configuration.get_velocity_feedback(servo=alias),
                mc.configuration.get_position_feedback(servo=alias),
                mc.configuration.get_auxiliar_feedback(servo=alias)]
    return set(fdbk_lst)


def test_digital_halls_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    if SensorType.HALLS in feedback_list:
        results = mc.tests.digital_halls_test(servo=alias)
        assert results["result_severity"] == BaseTest.SeverityLevel.SUCCESS
    else:
        with pytest.raises(exceptions.ILStateError):
            mc.tests.digital_halls_test(servo=alias)


def test_incremental_encoder_1_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    if SensorType.QEI in feedback_list:
        results = mc.tests.incremental_encoder_1_test(servo=alias)
        assert results["result_severity"] == BaseTest.SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.incremental_encoder_1_test(servo=alias)


def test_incremental_encoder_2_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    if SensorType.QEI2 in feedback_list:
        results = mc.tests.incremental_encoder_2_test(servo=alias)
        assert results["result_severity"] == BaseTest.SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.incremental_encoder_2_test(servo=alias)


def test_absolute_encoder_1_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    if SensorType.ABS1 in feedback_list:
        results = mc.tests.absolute_encoder_1_test(servo=alias)
        assert results["result_severity"] == BaseTest.SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.absolute_encoder_1_test(servo=alias)


def test_absolute_encoder_2_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    if SensorType.BISSC2 in feedback_list:
        results = mc.tests.absolute_encoder_2_test(servo=alias)
        assert results["result_severity"] == BaseTest.SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.absolute_encoder_2_test(servo=alias)


def test_secondary_ssi_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    if SensorType.SSI2 in feedback_list:
        results = mc.tests.secondary_ssi_test(servo=alias)
        assert results["result_severity"] == BaseTest.SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.secondary_ssi_test(servo=alias)


def test_commutation(motion_controller):
    mc, alias = motion_controller
    results = mc.tests.commutation(servo=alias)
    assert results["result_severity"] == BaseTest.SeverityLevel.SUCCESS


def test_commutation_error(motion_controller, force_fault):
    mc, alias = motion_controller
    with pytest.raises(force_fault):
        mc.tests.commutation(servo=alias)


def test_phasing_check(motion_controller):
    mc, alias = motion_controller
    results = mc.tests.phasing_check(servo=alias)
    assert results["result_severity"] == BaseTest.SeverityLevel.SUCCESS


def test_phasing_check_error(motion_controller, force_fault):
    mc, alias = motion_controller
    with pytest.raises(force_fault):
        mc.tests.phasing_check(servo=alias)


@pytest.mark.smoke
def test_sto_test(motion_controller):
    mc, alias = motion_controller
    results = mc.tests.sto_test(servo=alias)
    assert results["result_severity"] == BaseTest.SeverityLevel.SUCCESS


@pytest.mark.smoke
@pytest.mark.parametrize("sto_value, message", [
    (0x4, "STO Active"), (0x1F, "Abnormal STO Latched"), (0x8, "Abnormal STO"),
    (0x73, "Abnormal Supply"), (0x5, "STO Inputs Differ")
])
def test_sto_test_error(mocker, motion_controller, sto_value, message):
    mocker.patch('ingeniamotion.configuration.Configuration.get_sto_status',
                 return_value=sto_value)
    mc, alias = motion_controller
    results = mc.tests.sto_test(servo=alias)
    assert results["result_severity"] == BaseTest.SeverityLevel.FAIL
    assert results["result_message"] == message


@pytest.mark.smoke
def test_brake_test(motion_controller):
    mc, alias = motion_controller
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)
    brake_test = mc.tests.brake_test(servo=alias)
    assert 1 == mc.configuration.get_motor_pair_poles(servo=alias)
    brake_test.finish()
    assert pair_poles == mc.configuration.get_motor_pair_poles(servo=alias)

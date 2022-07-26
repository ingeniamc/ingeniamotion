import time
import pytest

from threading import Thread
from ingenialink import exceptions

from ingeniamotion.enums import SensorType, SeverityLevel
from ingeniamotion.exceptions import IMRegisterNotExist
from ingeniamotion.wizard_tests.feedback_test import Feedbacks
from ingeniamotion.wizard_tests.phase_calibration import Phasing
from ingeniamotion.wizard_tests.phasing_check import PhasingCheck
from ingeniamotion.wizard_tests.base_test import BaseTest, TestError


@pytest.fixture
def force_fault(motion_controller):
    mc, alias = motion_controller
    uid = "DRV_PROT_USER_UNDER_VOLT"
    mc.communication.set_register(uid, 100, alias)
    yield exceptions.ILStateError
    mc.communication.set_register(uid, 10, alias)


@pytest.fixture(scope="module")
def feedback_test_setup(motion_controller):
    mc, alias = motion_controller
    mc.tests.commutation(servo=alias)


@pytest.mark.usefixtures("feedback_test_setup")
def test_digital_halls_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.HALLS in feedback_list:
        results = mc.tests.digital_halls_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(exceptions.ILStateError):
            mc.tests.digital_halls_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.usefixtures("feedback_test_setup")
def test_incremental_encoder_1_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.QEI in feedback_list:
        results = mc.tests.incremental_encoder_1_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.incremental_encoder_1_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.usefixtures("feedback_test_setup")
def test_incremental_encoder_2_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.QEI2 in feedback_list:
        results = mc.tests.incremental_encoder_2_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.incremental_encoder_2_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.usefixtures("feedback_test_setup")
def test_absolute_encoder_1_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.ABS1 in feedback_list:
        results = mc.tests.absolute_encoder_1_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.absolute_encoder_1_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.usefixtures("feedback_test_setup")
def test_absolute_encoder_2_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.BISSC2 in feedback_list:
        results = mc.tests.absolute_encoder_2_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.absolute_encoder_2_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.usefixtures("feedback_test_setup")
def test_secondary_ssi_test(motion_controller, feedback_list):
    mc, alias = motion_controller
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.SSI2 in feedback_list:
        results = mc.tests.secondary_ssi_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.secondary_ssi_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


def test_commutation(motion_controller):
    mc, alias = motion_controller
    results = mc.tests.commutation(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS


def test_commutation_error(motion_controller, force_fault):
    mc, alias = motion_controller
    with pytest.raises(force_fault):
        mc.tests.commutation(servo=alias)


def test_phasing_check(motion_controller):
    mc, alias = motion_controller
    results = mc.tests.phasing_check(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS


def test_phasing_check_error(motion_controller, force_fault):
    mc, alias = motion_controller
    with pytest.raises(force_fault):
        mc.tests.phasing_check(servo=alias)


@pytest.mark.smoke
def test_sto_test(motion_controller):
    mc, alias = motion_controller
    results = mc.tests.sto_test(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS


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
    assert results["result_severity"] == SeverityLevel.FAIL
    assert results["result_message"] == message


@pytest.mark.smoke
def test_brake_test(motion_controller):
    mc, alias = motion_controller
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)
    brake_test = mc.tests.brake_test(servo=alias)
    assert 1 == mc.configuration.get_motor_pair_poles(servo=alias)
    brake_test.finish()
    assert pair_poles == mc.configuration.get_motor_pair_poles(servo=alias)


def get_backup_registers(test, mc, alias):
    reg_values = {}
    for reg in test.BACKUP_REGISTERS:
        try:
            reg_values[reg] = mc.communication.get_register(reg, servo=alias)
        except IMRegisterNotExist:
            pass
    return reg_values


def run_test_and_stop(test):
    test_thread = Thread(target=test.run)
    test_thread.start()
    time.sleep(2)
    test.stop()
    test_thread.join()


@pytest.mark.usefixtures("feedback_test_setup")
@pytest.mark.parametrize("sensor", list(SensorType))
def test_feedback_stop(motion_controller, sensor):
    mc, alias = motion_controller
    test = Feedbacks(mc, alias, 1, sensor)
    reg_values = get_backup_registers(test, mc, alias)
    run_test_and_stop(test)
    for reg in reg_values:
        assert reg_values[reg] == mc.communication.get_register(reg, servo=alias)


@pytest.mark.usefixtures("commutation_teardown")
def test_commutation_stop(motion_controller):
    mc, alias = motion_controller
    test = Phasing(mc, alias, 1)
    reg_values = get_backup_registers(test, mc, alias)
    run_test_and_stop(test)
    for reg in reg_values:
        assert reg_values[reg] == mc.communication.get_register(reg, servo=alias)


@pytest.mark.usefixtures("commutation_teardown")
def test_phasing_check_stop(motion_controller):
    mc, alias = motion_controller
    test = PhasingCheck(mc, alias, 1)
    reg_values = get_backup_registers(test, mc, alias)
    run_test_and_stop(test)
    for reg in reg_values:
        assert reg_values[reg] == mc.communication.get_register(reg, servo=alias)

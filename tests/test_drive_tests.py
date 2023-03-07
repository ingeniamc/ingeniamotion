import time
import pytest

from threading import Thread
from ingenialink import exceptions

from ingeniamotion.enums import SensorType, SeverityLevel
from ingeniamotion.exceptions import IMRegisterNotExist
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder1_test import AbsoluteEncoder1Test
from ingeniamotion.wizard_tests.feedbacks_tests.absolute_encoder2_test import AbsoluteEncoder2Test
from ingeniamotion.wizard_tests.feedbacks_tests.digital_hall_test import DigitalHallTest
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental1_test import (
    DigitalIncremental1Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.digital_incremental2_test import (
    DigitalIncremental2Test,
)
from ingeniamotion.wizard_tests.feedbacks_tests.secondary_ssi_test import SecondarySSITest
from ingeniamotion.wizard_tests.phase_calibration import Phasing
from ingeniamotion.wizard_tests.phasing_check import PhasingCheck
from ingeniamotion.wizard_tests.base_test import BaseTest, TestError

CURRENT_QUADRATURE_SET_POINT_REGISTER = "CL_CUR_Q_SET_POINT"
RATED_CURRENT_REGISTER = "MOT_RATED_CURRENT"
MAXIMUM_CONTINUOUS_CURRENT_DRIVE_PROTECTION = "DRV_PROT_MAN_MAX_CONT_CURRENT_VALUE"


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
@pytest.mark.parametrize(
    "sto_value, message",
    [
        (0x4, "STO Active"),
        (0x1F, "Abnormal STO Latched"),
        (0x8, "Abnormal STO"),
        (0x73, "Abnormal Supply"),
        (0x5, "STO Inputs Differ"),
    ],
)
def test_sto_test_error(mocker, motion_controller, sto_value, message):
    mocker.patch("ingeniamotion.configuration.Configuration.get_sto_status", return_value=sto_value)
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
    test = mc.tests.get_feedback_test(alias, sensor, 1)
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


@pytest.mark.develop
@pytest.mark.parametrize("test_currents", ["Rated current", "Drive current", "Same value"])
@pytest.mark.parametrize(
    "test_sensor",
    [
        SensorType.ABS1,
        SensorType.QEI,
        SensorType.HALLS,
        SensorType.SSI2,
        SensorType.BISSC2,
        SensorType.QEI2,
    ],
)
def test_current_ramp_up(motion_controller, test_currents, test_sensor):
    mc, alias = motion_controller

    axis = 1
    test_feedback_options = {
        SensorType.ABS1: AbsoluteEncoder1Test(mc, alias, axis),
        SensorType.QEI: DigitalIncremental1Test(mc, alias, axis),
        SensorType.HALLS: DigitalHallTest(mc, alias, axis),
        SensorType.SSI2: SecondarySSITest(mc, alias, axis),
        SensorType.BISSC2: AbsoluteEncoder2Test(mc, alias, axis),
        SensorType.QEI2: DigitalIncremental2Test(mc, alias, axis),
    }
    feedbacks_test = test_feedback_options[test_sensor]

    current_drive = mc.communication.get_register(
        MAXIMUM_CONTINUOUS_CURRENT_DRIVE_PROTECTION, servo=alias, axis=1
    )

    if test_currents == "Rated current":
        current_motor = current_drive + 1
    elif test_currents == "Drive current":
        current_motor = current_drive - 1
    else:
        current_motor = current_drive

    mc.communication.set_register(RATED_CURRENT_REGISTER, current_motor, servo=alias, axis=1)

    feedbacks_test.current_ramp_up()

    current_quadrature = mc.communication.get_register(
        CURRENT_QUADRATURE_SET_POINT_REGISTER, servo=alias, axis=1
    )

    test_max_current = current_quadrature / feedbacks_test.PERCENTAGE_CURRENT_USED

    if test_currents == "Rated current":
        assert pytest.approx(test_max_current) == current_drive
    elif test_currents == "Drive current":
        assert pytest.approx(test_max_current) == current_motor
    else:
        assert pytest.approx(test_max_current) == current_drive == current_motor

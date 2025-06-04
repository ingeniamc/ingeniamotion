import contextlib
import time
from threading import Thread

import pytest
from ingenialink import exceptions

from ingeniamotion.enums import SensorType, SeverityLevel
from ingeniamotion.exceptions import IMRegisterNotExistError
from ingeniamotion.wizard_tests.base_test import TestError
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

CURRENT_QUADRATURE_SET_POINT_REGISTER = "CL_CUR_Q_SET_POINT"
RATED_CURRENT_REGISTER = "MOT_RATED_CURRENT"
MAXIMUM_CONTINUOUS_CURRENT_DRIVE_PROTECTION = "DRV_PROT_MAN_MAX_CONT_CURRENT_VALUE"


@pytest.fixture
def force_fault(mc, alias):
    uid = "DRV_PROT_USER_UNDER_VOLT"
    mc.communication.set_register(uid, 100, alias)
    yield exceptions.ILError
    mc.communication.set_register(uid, 10, alias)


@pytest.fixture(scope="module")
def feedback_test_setup(_motion_controller_creator, alias):
    mc = _motion_controller_creator
    mc.tests.commutation(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
def test_digital_halls_test(mc, alias, feedback_list):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.HALLS in feedback_list:
        results = mc.tests.digital_halls_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.digital_halls_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
def test_incremental_encoder_1_test(mc, alias, feedback_list):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.QEI in feedback_list:
        results = mc.tests.incremental_encoder_1_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.incremental_encoder_1_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
def test_incremental_encoder_2_test(mc, alias, feedback_list):
    if not mc.info.register_exists("FBK_DIGENC2_RESOLUTION", servo=alias):
        pytest.skip("Incremental encoder 2 is not available")
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.QEI2 in feedback_list:
        results = mc.tests.incremental_encoder_2_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.incremental_encoder_2_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
def test_absolute_encoder_1_test(mc, alias, feedback_list):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.ABS1 in feedback_list:
        results = mc.tests.absolute_encoder_1_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.absolute_encoder_1_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
def test_absolute_encoder_2_test(mc, alias, feedback_list):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.BISSC2 in feedback_list:
        results = mc.tests.absolute_encoder_2_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.absolute_encoder_2_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
def test_secondary_ssi_test(mc, alias, feedback_list):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.QEI in feedback_list:
        pytest.skip("Can not run the test. Incremental encoder 1 and SSI 2 share pins.")
    if SensorType.SSI2 in feedback_list:
        results = mc.tests.secondary_ssi_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.secondary_ssi_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_commutation(alias, motion_controller_teardown):
    mc = motion_controller_teardown
    results = mc.tests.commutation(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_commutation_error(mc, alias, force_fault):
    with pytest.raises(force_fault):
        mc.tests.commutation(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.skip("Skip until is fixed INGM-352")
def test_phasing_check(mc, alias):
    mc.tests.commutation(servo=alias)
    results = mc.tests.phasing_check(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_phasing_check_error(mc, alias, force_fault):
    with pytest.raises(force_fault):
        mc.tests.phasing_check(servo=alias)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_sto_test(mc, alias):
    results = mc.tests.sto_test(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS


@pytest.mark.virtual
@pytest.mark.parametrize(
    "sto_value, message",
    [
        (0x4, "STO Active"),
        (0x1F, "Abnormal STO Latched"),
        (0xE, "Abnormal STO"),
        (0x73, "Abnormal Supply"),
        (0x5, "STO Inputs Differ"),
    ],
)
def test_sto_test_error(mocker, mc, alias, sto_value, message):
    mocker.patch("ingeniamotion.configuration.Configuration.get_sto_status", return_value=sto_value)
    results = mc.tests.sto_test(servo=alias)
    assert results["result_severity"] == SeverityLevel.FAIL
    assert results["result_message"] == message


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_brake_test(mc, alias):
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)
    brake_test = mc.tests.brake_test(servo=alias)
    assert mc.configuration.get_motor_pair_poles(servo=alias) == 1
    brake_test.finish()
    assert pair_poles == mc.configuration.get_motor_pair_poles(servo=alias)


def get_backup_registers(test, mc, alias):
    reg_values = {}
    for reg in test.BACKUP_REGISTERS:
        with contextlib.suppress(IMRegisterNotExistError):
            reg_values[reg] = mc.communication.get_register(reg, servo=alias)
    return reg_values


def run_test_and_stop(test):
    test_thread = Thread(target=test.run)
    test_thread.start()
    time.sleep(2)
    test.stop()
    test_thread.join()


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
@pytest.mark.parametrize(
    "feedback_class",
    [
        AbsoluteEncoder1Test,
        AbsoluteEncoder2Test,
        DigitalHallTest,
        DigitalIncremental1Test,
        DigitalIncremental2Test,
        SecondarySSITest,
    ],
)
def test_feedback_stop(mc, alias, feedback_class):
    test = feedback_class(mc, alias, 1)
    reg_values = get_backup_registers(test, mc, alias)
    run_test_and_stop(test)
    for reg in reg_values:
        assert reg_values[reg] == mc.communication.get_register(reg, servo=alias)


@pytest.mark.virtual
def test_commutation_stop(mc, alias):
    test = Phasing(mc, alias, 1)
    reg_values = get_backup_registers(test, mc, alias)
    run_test_and_stop(test)
    for reg in reg_values:
        assert reg_values[reg] == mc.communication.get_register(reg, servo=alias)


@pytest.mark.virtual
def test_phasing_check_stop(mc, alias):
    test = PhasingCheck(mc, alias, 1)
    reg_values = get_backup_registers(test, mc, alias)
    run_test_and_stop(test)
    for reg in reg_values:
        assert reg_values[reg] == mc.communication.get_register(reg, servo=alias)


@pytest.mark.virtual
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
def test_current_ramp_up(mc, alias, test_currents, test_sensor):
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

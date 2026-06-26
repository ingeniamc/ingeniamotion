import logging
import time
from collections.abc import Collection
from enum import Enum
from threading import Thread
from typing import TYPE_CHECKING

import pytest
from ingenialink import exceptions
from ingenialink.drive_context_manager import DriveRegistersValue
from ingenialink.servo import Servo
from summit_testing_framework.connection.reconnect_utils import ConnectionWrapper

from ingeniamotion.enums import SensorType, SeverityLevel
from ingeniamotion.motion_controller import MotionController
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

# Record stop opportunities for every wizard-test integration case in this module.
pytestmark = pytest.mark.usefixtures("stoppable_trace_recorder")

if TYPE_CHECKING:
    from summit_testing_framework.setups.environment_control import DriveEnvironmentController


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
def feedback_test_setup(
    _motion_controller_creator, environment: "DriveEnvironmentController"
) -> None:
    mc = _motion_controller_creator
    mc.tests.commutation(servo=environment.aliases)


def assert_returns_to_initial_value(
    servo: Servo,
    initial_value: DriveRegistersValue,
    accepted_changed_registers: Collection[str] = (),
):
    """Assert that the test returns to the initial configuration after running.

    Args:
        servo (Servo): The servo to check.
        initial_value (DriveRegistersValue): The initial configuration of the servo.
        accepted_changed_registers (Collection[str]): UIDs of registers the test is
            expected to change permanently (e.g. calibration results or values set by
            a fixture). Differences in these registers are ignored.
    """
    current_state = DriveRegistersValue.from_hardware(servo)

    differences = {
        register: values
        for register, values in initial_value.diff(current_state).items()
        if register.identifier not in accepted_changed_registers
    }

    differences_str = "\n".join(
        f"{register}: initial={initial_value}, current={current_value}"
        for register, (initial_value, current_value) in differences.items()
    )
    assert len(differences) == 0, (
        f"Test did not return to initial value. Differences:\n{differences_str}"
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-782
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_digital_halls_test(
    mc, alias, feedback_list, servo: Servo, register_baseline: DriveRegistersValue
):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.HALLS in feedback_list:
        results = mc.tests.digital_halls_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.digital_halls_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)

    assert_returns_to_initial_value(
        servo, register_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-783
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_incremental_encoder_1_test(
    mc, alias, feedback_list, servo: Servo, register_baseline: DriveRegistersValue
):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.QEI in feedback_list:
        results = mc.tests.incremental_encoder_1_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.incremental_encoder_1_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)

    assert_returns_to_initial_value(
        servo, register_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-784
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_incremental_encoder_2_test(
    mc, alias, feedback_list, servo: Servo, register_baseline: DriveRegistersValue
):
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

    assert_returns_to_initial_value(
        servo, register_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-785
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_absolute_encoder_1_test(
    mc, alias, feedback_list, servo: Servo, register_baseline: DriveRegistersValue
):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.ABS1 in feedback_list:
        results = mc.tests.absolute_encoder_1_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.absolute_encoder_1_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)

    assert_returns_to_initial_value(
        servo, register_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-786
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_absolute_encoder_2_test(
    mc, alias, feedback_list, servo: Servo, register_baseline: DriveRegistersValue
):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.BISSC2 in feedback_list:
        results = mc.tests.absolute_encoder_2_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.absolute_encoder_2_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)

    assert_returns_to_initial_value(
        servo, register_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-787
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_secondary_ssi_test(
    mc, alias, feedback_list, servo: Servo, register_baseline: DriveRegistersValue
):
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

    assert_returns_to_initial_value(
        servo, register_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
# https://novantamotion.atlassian.net/browse/INGM-774
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_commutation(
    alias: str, mc: "MotionController", servo: Servo, register_baseline: DriveRegistersValue
) -> None:
    results = mc.tests.commutation(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS

    assert_returns_to_initial_value(
        servo, register_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_commutation_error(mc, alias, force_fault, servo: Servo):
    # Capture the baseline after force_fault applied it, so its value is part of the
    # expected state and the test still verifies the wizard restored everything else.
    initial_values = DriveRegistersValue.from_hardware(servo)
    with pytest.raises(force_fault):
        mc.tests.commutation(servo=alias)

    assert_returns_to_initial_value(servo, initial_values)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.skip("Skip until is fixed INGM-352")
def test_phasing_check(mc, alias, servo: Servo, register_baseline: DriveRegistersValue):
    mc.tests.commutation(servo=alias)
    results = mc.tests.phasing_check(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS
    assert_returns_to_initial_value(
        servo, register_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_phasing_check_error(mc, alias, force_fault, servo: Servo):
    # Capture the baseline after force_fault applied it, so its value is part of the
    # expected state and the test still verifies the wizard restored everything else.
    initial_values = DriveRegistersValue.from_hardware(servo)
    with pytest.raises(force_fault):
        mc.tests.phasing_check(servo=alias)

    assert_returns_to_initial_value(servo, initial_values)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_sto_test(mc, alias, servo: Servo, register_baseline: DriveRegistersValue):
    results = mc.tests.sto_test(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS

    assert_returns_to_initial_value(servo, register_baseline)


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
def test_sto_test_error(
    mocker, mc, alias, sto_value, message, servo: Servo, register_baseline: DriveRegistersValue
):
    mocker.patch("ingeniamotion.configuration.Configuration.get_sto_status", return_value=sto_value)
    results = mc.tests.sto_test(servo=alias)
    assert results["result_severity"] == SeverityLevel.FAIL
    assert results["result_message"] == message

    assert_returns_to_initial_value(servo, register_baseline)


@pytest.mark.virtual
@pytest.mark.parametrize("sto_value", [0x4, 0x1F, 0xE, 0x73, 0x5, 0x17])
def test_sto_test_logs(
    caplog, mocker, mc, alias, sto_value, servo: Servo, register_baseline: DriveRegistersValue
):
    caplog.set_level(logging.INFO)
    mocker.patch("ingeniamotion.configuration.Configuration.get_sto_status", return_value=sto_value)
    mc.tests.sto_test(servo=alias)

    # Calculate expected log messages from bit pattern
    # STO1 active when bit 0 is 0, STO2 active when bit 1 is 0
    sto1_log = f"STO1 bit is {'HIGH' if sto_value & 0x1 else 'LOW'}"
    sto2_log = f"STO2 bit is {'HIGH' if sto_value & 0x2 else 'LOW'}"
    supply_log = f"STO Power Supply is {'HIGH' if sto_value & 0x4 else 'LOW'}"
    abnormal_log = f"STO abnormal fault bit is {'HIGH' if sto_value & 0x8 else 'LOW'}"
    report_log = f"STO report bit is {'HIGH' if sto_value & 0x10 else 'LOW'}"

    assert sto1_log in caplog.text
    assert sto2_log in caplog.text
    assert supply_log in caplog.text
    assert abnormal_log in caplog.text
    assert report_log in caplog.text

    assert_returns_to_initial_value(servo, register_baseline)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_brake_test(mc, alias, servo: Servo, connection_wrapper: ConnectionWrapper):
    # Set frame type to BiSS-C BP3 to ensure that the test changes it to avoid an error.
    mc.communication.set_register("FBK_BISS1_SSI1_FRAME_TYPE", 3, servo=alias)
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)
    initial_values = connection_wrapper.current_registers_values()
    brake_test = mc.tests.brake_test(servo=alias)
    assert mc.configuration.get_motor_pair_poles(servo=alias) == 1
    brake_test.finish()
    assert pair_poles == mc.configuration.get_motor_pair_poles(servo=alias)

    assert_returns_to_initial_value(servo, initial_values)


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
# https://novantamotion.atlassian.net/browse/INGM-790
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_feedback_stop(
    mc, alias, feedback_class, servo: Servo, register_baseline: DriveRegistersValue
):
    test = feedback_class(mc, alias, 1)
    run_test_and_stop(test)

    assert_returns_to_initial_value(
        servo, register_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.virtual
def test_commutation_stop(mc, alias, servo: Servo, register_baseline: DriveRegistersValue):
    test = Phasing(mc, alias, 1)
    run_test_and_stop(test)

    assert_returns_to_initial_value(servo, register_baseline)


@pytest.mark.virtual
def test_phasing_check_stop(mc, alias, servo: Servo, register_baseline: DriveRegistersValue):
    test = PhasingCheck(mc, alias, 1)
    run_test_and_stop(test)

    assert_returns_to_initial_value(servo, register_baseline)


class TestCurrents(Enum):
    RATED_CURRENT = "Rated current"
    DRIVE_CURRENT = "Drive current"
    SAME_VALUE = "Same value"


@pytest.mark.virtual
@pytest.mark.parametrize(
    "test_currents",
    [TestCurrents.RATED_CURRENT, TestCurrents.DRIVE_CURRENT, TestCurrents.SAME_VALUE],
)
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
def test_current_ramp_up(
    mc: MotionController,
    alias: str,
    test_currents: TestCurrents,
    test_sensor: SensorType,
):
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

    if test_currents == TestCurrents.RATED_CURRENT:
        current_motor = current_drive + 1
    elif test_currents == TestCurrents.DRIVE_CURRENT:
        current_motor = current_drive - 1
    elif test_currents == TestCurrents.SAME_VALUE:
        current_motor = current_drive
    else:
        raise NotImplementedError(f"Test currents option {test_currents} is not implemented.")

    mc.communication.set_register(RATED_CURRENT_REGISTER, current_motor, servo=alias, axis=1)

    feedbacks_test.current_ramp_up()

    current_quadrature = mc.communication.get_register(
        CURRENT_QUADRATURE_SET_POINT_REGISTER, servo=alias, axis=1
    )

    test_max_current = current_quadrature / feedbacks_test.PERCENTAGE_CURRENT_USED

    if test_currents == TestCurrents.RATED_CURRENT:
        assert pytest.approx(test_max_current) == current_drive
    elif test_currents == TestCurrents.DRIVE_CURRENT:
        assert pytest.approx(test_max_current) == current_motor
    elif test_currents == TestCurrents.SAME_VALUE:
        assert pytest.approx(test_max_current) == current_drive == current_motor
    else:
        raise NotImplementedError(f"Test currents option {test_currents} is not implemented.")

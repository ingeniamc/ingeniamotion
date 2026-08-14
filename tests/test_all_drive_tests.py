import logging
import random
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

from ingeniamotion.enums import PhasingMode, SensorType, SeverityLevel
from ingeniamotion.motion_controller import MotionController
from ingeniamotion.wizard_tests.base_test import TestError
from ingeniamotion.wizard_tests.dynamic_forced_phasing import (
    COMMUTATION_ANGLE_VALUE_REGISTER,
    REFERENCE_ANGLE_VALUE_REGISTER,
    DynamicForcedPhasing,
    circular_distance,
)
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
from tests.conftest import refresh_registers_for_test_rollback

# Record stop opportunities for every wizard-test integration case in this module.
pytestmark = pytest.mark.usefixtures("stoppable_trace_recorder")

if TYPE_CHECKING:
    from summit_testing_framework.setups.environment_control import DriveEnvironmentController


CURRENT_QUADRATURE_SET_POINT_REGISTER = "CL_CUR_Q_SET_POINT"
RATED_CURRENT_REGISTER = "MOT_RATED_CURRENT"
MAXIMUM_CONTINUOUS_CURRENT_DRIVE_PROTECTION = "DRV_PROT_MAN_MAX_CONT_CURRENT_VALUE"
# Diagnostic error-history registers that change as a side effect of any error raised during
# a test (e.g. the CANopen pre-defined error field 0x1003) and cannot be restored to a prior
# value (writable only to 0, to clear). Always ignored by the restore assertion.
DIAGNOSTIC_ERROR_REGISTERS = ("CIA301_COMMS_ERROR_FIELD",)


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
            a fixture). Differences in these registers are ignored, on top of the
            always-ignored DIAGNOSTIC_ERROR_REGISTERS.
    """
    current_state = DriveRegistersValue.from_hardware(servo)

    ignored = set(accepted_changed_registers) | set(DIAGNOSTIC_ERROR_REGISTERS)
    differences = {
        register: values
        for register, values in initial_value.diff(current_state).items()
        if register.identifier not in ignored
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
def test_digital_halls_test(
    servo: Servo, mc, alias, feedback_list, registers_baseline: DriveRegistersValue
):
    with refresh_registers_for_test_rollback(
        servo,
        [
            "COMMU_ANGLE_OFFSET",
            "COMMU_ANGLE_REF_OFFSET",
            "COMMU_PHASING_MAX_CURRENT",
            "COMMU_PHASING_TIMEOUT",
        ],
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
        servo,
        registers_baseline,
        accepted_changed_registers=DigitalHallTest.ACCEPTED_CHANGED_REGISTERS,
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-783
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_incremental_encoder_1_test(
    mc, alias, feedback_list, servo: Servo, registers_baseline: DriveRegistersValue
):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.QEI in feedback_list:
        results = mc.tests.incremental_encoder_1_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.incremental_encoder_1_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-784
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_incremental_encoder_2_test(
    mc, alias, feedback_list, servo: Servo, registers_baseline: DriveRegistersValue
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

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-785
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_absolute_encoder_1_test(
    mc, alias, feedback_list, servo: Servo, registers_baseline: DriveRegistersValue
):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.ABS1 in feedback_list:
        results = mc.tests.absolute_encoder_1_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.absolute_encoder_1_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-786
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_absolute_encoder_2_test(
    mc, alias, feedback_list, servo: Servo, registers_baseline: DriveRegistersValue
):
    commutation_fdbk = mc.configuration.get_commutation_feedback(servo=alias)
    if SensorType.BISSC2 in feedback_list:
        results = mc.tests.absolute_encoder_2_test(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS
    else:
        with pytest.raises(TestError):
            mc.tests.absolute_encoder_2_test(servo=alias)
    assert commutation_fdbk == mc.configuration.get_commutation_feedback(servo=alias)

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-787
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_secondary_ssi_test(
    mc, alias, feedback_list, servo: Servo, registers_baseline: DriveRegistersValue
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

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
# https://novantamotion.atlassian.net/browse/INGM-774
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_commutation(
    servo: Servo, alias: str, mc: "MotionController", registers_baseline: DriveRegistersValue
) -> None:
    with refresh_registers_for_test_rollback(
        servo,
        [
            "COMMU_ANGLE_OFFSET",
            "COMMU_ANGLE_REF_OFFSET",
            "COMMU_PHASING_MAX_CURRENT",
        ],
    ):
        results = mc.tests.commutation(servo=alias)
        assert results["result_severity"] == SeverityLevel.SUCCESS

    assert_returns_to_initial_value(
        servo, registers_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
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

    assert_returns_to_initial_value(
        servo, initial_values, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.skip("Skip until is fixed INGM-352")
def test_phasing_check(mc, alias, servo: Servo, registers_baseline: DriveRegistersValue):
    mc.tests.commutation(servo=alias)
    results = mc.tests.phasing_check(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS
    assert_returns_to_initial_value(servo, registers_baseline)


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
def test_sto_test(mc, alias, servo: Servo, registers_baseline: DriveRegistersValue):
    results = mc.tests.sto_test(servo=alias)
    assert results["result_severity"] == SeverityLevel.SUCCESS

    assert_returns_to_initial_value(servo, registers_baseline)


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
    mocker, mc, alias, sto_value, message, servo: Servo, registers_baseline: DriveRegistersValue
):
    mocker.patch("ingeniamotion.configuration.Configuration.get_sto_status", return_value=sto_value)
    results = mc.tests.sto_test(servo=alias)
    assert results["result_severity"] == SeverityLevel.FAIL
    assert results["result_message"] == message

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.virtual
@pytest.mark.parametrize("sto_value", [0x4, 0x1F, 0xE, 0x73, 0x5, 0x17])
def test_sto_test_logs(
    caplog, mocker, mc, alias, sto_value, servo: Servo, registers_baseline: DriveRegistersValue
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

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_brake_test(mc, alias, servo: Servo, connection_wrapper: ConnectionWrapper):
    # Set frame type to BiSS-C BP3 to ensure that the test changes it to avoid an error.
    mc.communication.set_register("FBK_BISS1_SSI1_FRAME_TYPE", 3, servo=alias)
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)
    initial_values = connection_wrapper.current_registers_values()
    with mc.tests.brake_test(servo=alias):
        # Inside the context the drive is left configured for the brake test.
        assert mc.configuration.get_motor_pair_poles(servo=alias) == 1
    # On context exit the drive state is restored.
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
    mc, alias, feedback_class, servo: Servo, registers_baseline: DriveRegistersValue
):
    test = feedback_class(mc, alias, 1)
    run_test_and_stop(test)

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.virtual
def test_commutation_stop(mc, alias, servo: Servo, registers_baseline: DriveRegistersValue):
    test = Phasing(mc, alias, 1)
    run_test_and_stop(test)

    assert_returns_to_initial_value(
        servo, registers_baseline, accepted_changed_registers=Phasing.ACCEPTED_CHANGED_REGISTERS
    )


@pytest.mark.virtual
def test_phasing_check_stop(mc, alias, servo: Servo, registers_baseline: DriveRegistersValue):
    test = PhasingCheck(mc, alias, 1)
    run_test_and_stop(test)

    assert_returns_to_initial_value(servo, registers_baseline)


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


@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.not_valid_for_product(part_number="EVE-*")
def test_dynamic_forced_phasing(mc, alias, registers_baseline: DriveRegistersValue, servo: Servo):
    """Run the test on a real drive and check it succeeds, leaving the drive in NO_PHASING.

    Reads the motor rated current, runs the phasing without writing registers, and verifies
    the result is SUCCESS with a normalized commutation angle in [0, 1).
    """
    rated_current = mc.communication.get_register(RATED_CURRENT_REGISTER, servo=alias, axis=1)
    result = mc.tests.dynamic_forced_phasing(
        alias,
        1,
        apply_changes=False,
        phasing_max_current=rated_current,
    )
    assert result.result_severity == SeverityLevel.SUCCESS
    assert result.result_message == "Success"
    assert result.commutation_phasing_mode == PhasingMode.NO_PHASING
    assert result.phasing_max_current == rated_current
    assert 0 <= result.commutation_angle <= 1

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.virtual
def test_dynamic_forced_phasing_fails_when_monitoring_not_supported(mc, alias, mocker):
    """Check the test aborts with a TestError when the drive can't do monitoring.

    Patches the monitoring version check to raise, then asserts the phasing surfaces that
    failure as a TestError.
    """
    mocker.patch.object(
        mc.capture, "_check_version", side_effect=NotImplementedError("Monitoring not available")
    )
    mocker.patch.object(mc.capture, "disable_monitoring")  # avoid real cleanup during teardown
    with pytest.raises(TestError, match="Monitoring not available"):
        mc.tests.dynamic_forced_phasing(alias, 1)


@pytest.mark.virtual
@pytest.mark.parametrize(
    ("comm_feedback", "ref_feedback", "error_match"),
    [
        (SensorType.INTGEN, SensorType.ABS1, "internal generator"),
        (SensorType.ABS1, SensorType.INTGEN, "internal generator"),
        (SensorType.QEI, SensorType.QEI, "not absolute"),
        (SensorType.ABS1, SensorType.BISSC2, "not the same"),
    ],
    ids=[
        "commutation_is_internal_generator",
        "reference_is_internal_generator",
        "reference_not_absolute",
        "feedbacks_differ",
    ],
)
def test_dynamic_forced_phasing_fails_with_invalid_feedback_config(
    mc, alias, mocker, comm_feedback, ref_feedback, error_match
):
    """Check the test rejects unsupported commutation/reference feedback combinations.

    Forces each invalid feedback pair via mocks and asserts a TestError is raised whose
    message explains why the configuration is unsupported.
    """
    axis_feedbacks = mc.motion_nodes[alias].get_axis(1).feedbacks
    current_configuration = axis_feedbacks.get_configuration()
    invalid_configuration = current_configuration.replace({
        axis_feedbacks.commutation: axis_feedbacks.get_sensor(comm_feedback),
        axis_feedbacks.reference: axis_feedbacks.get_sensor(ref_feedback),
    })
    mocker.patch.object(axis_feedbacks, "get_configuration", return_value=invalid_configuration)

    with pytest.raises(TestError, match=error_match):
        mc.tests.dynamic_forced_phasing(alias, 1)


@pytest.mark.virtual
def test_dynamic_forced_phasing_fails_when_phasing_current_exceeds_limit(mc, alias):
    """Check the test rejects a phasing current above the drive's allowed limit.

    Passes an impossibly large ``phasing_max_current`` and asserts a TestError is raised.
    """
    with pytest.raises(TestError, match="Phasing max current"):
        mc.tests.dynamic_forced_phasing(alias, 1, phasing_max_current=1e9)


@pytest.mark.virtual
def test_dynamic_forced_phasing_fails_when_no_constant_difference_found(
    mc, alias, mocker, servo: Servo, registers_baseline: DriveRegistersValue
):
    """Check the test fails when no stable phase difference can be measured.

    Stubs out the setup steps and forces signal collection to raise, then asserts the
    "could not find a constant signal difference" TestError propagates.
    """
    # Skip initial-state and monitoring setup so only the collection failure is exercised
    mocker.patch.object(DynamicForcedPhasing, "_DynamicForcedPhasing__check_initial_state")
    mocker.patch.object(DynamicForcedPhasing, "_DynamicForcedPhasing__configure_monitoring")
    mocker.patch.object(
        DynamicForcedPhasing,
        "_collect_mean_difference",
        side_effect=TestError(
            "Could not find a constant signal difference after trying all frequencies"
        ),
    )
    rated_current = mc.communication.get_register(RATED_CURRENT_REGISTER, servo=alias, axis=1)

    with pytest.raises(TestError, match="Could not find a constant signal difference"):
        mc.tests.dynamic_forced_phasing(alias, 1, phasing_max_current=rated_current)

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.virtual
def test_dynamic_forced_phasing_warning_on_high_asymmetry(
    mc, alias, mocker, servo: Servo, registers_baseline: DriveRegistersValue
):
    """Check the test returns a WARNING when forward/backward differences are too asymmetric.

    Feeds two mismatched mean differences (0.15 and 0.30) so the asymmetry exceeds the 10%
    threshold, then asserts the result severity is WARNING and mentions the asymmetry error.
    """
    mocker.patch.object(DynamicForcedPhasing, "_DynamicForcedPhasing__check_initial_state")
    mocker.patch.object(DynamicForcedPhasing, "_DynamicForcedPhasing__configure_monitoring")
    mocker.patch.object(DynamicForcedPhasing, "_collect_mean_difference", side_effect=[0.15, 0.30])
    result = mc.tests.dynamic_forced_phasing(alias, 1, apply_changes=False)

    assert result is not None
    assert result.result_severity == SeverityLevel.WARNING
    assert "Asymmetry error" in result.result_message

    assert_returns_to_initial_value(servo, registers_baseline)


@pytest.mark.virtual
@pytest.mark.parametrize("offset", [0.0, 0.25, 0.5, 0.75, 0.99])
@pytest.mark.parametrize("noise_amplitude", [0.0, 0.001, 0.01])
def test_dynamic_forced_phasing_signals_with_noise(mc, alias, offset, noise_amplitude):
    """Check the constant-difference detector recovers a known phase offset under noise.

    Builds two ramp signals separated by ``offset`` plus bounded random noise, runs the
    constant-difference check, and asserts the detected mean offset (compared on the circular
    [0, 1) domain) and the max deviation stay within the noise bounds.
    """
    random.seed(42)  # fixed seed keeps the random noise reproducible across runs
    test = DynamicForcedPhasing(mc, alias, 1)
    num_points = 200

    # signal1 is a normalized ramp; signal2 is the same ramp shifted by `offset` plus noise
    signal1 = [i / num_points for i in range(num_points)]
    signal2 = [
        (s1 - offset + random.uniform(-noise_amplitude, noise_amplitude)) % 1 for s1 in signal1
    ]

    # Points deviate from the mean by at most the noise span (each side of it).
    tolerance = 2 * noise_amplitude + 1e-6
    mean_diff = test._DynamicForcedPhasing__check_signals_difference_is_constant(
        signal1, signal2, tolerance_norm=tolerance
    )

    assert mean_diff is not None
    # Compare in the circular [0, 1) domain so the wrap-around boundary is handled.
    assert circular_distance(mean_diff, offset) < noise_amplitude + 1e-6


@pytest.mark.virtual
def test_calculate_monitoring_max_time(mc, alias, mocker):
    """Check the monitoring max time calculation returns the expected value."""
    # Mock the loop rate and max sample size to known values so the calculation is deterministic.
    mocker.patch.object(
        mc.configuration, "get_position_and_velocity_loop_rate", return_value=20000.0
    )
    mocker.patch.object(mc.capture, "monitoring_max_sample_size", return_value=8192)
    dfp = DynamicForcedPhasing(mc, alias, 1)
    mapped_registers = [
        {"name": COMMUTATION_ANGLE_VALUE_REGISTER, "axis": 1},
        {"name": REFERENCE_ANGLE_VALUE_REGISTER, "axis": 1},
    ]
    result = dfp._DynamicForcedPhasing__calculate_monitoring_max_time(
        frequency_divider=20,
        mapped_registers=mapped_registers,
    )
    # The expected max time is calculated as:
    # map_reg_size = 2*4 bytes (two float registers)
    # max_sample_size = 8192 bytes
    # frequency = loop_rate / frequency_divider = 20000 Hz / 20 = 1000 Hz
    # max_time = (8192 bytes / 8 bytes) / 1000 Hz = 1.024 seconds
    expected = 1.024
    assert result == pytest.approx(expected)

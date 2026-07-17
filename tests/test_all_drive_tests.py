import contextlib
import logging
import random
import time
from threading import Thread
from typing import TYPE_CHECKING

import pytest
from ingenialink import exceptions

from ingeniamotion.enums import PhasingMode, SensorType, SeverityLevel
from ingeniamotion.exceptions import IMRegisterNotExistError
from ingeniamotion.wizard_tests.base_test import TestError
from ingeniamotion.wizard_tests.dynamic_forced_phasing import (
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
from tests.conftest import not_valid_for_all_eve_products, refresh_registers_for_test_rollback

# Record stop opportunities for every wizard-test integration case in this module.
pytestmark = pytest.mark.usefixtures("stoppable_trace_recorder")

if TYPE_CHECKING:
    from summit_testing_framework.setups.environment_control import DriveEnvironmentController

    from ingeniamotion.motion_controller import MotionController

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


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-782
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_digital_halls_test(servo, mc, alias, feedback_list):
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


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("feedback_test_setup")
# https://novantamotion.atlassian.net/browse/INGM-783
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
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
# https://novantamotion.atlassian.net/browse/INGM-784
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
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
# https://novantamotion.atlassian.net/browse/INGM-785
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
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
# https://novantamotion.atlassian.net/browse/INGM-786
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
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
# https://novantamotion.atlassian.net/browse/INGM-787
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
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
# https://novantamotion.atlassian.net/browse/INGM-774
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
def test_commutation(servo, alias: str, mc: "MotionController") -> None:
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


@pytest.mark.virtual
@pytest.mark.parametrize("sto_value", [0x4, 0x1F, 0xE, 0x73, 0x5, 0x17])
def test_sto_test_logs(caplog, mocker, mc, alias, sto_value):
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


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_brake_test(mc, alias):
    # Set frame type to BiSS-C BP3 to ensure that the test changes it to avoid an error.
    mc.communication.set_register("FBK_BISS1_SSI1_FRAME_TYPE", 3, servo=alias)
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
# https://novantamotion.atlassian.net/browse/INGM-790
@pytest.mark.not_valid_for_product(part_number="CAP-XCR-E")
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


@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.ethernet
@not_valid_for_all_eve_products
def test_dynamic_forced_phasing(mc, alias):
    """Run the test on a real drive and check it succeeds, leaving the drive in NO_PHASING.

    Reads the motor rated current, runs the phasing without writing registers, and verifies
    the result is SUCCESS with a normalised commutation angle in [0, 1).
    """
    rated_current = mc.communication.get_register(RATED_CURRENT_REGISTER, servo=alias, axis=1)
    result = mc.tests.dynamic_forced_phasing(
        alias,
        1,
        apply_changes=False,
        phasing_max_current=rated_current,  # don't persist registers
    )
    assert result.result_severity == SeverityLevel.SUCCESS
    assert result.result_message == "Success"
    assert result.commutation_phasing_mode == PhasingMode.NO_PHASING
    assert 0 <= result.commutation_angle <= 1


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
    mocker.patch.object(mc.configuration, "get_commutation_feedback", return_value=comm_feedback)
    mocker.patch.object(mc.configuration, "get_reference_feedback", return_value=ref_feedback)

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
def test_dynamic_forced_phasing_fails_when_no_constant_difference_found(mc, alias, mocker):
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


@pytest.mark.virtual
def test_dynamic_forced_phasing_warning_on_high_asymmetry(mc, alias, mocker):
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

    # signal1 is a normalised ramp; signal2 is the same ramp shifted by `offset` plus noise
    signal1 = [i / num_points for i in range(num_points)]
    signal2 = [
        (s1 - offset + random.uniform(-noise_amplitude, noise_amplitude)) % 1 for s1 in signal1
    ]

    tolerance = DynamicForcedPhasing.NORM_TOLERANCE
    mean_diff, max_diff = test._DynamicForcedPhasing__check_signals_difference_is_constant(
        signal1, signal2, tolerance
    )

    assert mean_diff is not None
    assert max_diff is not None
    # Compare in the circular [0, 1) domain so the wrap-around boundary is handled.
    assert circular_distance(mean_diff, offset) < noise_amplitude + 1e-6
    # Points deviate from the mean by at most the noise span (each side of it).
    assert max_diff <= 2 * noise_amplitude + 1e-6

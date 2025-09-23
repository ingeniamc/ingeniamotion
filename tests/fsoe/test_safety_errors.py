import time
from typing import TYPE_CHECKING, Callable

import pytest
from ingenialink.dictionary import Interface
from ingenialink.servo import DictionaryFactory

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEState
from tests.dictionaries import SAMPLE_SAFE_PH2_XDFV3_DICTIONARY

try:
    import pysoem
except ImportError:
    pysoem = None

if TYPE_CHECKING:
    from ingenialink.ethercat.servo import EthercatServo
    from summit_testing_framework.setups.environment_control import DriveEnvironmentController

    from ingeniamotion.motion_controller import MotionController

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import (
        FSoEMasterHandler,
        ProcessImage,
        SafeInputsFunction,
        SLPFunction,
        SPFunction,
        SS1Function,
        STOFunction,
        SVFunction,
    )
    from ingeniamotion.fsoe_master.errors import Error, ServoErrorQueue

__INVALID_MAPPING_ERROR_ID = 0x80040002  # Error ID for invalid mapping error


@pytest.mark.fsoe_phase2
def test_get_known_error() -> None:
    """Test getting a known error from the dictionary."""
    dictionary = DictionaryFactory.create_dictionary(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, interface=Interface.ECAT
    )
    error = Error.from_id(0x00007394, dictionary=dictionary)
    assert error.error_id == 0x00007394
    assert error.error_description == "Emergency position set-point not configured."
    assert (
        repr(error) == f"<Error object at {hex(id(error))} error_id=29588"
        f" error_description='Emergency position set-point not configured.'>"
    )


@pytest.mark.fsoe_phase2
def test_get_error_with_id_not_in_dict() -> None:
    """Test getting an error with an unknown ID."""
    dictionary = DictionaryFactory.create_dictionary(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, interface=Interface.ECAT
    )
    error = Error.from_id(0x1234, dictionary=dictionary)
    assert error.error_id == 0x1234
    assert error.error_description == "Unknown error 4660 / 0x1234"


@pytest.mark.fsoe_phase2
def test_no_errors(
    mcu_error_queue_a: "ServoErrorQueue", environment: "DriveEnvironmentController"
) -> None:
    """Test methods when there are no errors"""
    # Clear any existing errors by power cycling
    environment.power_cycle(wait_for_drives=True)

    assert mcu_error_queue_a.get_number_total_errors() == 0

    last_error = mcu_error_queue_a.get_last_error()
    assert last_error is None

    mcu_error_queue_a.get_pending_errors() == []


@pytest.mark.skip(reason="FSOE Over temperature error was not available in release 2.8.1")
@pytest.mark.fsoe_phase2
def test_get_last_error_overtemp_error(
    servo: "EthercatServo",
    mcu_error_queue_a: "ServoErrorQueue",
    environment: "DriveEnvironmentController",
) -> None:
    """Test getting the last error when there is an overtemperature error."""
    # Clear any existing errors by power cycling
    environment.power_cycle(wait_for_drives=True)

    servo.write("FSOE_USER_OVER_TEMPERATURE", 0, subnode=1)

    last_error = mcu_error_queue_a.get_last_error()

    assert isinstance(last_error, Error)
    assert last_error.error_id == 0x80020001
    assert last_error.error_description == (
        "Overtemperature. The local temperature of a safety core exceeds the upper limit."
    )


@pytest.mark.fsoe_phase2
def test_get_last_error_invalid_map(
    mcu_error_queue_a: "ServoErrorQueue",
    mc_with_fsoe_factory: Callable[..., tuple["MotionController", "FSoEMasterHandler"]],
    environment: "DriveEnvironmentController",
    timeout_for_data_sra: float,
) -> None:
    """Test getting the last error when there is an invalid map error."""
    environment.power_cycle(wait_for_drives=True)

    mc, handler = mc_with_fsoe_factory(use_sra=True, fail_on_fsoe_errors=False)

    # Add a function that uses safe position to handler
    # and select feedback scenario invalid
    handler.safety_parameters["FSOE_FEEDBACK_SCENARIO"].set(0)  # No feedbacks

    sto = handler.get_function_instance(STOFunction)
    slp_1 = handler.get_function_instance(SLPFunction, instance=1)

    handler.get_function_instance(SPFunction)
    handler.get_function_instance(SVFunction)

    maps = ProcessImage.empty(handler.dictionary)

    maps.inputs.add(sto.command)

    maps.outputs.add(sto.command)
    maps.outputs.add(slp_1.command)

    handler.set_process_image(maps)

    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
    time.sleep(timeout_for_data_sra)
    try:
        assert mcu_error_queue_a.get_number_total_errors() == 1
        assert mcu_error_queue_a.get_last_error().error_id == __INVALID_MAPPING_ERROR_ID

        errors_a, errors_losts = mcu_error_queue_a.get_pending_errors()
        assert len(errors_a) == 1
        assert errors_a[0].error_id == __INVALID_MAPPING_ERROR_ID

        assert not errors_losts
    finally:
        # Stop the master
        mc.fsoe.stop_master(stop_pdos=True)
        # Power cycle to clear the errors generated
        environment.power_cycle(wait_for_drives=True)


@pytest.mark.fsoe_phase2
@pytest.mark.parametrize(
    "last_total_errors, current_total_errors, expected_pending_error_indexes, expected_errors_lost",
    [
        (0, 5, (0, 1, 2, 3, 4), False),
        (7, 11, (7, 8, 9, 10), False),
        (29, 35, (29, 30, 31, 0, 1, 2), False),
        (17, 17 + 32, tuple(range(17, 32)) + tuple(range(17)), False),
        (17, 17 + 33, tuple(range(18, 32)) + tuple(range(18)), True),
    ],
)
def test_get_pending_error_indexes(
    last_total_errors: int,
    current_total_errors: int,
    expected_pending_error_indexes: tuple[int, ...],
    expected_errors_lost: bool,
    mcu_error_queue_a: "ServoErrorQueue",
) -> None:
    mcu_error_queue_a._ServoErrorQueue__last_read_total_errors_pending = last_total_errors
    pending_error_indexes, errors_lost = (
        mcu_error_queue_a._ServoErrorQueue__get_pending_error_indexes(current_total_errors)
    )

    assert pending_error_indexes == expected_pending_error_indexes
    assert errors_lost == expected_errors_lost


@pytest.mark.fsoe_phase2
def test_feedback_scenario_0_ss1_time_controlled_allowed(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    servo: "EthercatServo",
    no_error_tracker: None,  # noqa: ARG001
) -> None:
    """With feedback scenario 0, SS1 time controlled is allowed."""
    mc, handler = mc_with_fsoe_with_sra
    assert handler.safety_parameters.get("FSOE_FEEDBACK_SCENARIO").get() == 0

    handler.process_image.inputs.clear()
    handler.process_image.outputs.clear()

    sto = handler.get_function_instance(STOFunction)
    safe_inputs = handler.get_function_instance(SafeInputsFunction)
    ss1 = handler.get_function_instance(SS1Function)

    outputs = handler.process_image.outputs
    outputs.add(sto.command)
    outputs.add(ss1.command)
    outputs.add_padding(6)

    inputs = handler.process_image.inputs
    inputs.add(sto.command)
    inputs.add(ss1.command)
    inputs.add_padding(6)
    inputs.add(safe_inputs.value)
    inputs.add_padding(7)

    # Configure SS1 time controlled
    ss1.deceleration_limit.set(0)

    # Map is valid
    handler.process_image.validate()

    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    time.sleep(1)
    assert mc.fsoe.get_fsoe_master_state() == FSoEState.DATA
    assert servo.slave.state is pysoem.OP_STATE
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe_phase2
def test_feedback_scenario_0_ss1_ramp_monitored_not_allowed(
    mc_with_fsoe_factory: Callable[..., tuple["MotionController", "FSoEMasterHandler"]],
    timeout_for_data_sra: float,
    servo: "EthercatServo",
    mcu_error_queue_a: "ServoErrorQueue",
) -> None:
    """With feedback scenario 0, SS1 ramp monitored is not allowed."""
    mc, handler = mc_with_fsoe_factory(use_sra=True, fail_on_fsoe_errors=False)
    assert handler.safety_parameters.get("FSOE_FEEDBACK_SCENARIO").get() == 0

    handler.process_image.inputs.clear()
    handler.process_image.outputs.clear()

    sto = handler.get_function_instance(STOFunction)
    safe_inputs = handler.get_function_instance(SafeInputsFunction)
    ss1 = handler.get_function_instance(SS1Function)

    outputs = handler.process_image.outputs
    outputs.add(sto.command)
    outputs.add(ss1.command)
    outputs.add_padding(6)

    inputs = handler.process_image.inputs
    inputs.add(sto.command)
    inputs.add(ss1.command)
    inputs.add_padding(6)
    inputs.add(safe_inputs.value)
    inputs.add_padding(7)

    # Configure SS1 time controlled
    ss1.deceleration_limit.set(1)

    # Map is valid
    handler.process_image.validate()

    previous_mcu_a_errors = mcu_error_queue_a.get_number_total_errors()

    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
    time.sleep(timeout_for_data_sra)

    # Servo cannot reach OP state
    assert servo.slave.state is not pysoem.OP_STATE
    assert mcu_error_queue_a.get_number_total_errors() > previous_mcu_a_errors
    assert mcu_error_queue_a.get_last_error().error_id == __INVALID_MAPPING_ERROR_ID

    mc.fsoe.stop_master(stop_pdos=True)

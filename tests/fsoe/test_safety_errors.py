import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Callable

import pytest
from ingenialink.dictionary import Interface
from ingenialink.servo import DictionaryFactory
from summit_testing_framework.setups.specifiers import PartNumber

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEState
from tests.dictionaries import SAMPLE_SAFE_PH2_XDFV3_DICTIONARY

try:
    import pysoem
except ImportError:
    pysoem = None

if TYPE_CHECKING:
    from ingenialink.ethercat.servo import EthercatServo
    from summit_testing_framework.setups.descriptors import DriveHwSetup
    from summit_testing_framework.setups.environment_control import DriveEnvironmentController

    from ingeniamotion.motion_controller import MotionController

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import (
        FSoEMasterHandler,
        ProcessImage,
        SafeInputsFunction,
        SLPFunction,
        SOutFunction,
        SPFunction,
        SS1Function,
        STOFunction,
        SVFunction,
    )
    from ingeniamotion.fsoe_master.errors import Error, ServoErrorQueue

_INVALID_MAPPING_ERROR_ID = 0x80040002  # Error ID for invalid mapping error


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
    mcu_error_queue_a: "ServoErrorQueue",
    environment: "DriveEnvironmentController",
) -> None:
    """Test methods when there are no errors"""
    # Clear any existing errors by power cycling
    environment.power_cycle(wait_for_drives=True, reconnect_drives=True)

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
    environment.power_cycle(wait_for_drives=True, reconnect_drives=True)

    servo.write("FSOE_USER_OVER_TEMPERATURE", 0, subnode=1)

    last_error = mcu_error_queue_a.get_last_error()

    assert isinstance(last_error, Error)
    assert last_error.error_id == 0x80020001
    assert last_error.error_description == (
        "Overtemperature. The local temperature of a safety core exceeds the upper limit."
    )


@pytest.fixture
def mc_with_fsoe_with_sra_no_fail_on_errors(
    mc_with_fsoe_factory: Callable[..., tuple["MotionController", "FSoEMasterHandler"]],
) -> Iterator[tuple["MotionController", "FSoEMasterHandler"]]:
    mc, handler = mc_with_fsoe_factory(use_sra=True, fail_on_fsoe_errors=False)
    yield mc, handler


@pytest.mark.fsoe_phase2
def test_get_last_error_invalid_map(
    mcu_error_queue_a: "ServoErrorQueue",
    mc_with_fsoe_with_sra_no_fail_on_errors: tuple["MotionController", "FSoEMasterHandler"],
    environment: "DriveEnvironmentController",
    timeout_for_data_sra: float,
) -> None:
    """Test getting the last error when there is an invalid map error."""
    environment.power_cycle(wait_for_drives=True, reconnect_drives=True)

    mc, handler = mc_with_fsoe_with_sra_no_fail_on_errors

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
        assert mcu_error_queue_a.get_last_error().error_id == _INVALID_MAPPING_ERROR_ID

        errors_a, errors_losts = mcu_error_queue_a.get_pending_errors()
        assert len(errors_a) == 1
        assert errors_a[0].error_id == _INVALID_MAPPING_ERROR_ID

        assert not errors_losts
    finally:
        # Stop the master
        mc.fsoe.stop_master(stop_pdos=True)
        # Power cycle to clear the errors generated
        environment.power_cycle(wait_for_drives=True, reconnect_drives=True)


@pytest.mark.fsoe_phase2
@pytest.mark.parametrize(
    "last_total_errors, current_total_errors, expected_number_of_pending_errors, "
    "expected_errors_lost",
    [
        (0, 5, 5, False),
        (7, 11, 4, False),
        (29, 35, 6, False),
        (17, 17 + 32, 32, False),
        (17, 17 + 33, 32, True),
    ],
)
def test_get_pending_error_indexes(
    last_total_errors: int,
    current_total_errors: int,
    expected_number_of_pending_errors: int,
    expected_errors_lost: bool,
    mcu_error_queue_a: "ServoErrorQueue",
) -> None:
    mcu_error_queue_a._ServoErrorQueue__last_read_total_errors_pending = last_total_errors
    pending_error_indexes, errors_lost = (
        mcu_error_queue_a._ServoErrorQueue__get_number_of_pending_error(current_total_errors)
    )

    assert pending_error_indexes == expected_number_of_pending_errors
    assert errors_lost == expected_errors_lost


@pytest.fixture
def mc_with_fsoe_with_sra_with_feedback_scenario_0(
    mc_with_fsoe_with_sra_no_fail_on_errors: tuple["MotionController", "FSoEMasterHandler"],
) -> Iterator[tuple["MotionController", "FSoEMasterHandler"]]:
    mc, handler = mc_with_fsoe_with_sra_no_fail_on_errors
    handler.process_image.inputs.clear()
    handler.process_image.outputs.clear()
    handler.safety_parameters["FSOE_FEEDBACK_SCENARIO"].set(0)
    yield mc, handler


def _check_op_state_reached_with_no_errors(
    mc: "MotionController",
    servo: "EthercatServo",
    mcu_error_queue_a: "ServoErrorQueue",
    timeout_for_data_sra: float,
) -> None:
    previous_mcu_a_errors = mcu_error_queue_a.get_number_total_errors()
    mc.fsoe.start_master(start_pdos=True)
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    time.sleep(1)
    assert mc.fsoe.get_fsoe_master_state() == FSoEState.DATA
    assert mcu_error_queue_a.get_number_total_errors() == previous_mcu_a_errors
    assert servo.slave.state is pysoem.OP_STATE
    mc.fsoe.stop_master(stop_pdos=True)


def _check_invalid_map_error_is_raised(
    mc: "MotionController",
    servo: "EthercatServo",
    mcu_error_queue_a: "ServoErrorQueue",
    timeout_for_data_sra: float,
) -> None:
    previous_mcu_a_errors = mcu_error_queue_a.get_number_total_errors()
    mc.fsoe.start_master(start_pdos=True)
    time.sleep(timeout_for_data_sra)
    # Servo cannot reach OP state
    assert mcu_error_queue_a.get_number_total_errors() > previous_mcu_a_errors
    assert mcu_error_queue_a.get_last_error().error_id == _INVALID_MAPPING_ERROR_ID
    assert servo.slave.state is not pysoem.OP_STATE
    mc.fsoe.stop_master(stop_pdos=True)


class TestFeedbackScenario0:
    """If Feedback scenario is set 0, no motion-dependent safety functions are allowed.

    * Only STO, SS1-t and SOUT commands are allowed.
    * Safe Input value is allowed, but cannot be mapped to SS2 or SS1-r.
    """

    @pytest.fixture(scope="function")
    def configured_handler(
        self,
        mc_with_fsoe_with_sra_with_feedback_scenario_0: tuple[
            "MotionController", "FSoEMasterHandler"
        ],
    ) -> Iterator[tuple["MotionController", "FSoEMasterHandler"]]:
        mc, handler = mc_with_fsoe_with_sra_with_feedback_scenario_0

        self.sto = handler.get_function_instance(STOFunction)
        self.safe_inputs = handler.get_function_instance(SafeInputsFunction)
        self.ss1 = handler.get_function_instance(SS1Function)

        outputs = handler.process_image.outputs
        outputs.add(self.sto.command)
        outputs.add(self.ss1.command)
        outputs.add_padding(6)

        inputs = handler.process_image.inputs
        inputs.add(self.sto.command)
        inputs.add(self.ss1.command)
        inputs.add_padding(6)
        inputs.add(self.safe_inputs.value)
        inputs.add_padding(7)
        yield mc, handler

    @pytest.mark.fsoe_phase2
    def test_ss1_time_controlled_allowed(
        self,
        configured_handler: tuple["MotionController", "FSoEMasterHandler"],
        timeout_for_data_sra: float,
        servo: "EthercatServo",
        mcu_error_queue_a: "ServoErrorQueue",
        no_error_tracker: None,  # noqa: ARG002
    ) -> None:
        """With feedback scenario 0, SS1 time controlled is allowed."""
        mc, handler = configured_handler
        self.ss1.deceleration_limit.set(0)  # Configure SS1 time controlled
        handler.process_image.validate()
        mc.fsoe.configure_pdos()
        _check_op_state_reached_with_no_errors(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

    @pytest.mark.fsoe_phase2
    def test_ss1_ramp_monitored_not_allowed(
        self,
        configured_handler: tuple["MotionController", "FSoEMasterHandler"],
        timeout_for_data_sra: float,
        servo: "EthercatServo",
        mcu_error_queue_a: "ServoErrorQueue",
    ) -> None:
        """With feedback scenario 0, SS1 ramp monitored is not allowed."""
        mc, handler = configured_handler
        self.ss1.deceleration_limit.set(1)  # Configure SS1 time controlled
        handler.process_image.validate()
        mc.fsoe.configure_pdos()
        _check_invalid_map_error_is_raised(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

    @pytest.mark.fsoe_phase2
    def test_safe_input_mapped_toss1_r_not_allowed(
        self,
        configured_handler: tuple["MotionController", "FSoEMasterHandler"],
        timeout_for_data_sra: float,
        servo: "EthercatServo",
        mcu_error_queue_a: "ServoErrorQueue",
    ) -> None:
        """With feedback scenario 0, safe inputs are allowed if not mapped to SS1-r or SS2."""
        mc, handler = configured_handler

        # Configure SS1 time controlled and map safe inputs
        self.ss1.deceleration_limit.set(0)
        self.safe_inputs.map.set(2)

        # Map is valid, servo should reach OP state
        handler.process_image.validate()
        mc.fsoe.configure_pdos()
        _check_op_state_reached_with_no_errors(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

        # Map safe inputs to SS1-r - it should not reach OP state
        self.ss1.deceleration_limit.set(1)
        _check_invalid_map_error_is_raised(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

    @pytest.mark.fsoe_phase2
    def test_safe_input_mapped_to_ss2_not_allowed(
        self,
        configured_handler: tuple["MotionController", "FSoEMasterHandler"],
        timeout_for_data_sra: float,
        servo: "EthercatServo",
        mcu_error_queue_a: "ServoErrorQueue",
    ) -> None:
        """With feedback scenario 0, safe inputs are allowed if not mapped to SS1-r or SS2."""
        mc, handler = configured_handler
        handler.process_image.validate()
        mc.fsoe.configure_pdos()

        # Map safe inputs to SS2 - it should not reach OP state
        self.ss1.deceleration_limit.set(0)
        self.safe_inputs.map.set(3)
        _check_invalid_map_error_is_raised(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )


@pytest.fixture
def mc_with_fsoe_with_sra_with_feedback_scenario_0_with_sout(
    mc_with_fsoe_with_sra_with_feedback_scenario_0: tuple["MotionController", "FSoEMasterHandler"],
    setup_descriptor: "DriveHwSetup",
) -> Iterator[tuple["MotionController", "FSoEMasterHandler"]]:
    mc, handler = mc_with_fsoe_with_sra_with_feedback_scenario_0
    if handler.sout_function() is None:
        if setup_descriptor.identifier.upper() != PartNumber.DEN_S_NET_E.value:
            raise ValueError("SOUT function should be available in this dictionary.")
        pytest.skip("SOUT function not available in this dictionary.")
    yield mc, handler


class TestSoutDisabled:
    """If SOUT disable is set to 1, no SOUT-dependent safety functions are allowed.

    * SOUT command is not allowed.
    * STO activate SOUT and SS1 activate SOUT are not allowed to be enabled.
    * Safe Input cannot be mapped to SOUT.
    * Safe Input cannot be mapped to STO or SS1 if they activate SOUT.
    """

    @pytest.fixture(scope="function")
    def configured_handler(
        self,
        mc_with_fsoe_with_sra_with_feedback_scenario_0_with_sout: tuple[
            "MotionController", "FSoEMasterHandler"
        ],
    ) -> Iterator[tuple["MotionController", "FSoEMasterHandler"]]:
        mc, handler = mc_with_fsoe_with_sra_with_feedback_scenario_0_with_sout

        self.sto = handler.get_function_instance(STOFunction)
        self.safe_inputs = handler.get_function_instance(SafeInputsFunction)
        self.ss1 = handler.get_function_instance(SS1Function)

        outputs = handler.process_image.outputs
        outputs.add(self.sto.command)
        outputs.add(self.ss1.command)
        outputs.add_padding(6)

        inputs = handler.process_image.inputs
        inputs.add(self.sto.command)
        inputs.add(self.ss1.command)
        inputs.add_padding(6)
        inputs.add(self.safe_inputs.value)
        inputs.add_padding(7)
        yield mc, handler

    @pytest.mark.fsoe_phase2
    def test_sout_command_not_allowed(
        self,
        mc_with_fsoe_with_sra_with_feedback_scenario_0_with_sout: tuple[
            "MotionController", "FSoEMasterHandler"
        ],
        timeout_for_data_sra: float,
        servo: "EthercatServo",
        mcu_error_queue_a: "ServoErrorQueue",
    ) -> None:
        """SOUT command is not allowed if SOUT disable is set to 1."""
        mc, handler = mc_with_fsoe_with_sra_with_feedback_scenario_0_with_sout

        sto = handler.get_function_instance(STOFunction)
        safe_inputs = handler.get_function_instance(SafeInputsFunction)
        sout = handler.get_function_instance(SOutFunction)
        outputs = handler.process_image.outputs
        outputs.add(sto.command)
        outputs.add(sout.command)
        outputs.add_padding(6)

        inputs = handler.process_image.inputs
        inputs.add(sto.command)
        inputs.add(sout.command)
        inputs.add_padding(6)
        inputs.add(safe_inputs.value)
        inputs.add_padding(7)

        handler.process_image.validate()
        mc.fsoe.configure_pdos()
        _check_invalid_map_error_is_raised(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

    @pytest.mark.fsoe_phase2
    def test_sto_activate_sout_not_allowed(
        self,
        configured_handler: tuple["MotionController", "FSoEMasterHandler"],
        timeout_for_data_sra: float,
        servo: "EthercatServo",
        mcu_error_queue_a: "ServoErrorQueue",
    ) -> None:
        """STO activate SOUT is not allowed if SOUT disable is set to 1."""
        mc, handler = configured_handler
        handler.safety_parameters.get("FSOE_STO_ACTIVATE_SOUT").set(0x66600001)
        handler.process_image.validate()
        mc.fsoe.configure_pdos()
        _check_invalid_map_error_is_raised(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

    @pytest.mark.fsoe_phase2
    def test_ss1_activate_sout_not_allowed(
        self,
        configured_handler: tuple["MotionController", "FSoEMasterHandler"],
        timeout_for_data_sra: float,
        servo: "EthercatServo",
        mcu_error_queue_a: "ServoErrorQueue",
    ) -> None:
        """SS1 activate SOUT is not allowed if SOUT disable is set to 1."""
        mc, handler = configured_handler
        handler.safety_parameters.get("FSOE_SS1_ACTIVATE_SOUT_1").set(0x66600001)
        handler.process_image.validate()
        mc.fsoe.configure_pdos()
        _check_invalid_map_error_is_raised(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

    @pytest.mark.fsoe_phase2
    def test_safe_input_cannot_be_mapped_to_sout(
        self,
        configured_handler: tuple["MotionController", "FSoEMasterHandler"],
        timeout_for_data_sra: float,
        servo: "EthercatServo",
        mcu_error_queue_a: "ServoErrorQueue",
    ) -> None:
        """Safe Input cannot be mapped to SOUT if SOUT disable is set to 1."""
        mc, handler = configured_handler

        # Map safe inputs to SOUT - it should not reach OP state
        self.safe_inputs.map.set(4)
        handler.process_image.validate()
        mc.fsoe.configure_pdos()
        _check_invalid_map_error_is_raised(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

    @pytest.mark.fsoe_phase2
    def test_safe_input_cannot_be_mapped_to_sto_if_sto_activates_sout(
        self,
        configured_handler: tuple["MotionController", "FSoEMasterHandler"],
        timeout_for_data_sra: float,
        servo: "EthercatServo",
        mcu_error_queue_a: "ServoErrorQueue",
    ) -> None:
        """Safe Input cannot be mapped to STO if STO activates SOUT."""
        mc, handler = configured_handler

        # Map safe inputs to STO - it should reach OP state if STO does not activate SOUT
        self.safe_inputs.map.set(1)

        # It should reach OP state if STO does not activate SOUT
        handler.safety_parameters.get("FSOE_STO_ACTIVATE_SOUT").set(0)
        handler.process_image.validate()
        mc.fsoe.configure_pdos()
        _check_op_state_reached_with_no_errors(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

        # Set STO to activate SOUT, it should not reach OP state
        handler.safety_parameters.get("FSOE_STO_ACTIVATE_SOUT").set(0x66600001)
        _check_invalid_map_error_is_raised(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

    @pytest.mark.fsoe_phase2
    def test_safe_input_cannot_be_mapped_to_ss1_if_ss1_activates_sout(
        self,
        mc_with_fsoe_with_sra_with_feedback_scenario_0_with_sout: tuple[
            "MotionController", "FSoEMasterHandler"
        ],
        timeout_for_data_sra: float,
        servo: "EthercatServo",
        mcu_error_queue_a: "ServoErrorQueue",
    ) -> None:
        """Safe Input cannot be mapped to SS1 if SS1 activates SOUT."""
        mc, handler = mc_with_fsoe_with_sra_with_feedback_scenario_0_with_sout

        sto = handler.get_function_instance(STOFunction)
        safe_inputs = handler.get_function_instance(SafeInputsFunction)

        outputs = handler.process_image.outputs
        outputs.add(sto.command)
        outputs.add_padding(6)

        inputs = handler.process_image.inputs
        inputs.add(sto.command)
        inputs.add_padding(6)
        inputs.add(safe_inputs.value)
        inputs.add_padding(7)

        # Map safe inputs to SS1
        safe_inputs.map.set(2)

        # It should reach OP state if SS1 does not activate SOUT
        handler.safety_parameters.get("FSOE_SS1_ACTIVATE_SOUT_1").set(0)
        mc.fsoe.configure_pdos()
        _check_op_state_reached_with_no_errors(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )

        # Set SS1 to activate SOUT, it should not reach OP state
        handler.safety_parameters.get("FSOE_SS1_ACTIVATE_SOUT_1").set(0x66600001)
        _check_invalid_map_error_is_raised(
            mc=mc,
            servo=servo,
            mcu_error_queue_a=mcu_error_queue_a,
            timeout_for_data_sra=timeout_for_data_sra,
        )


@pytest.mark.parametrize(
    "current_errors, new_errors, new_error_index, generate_error_before_read, expected_errors",
    [
        (
            [0x80030002, 0x80030003, 0x80030004],
            [0x80030001],
            1,
            False,
            [0x80030001, 0x80030002, 0x80030003, 0x80030004],
        ),
        (
            [0x80030003, 0x80030004, 0x80030005],
            [0x80030001, 0x80030002],
            2,
            False,
            [0x80030001, 0x80030002, 0x80030003, 0x80030004, 0x80030005],
        ),
        (
            [0x80030002, 0x80030003, 0x80030004],
            [0x80030001],
            0,
            True,
            [0x80030001, 0x80030002, 0x80030003, 0x80030004],
        ),
        (
            [0x80030003, 0x80030004, 0x80030005],
            [0x80030001, 0x80030002],
            2,
            True,
            [0x80030001, 0x80030002, 0x80030003, 0x80030004, 0x80030005],
        ),
        (
            [0x80030004],
            [0x80030001, 0x80030002, 0x80030003],
            0,
            True,
            [0x80030001, 0x80030002, 0x80030003, 0x80030004],
        ),
        (
            [0x80030004],
            [0x80030001, 0x80030002, 0x80030003],
            0,
            False,
            [0x80030001, 0x80030002, 0x80030003, 0x80030004],
        ),
    ],
)
@pytest.mark.fsoe_phase2
def test_error_loss(
    mcu_error_queue_a: "ServoErrorQueue",
    mocker,
    current_errors: list[int],
    new_errors: list[int],
    new_error_index: int,
    generate_error_before_read: bool,
    expected_errors: list[int],
) -> None:
    """
    Test that `get_pending_errors` correctly handles new errors appearing during the read process.

    This simulates a scenario where:
    - `current_errors` are initially in the queue.
    - `new_errors` appear dynamically while reading, triggered when a specific index
    (`new_error_index`) is accessed.
    - The `generate_error_before_read` flag determines if new errors are generated
      before or after reading the error at `new_error_index`.
    - The method should return all errors (including new ones) in reverse order (newest first).

    Expected behavior:
    - No errors are lost.
    - The final list matches `expected_errors`.
    """

    class MockServoErrorQueue:
        """
        Mock implementation of ServoErrorQueue to simulate dynamic error insertion.
        - When `get_error_by_index` reaches `new_error_index`, new errors are inserted at the front.
        """

        def __init__(
            self,
            current_errors: list[int],
            new_errors: list[int],
            new_error_index: int,
            generate_before_read: bool,
        ) -> None:
            self._error_stack = current_errors
            self._new_errors = new_errors
            self._new_error_index = new_error_index
            self._last_read_index = -1
            self._new_errors_generated = False
            self._generate_before_read = generate_before_read

        def get_number_total_errors(self) -> int:
            return len(self._error_stack)

        def _generate_new_errors(self):
            # Insert new errors only once when the trigger index is reached
            if self._new_errors_generated:
                return
            self._error_stack = self._new_errors + self._error_stack
            self._new_errors_generated = True

        def get_error_by_index(self, index) -> "Error":
            if self._generate_before_read and index == self._new_error_index:
                self._generate_new_errors()
            self._last_read_index = index
            index_error = Error.from_id(self._error_stack[index])
            if not self._generate_before_read and index == self._new_error_index:
                self._generate_new_errors()
            return index_error

    # Patch the real queue methods with our mock
    mocked_error_queue = MockServoErrorQueue(
        current_errors, new_errors, new_error_index, generate_error_before_read
    )
    mocker.patch.object(
        mcu_error_queue_a,
        "get_number_total_errors",
        side_effect=mocked_error_queue.get_number_total_errors,
    )
    mocker.patch.object(
        mcu_error_queue_a, "get_error_by_index", side_effect=mocked_error_queue.get_error_by_index
    )

    # Execute and verify
    errors, _ = mcu_error_queue_a.get_pending_errors()
    assert [error.error_id for error in errors] == expected_errors

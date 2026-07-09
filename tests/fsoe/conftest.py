import logging
import random
from collections import OrderedDict
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, Union

import pytest
from ingenialink import RegAccess, RegDtype
from ingenialink.dictionary import CanOpenObject, Interface
from ingenialink.enums.register import RegCyclicType
from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.network import Network
from ingenialink.pdo_network_manager import PDONetworkManager as ILPDONetworkManager
from ingenialink.servo import DictionaryFactory, Servo
from ingenialink.utils._utils import convert_dtype_to_bytes

from ingeniamotion.enums import FSoEState
from ingeniamotion.errors import (
    FSOE_MCUA_ERROR_QUEUE,
    FSOE_MCUB_ERROR_QUEUE,
    ServoErrorQueue,
)
from ingeniamotion.exceptions import IMErrorQueueNotExistsError
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEError
from tests.dictionaries import SAMPLE_SAFE_PH2_XDFV3_DICTIONARY

logger = logging.getLogger(__name__)

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import (
        FSoEMasterHandler,
        ProcessImage,
        SafeInputsFunction,
        SafetyFunction,
        SafetyParameter,
        SS1Function,
        STOFunction,
    )
    from tests.fsoe.utils.map_generator import FSoERandomMappingGenerator


if TYPE_CHECKING:
    from ingenialink.emcy import EmergencyMessage
    from ingenialink.ethercat.dictionary import EthercatDictionary
    from ingenialink.register import Register
    from summit_testing_framework.pytest_helpers.pytest_output_handler import PytestOutputHandler

    from ingeniamotion.fsoe_master import FSoEDictionary
    from ingeniamotion.motion_controller import MotionController


TIMEOUT_FOR_DATA = 30
TIMEOUT_FOR_DATA_SRA = 3


def emergency_handler(servo_alias: str, message: "EmergencyMessage") -> None:
    if message.error_code == 0xFF43:
        # Cyclic timeout Ethercat PDO lifeguard
        # is a typical error code when the pdos are stopped
        # Ignore
        return

    if message.error_code == 0:
        # When drive goes to Operational again
        # No error is thrown
        # https://novantamotion.atlassian.net/browse/INGM-627
        return

    raise RuntimeError(f"Emergency message received from {servo_alias}: {message}")


@pytest.fixture
def mcu_error_queue_a(servo: "EthercatServo") -> Optional["ServoErrorQueue"]:
    try:
        return ServoErrorQueue(FSOE_MCUA_ERROR_QUEUE, servo, axis=1)
    except IMErrorQueueNotExistsError:
        return None  # Queue does not exist in phase 1


@pytest.fixture
def mcu_error_queue_b(servo: "EthercatServo") -> Optional["ServoErrorQueue"]:
    try:
        return ServoErrorQueue(FSOE_MCUB_ERROR_QUEUE, servo, axis=1)
    except IMErrorQueueNotExistsError:
        return None  # Queue does not exist in phase 1


@dataclass(frozen=True)
class FSoEErrorDisplay:
    """Class to display FSoE errors in tests."""

    error: FSoEError
    """Main error that was reported."""
    states: list[FSoEState]
    """State transitions that occurred until the error."""

    @property
    def display(self) -> str:
        """Get a text representation of the error."""
        return f"{str(self.error)}\n  FSoE States: {self.states}"


@pytest.fixture(scope="function")
def fsoe_error_monitor(
    mcu_error_queue_a: Optional["ServoErrorQueue"],
    mcu_error_queue_b: Optional["ServoErrorQueue"],
    fsoe_states: list[FSoEState],
) -> Iterator[Callable[[FSoEError], None]]:
    errors: list[FSoEErrorDisplay] = []

    # Establish baseline so get_pending_errors() only returns test-scoped errors.
    if mcu_error_queue_a is not None:
        mcu_error_queue_a.get_pending_errors()
    if mcu_error_queue_b is not None:
        mcu_error_queue_b.get_pending_errors()

    def error_handler(error: FSoEError) -> None:
        # WARNING: This callback runs in the PDO thread. Avoid heavy processing
        # (e.g. SDO reads) to prevent SM watchdog trips.
        logger.error(
            "Captured FSoE error during test: %s",
            FSoEErrorDisplay(error, fsoe_states.copy()).display,
        )
        errors.append(
            FSoEErrorDisplay(
                error=error,
                states=fsoe_states.copy(),
            )
        )

    yield error_handler

    # Teardown: report FSoE errors + MCU errors (safe to do SDO reads here,
    # the master is already stopped by the test body).
    if errors:
        parts = [error.display for error in errors]
        for queue, label in [(mcu_error_queue_a, "MCUA"), (mcu_error_queue_b, "MCUB")]:
            if queue is not None:
                pending, lost = queue.get_pending_errors()
                if pending:
                    parts.append(f"{label} errors ({len(pending)}):")
                    parts.extend(f"  {e}" for e in pending)
                if lost:
                    parts.append(f"  WARNING: Some {label} errors lost (buffer overflow)")
        pytest.fail("FSoE errors occurred:\n" + "\n".join(parts))


@pytest.fixture()
def fsoe_states() -> list["FSoEState"]:
    states: list[FSoEState] = []
    return states


def __set_default_phase2_mapping(handler: "FSoEMasterHandler") -> None:
    sto = handler.get_function_instance(STOFunction)
    safe_inputs = handler.get_function_instance(SafeInputsFunction)
    ss1 = handler.get_function_instance(SS1Function)

    handler.process_image.inputs.clear()
    handler.process_image.inputs.add(sto.command)
    handler.process_image.inputs.add(ss1.command)
    handler.process_image.inputs.add_padding(6)
    handler.process_image.inputs.add(safe_inputs.value)
    handler.process_image.inputs.add_padding(7)

    handler.process_image.outputs.clear()
    handler.process_image.outputs.add(sto.command)
    handler.process_image.outputs.add(ss1.command)
    handler.process_image.outputs.add_padding(6)


@pytest.fixture
def mc_with_fsoe_factory(
    request: pytest.FixtureRequest, mc: "MotionController", fsoe_states: list["FSoEState"]
) -> Iterator[Callable[[bool, bool], tuple["MotionController", "FSoEMasterHandler"]]]:
    created_handlers = []

    def factory(
        use_sra: bool = False, fail_on_fsoe_errors: bool = True
    ) -> tuple["MotionController", "FSoEMasterHandler"]:
        def add_state(state: FSoEState) -> None:
            fsoe_states.append(state)

        # Subscribe to emergency messages
        mc.communication.subscribe_emergency_message(emergency_handler)
        # Create and start the FSoE master handler
        handler = mc.fsoe.create_fsoe_master_handler(
            use_sra=use_sra, state_change_callback=add_state
        )
        if fail_on_fsoe_errors:
            # Configure error channel
            mc.fsoe.subscribe_to_errors(request.getfixturevalue(fsoe_error_monitor.__name__))
        created_handlers.append(handler)
        # If phase II, initialize the handler with the default mapping
        # and set feedback scenario to 0
        if handler.process_image.editable:
            __set_default_phase2_mapping(handler)
            handler.safety_parameters.get("FSOE_FEEDBACK_SCENARIO").set(0)

        if handler.sout_function() is not None:
            handler.sout_disable()

        return mc, handler

    yield factory

    # Stop the master, PDOs are stopped on mc teardown
    mc.fsoe.stop_master(stop_pdos=False)
    mc.fsoe._delete_master_handler()


@pytest.fixture()
def mc_with_fsoe(
    mc_with_fsoe_factory: Callable[..., tuple["MotionController", "FSoEMasterHandler"]],
) -> Iterator[tuple["MotionController", "FSoEMasterHandler"]]:
    yield mc_with_fsoe_factory(use_sra=False, fail_on_fsoe_errors=True)


@pytest.fixture()
def mc_with_fsoe_with_sra(
    mc_with_fsoe_factory: Callable[..., tuple["MotionController", "FSoEMasterHandler"]],
) -> Iterator[tuple["MotionController", "FSoEMasterHandler"]]:
    yield mc_with_fsoe_factory(use_sra=True, fail_on_fsoe_errors=True)


@pytest.fixture()
def mc_state_data_with_sra(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
) -> Iterator["MotionController"]:
    mc, _handler = mc_with_fsoe_with_sra

    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=TIMEOUT_FOR_DATA_SRA)

    # Remove fail-safe state
    mc.fsoe.set_fail_safe(False)

    yield mc

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.fixture()
def mc_state_data(
    mc_with_fsoe: tuple["MotionController", "FSoEMasterHandler"],
) -> Iterator["MotionController"]:
    mc, _ = mc_with_fsoe

    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=TIMEOUT_FOR_DATA)

    # Remove fail-safe state
    mc.fsoe.set_fail_safe(False)

    yield mc

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.fixture
def no_error_tracker(
    mcu_error_queue_a: Optional["ServoErrorQueue"], mcu_error_queue_b: Optional["ServoErrorQueue"]
) -> Iterator[None]:
    """Fixture to ensure no new errors are added to the error queues during a test."""
    previous_mcu_a_errors = (
        mcu_error_queue_a.get_number_total_errors() if mcu_error_queue_a is not None else None
    )
    previous_mcu_b_errors = (
        mcu_error_queue_b.get_number_total_errors() if mcu_error_queue_b is not None else None
    )
    yield
    if mcu_error_queue_a is not None:
        assert mcu_error_queue_a.get_number_total_errors() == previous_mcu_a_errors, (
            f"MCUA error queue changed: {previous_mcu_a_errors} -> "
            f"{mcu_error_queue_a.get_number_total_errors()}. "
            f"\nLast error: {mcu_error_queue_a.get_last_error()}"
        )
    if mcu_error_queue_b is not None:
        assert mcu_error_queue_b.get_number_total_errors() == previous_mcu_b_errors, (
            f"MCUB error queue changed: {previous_mcu_b_errors} -> "
            f"{mcu_error_queue_b.get_number_total_errors()}. "
            f"\nLast error: {mcu_error_queue_b.get_last_error()}"
        )


@pytest.fixture
def mc_with_fsoe_with_sra_and_feedback_scenario(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
) -> Iterator[tuple["MotionController", "FSoEMasterHandler"]]:
    """Fixture to provide a MotionController with FSoE and SRA configured with feedback scenario 4.

    Feedback Scenario 4:
        * Main feedback: Incremental Encoder.
        * Redundant feedback: Digital Halls.

    Yields:
        A tuple with the MotionController and the FSoEMasterHandler.
    """
    mc, handler = mc_with_fsoe_with_sra

    mc.communication.set_register(
        "CL_AUX_FBK_SENSOR", 5
    )  # Digital Halls as auxiliar sensor in Comoco
    handler.safety_parameters.get("FSOE_FEEDBACK_SCENARIO").set(4)

    yield mc, handler

    # If there has been a failure and it tries to remove the PDO maps, it may fail
    # if the servo is not in preop state
    try:
        if mc.capture.pdo.is_active():
            mc.fsoe.stop_master(stop_pdos=True)
    except Exception:
        pass


@pytest.fixture(scope="session")
def safe_dict() -> "EthercatDictionary":
    axis_1 = 1
    safe_dict = DictionaryFactory.create_dictionary(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, interface=Interface.ECAT
    )

    # Add sample registers
    safe_dict._registers[axis_1]["TEST_SI_U16"] = EthercatRegister(
        idx=0xF000,
        subidx=0,
        dtype=RegDtype.U16,
        access=RegAccess.RO,
        identifier="TEST_SI_U16",
        pdo_access=RegCyclicType.SAFETY_INPUT,
        cat_id="FSOE",
    )
    safe_dict._registers[axis_1]["TEST_SI_U8"] = EthercatRegister(
        idx=0xF001,
        subidx=0,
        dtype=RegDtype.U8,
        access=RegAccess.RO,
        identifier="TEST_SI_U8",
        pdo_access=RegCyclicType.SAFETY_INPUT,
        cat_id="FSOE",
    )

    # Add more CRC registers
    safe_dict._registers[axis_1]["FSOE_SLAVE_FRAME_ELEM_CRC2"] = EthercatRegister(
        idx=0xF002,
        subidx=0,
        dtype=RegDtype.U16,
        access=RegAccess.RO,
        identifier="FSOE_SLAVE_FRAME_ELEM_CRC2",
        pdo_access=RegCyclicType.SAFETY_INPUT,
        cat_id="FSOE",
    )
    safe_dict._registers[axis_1]["FSOE_SLAVE_FRAME_ELEM_CRC3"] = EthercatRegister(
        idx=0xF003,
        subidx=0,
        dtype=RegDtype.U16,
        access=RegAccess.RO,
        identifier="FSOE_SLAVE_FRAME_ELEM_CRC3",
        pdo_access=RegCyclicType.SAFETY_INPUT,
        cat_id="FSOE",
    )
    return safe_dict


@pytest.fixture(scope="session")
def fsoe_dict(safe_dict: "EthercatDictionary") -> Iterator["FSoEDictionary"]:
    return FSoEMasterHandler.create_safe_dictionary(safe_dict)


@pytest.fixture(scope="module")
def fsoe_maps_dir(test_output_handler: "PytestOutputHandler") -> Iterator[Path]:
    """Returns the directory where FSoE maps are stored.

    This directory is created if it does not exist.
    If the directory is empty after the tests, it will be removed.

    Yields:
        Path to the FSoE maps directory.
    """
    directory = test_output_handler.tests_output_dir / "fsoe_maps"
    directory.mkdir(parents=True, exist_ok=True)
    yield directory
    if not any(directory.iterdir()):
        directory.rmdir()


@pytest.fixture
def random_seed() -> int:
    """Returns a fixed random seed for reproducibility."""
    return random.randint(0, 1000)


@pytest.fixture
def random_paddings() -> bool:
    """Returns a random boolean for testing random paddings."""
    return random.choice([True, False])


@pytest.fixture
def random_max_items() -> int:
    """Returns a random integer for testing max items."""
    return random.randint(1, 10)


@pytest.fixture
def map_generator() -> Iterator["FSoERandomMappingGenerator"]:
    """Fixture to provide a random mapping generator.

    Yields:
        FSoERandomMappingGenerator instance.
    """
    yield FSoERandomMappingGenerator()


@pytest.fixture(scope="session")
def timeout_for_data() -> float:
    """Returns the timeout value for the Data state for handler without SRA."""
    return TIMEOUT_FOR_DATA


@pytest.fixture(scope="session")
def timeout_for_data_sra() -> float:
    """Returns the timeout value for the Data state for handler using SRA."""
    return TIMEOUT_FOR_DATA_SRA


class MockNetwork(EthercatNetwork):
    def __init__(self) -> None:
        Network.__init__(self)

        self._pdo_manager = ILPDONetworkManager(self)


class MockServo(Servo):
    interface = Interface.ECAT

    def __init__(self, dictionary_path: str) -> None:
        super().__init__(target=1, dictionary_path=dictionary_path)

        self.current_values = {
            register: convert_dtype_to_bytes(register.default, register.dtype)
            for register in self.dictionary.all_registers()
        }

    def _write_raw(self, reg: "Register", data: bytes, **kwargs: Any) -> None:
        self.current_values[reg] = data

    def _read_raw(self, reg: "Register", **kwargs: Any) -> bytes:
        return self.current_values[reg]

    def read_complete_access(
        self, reg: Union[str, "Register", "CanOpenObject"], *args, **kwargs
    ) -> bytes:
        if not isinstance(reg, CanOpenObject):
            raise NotImplementedError

        value = bytearray()

        for register in reg:
            value += self.current_values[register]
            if register.subidx == 0:
                value += b"\00"  # Padding after first u8 element

        return bytes(value)

    read_rpdo_map_from_slave = EthercatServo.read_rpdo_map_from_slave
    read_tpdo_map_from_slave = EthercatServo.read_tpdo_map_from_slave


if FSOE_MASTER_INSTALLED:

    class MockSafetyParameter(SafetyParameter):
        def __init__(self, register: "EthercatRegister", servo: "EthercatServo") -> None:
            self.__register = register
            self.__servo = servo

            self.__value = 0

        @property
        def register(self) -> "EthercatRegister":
            """Get the register associated with the safety parameter."""
            return self.__register

        def set(self, value):
            self.__value = value

        def get(self) -> Any:
            return self.__value

    class MockHandler(FSoEMasterHandler):
        def __init__(self, dictionary: str, module_uid: int):
            xdf = DictionaryFactory.create_dictionary(dictionary, interface=Interface.ECAT)
            self.dictionary = FSoEMasterHandler.create_safe_dictionary(xdf)
            self.__servo = MockServo(dictionary)
            self._process_image = ProcessImage.default(self.dictionary)
            self.safety_parameters = OrderedDict({
                app_parameter.uid: MockSafetyParameter(
                    xdf.get_register(app_parameter.uid), self.__servo
                )
                for app_parameter in xdf.get_safety_module(module_uid).application_parameters
            })

            self.safety_functions = tuple(SafetyFunction.for_handler(self))

        @property
        def process_image(self) -> "ProcessImage":
            return self._process_image

        def set_process_image(self, process_image: "ProcessImage") -> None:
            self._process_image = process_image

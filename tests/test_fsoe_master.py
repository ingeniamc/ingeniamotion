from typing import TYPE_CHECKING

import pytest

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import (
    FSOE_MASTER_INSTALLED,
    FSoEError,
    SafeInputsFunction,
    SS1Function,
    STOFunction,
)
from ingeniamotion.motion_controller import MotionController
from tests.conftest import timeout_loop

if FSOE_MASTER_INSTALLED:
    from fsoe_master import fsoe_master


if TYPE_CHECKING:
    from ingenialink.emcy import EmergencyMessage


def test_fsoe_master_not_installed():
    try:
        import fsoe_master  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        pytest.skip("fsoe_master is installed")

    mc = MotionController()
    with pytest.raises(NotImplementedError):
        mc.fsoe


def emergency_handler(servo_alias: str, message: "EmergencyMessage"):
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


def error_handler(error: FSoEError):
    raise RuntimeError(f"FSoE error received: {error}")


@pytest.fixture()
def mc_with_fsoe(mc):
    # Subscribe to emergency messages
    mc.communication.subscribe_emergency_message(emergency_handler)
    # Configure error channel
    mc.fsoe.subscribe_to_errors(error_handler)
    # Create and start the FSoE master handler
    handler = mc.fsoe.create_fsoe_master_handler()
    yield mc, handler
    # IM should be notified and clear references when a servo is disconnected from ingenialink
    # https://novantamotion.atlassian.net/browse/INGM-624
    mc.fsoe._delete_master_handler()


@pytest.mark.fsoe
def test_fsoe_master_get_safety_parameters(mc_with_fsoe):
    mc, handler = mc_with_fsoe

    assert len(handler.safety_parameters) != 0


@pytest.mark.fsoe
def test_mandatory_safety_functions(mc_with_fsoe):
    mc, handler = mc_with_fsoe

    safety_functions_by_types = handler.safety_functions_by_type()

    sto_instances = safety_functions_by_types[STOFunction]
    assert len(sto_instances) == 1

    ss1_instances = safety_functions_by_types[SS1Function]
    assert len(ss1_instances) >= 1

    si_instances = safety_functions_by_types[SafeInputsFunction]
    assert len(si_instances) == 1


@pytest.mark.fsoe
def test_getter_of_safety_functions(mc_with_fsoe):
    mc, handler = mc_with_fsoe

    sto_function = STOFunction(command=None, io=None, parameters=None)
    ss1_function_1 = SS1Function(command=None, time_to_sto=None, io=None, parameters=None)
    ss1_function_2 = SS1Function(command=None, time_to_sto=None, io=None, parameters=None)

    handler.safety_functions = (sto_function, ss1_function_1, ss1_function_2)
    handler.get_function_instance.cache_clear()

    # Single instance of STOFunction
    assert handler.get_function_instance(STOFunction) is sto_function
    assert handler.get_function_instance(STOFunction, instance=1) is sto_function

    # Multiple instances of SS1Function
    with pytest.raises(ValueError) as error:
        # Must specify the instance
        handler.get_function_instance(SS1Function)
    assert (
        error.value.args[0]
        == "Multiple SS1Function instances found (2). Specify the instance number."
    )

    with pytest.raises(IndexError) as error:
        # Instance 0 does not exist
        handler.get_function_instance(SS1Function, instance=0)
    assert error.value.args[0] == "Master handler does not contain SS1Function instance 0"
    assert handler.get_function_instance(SS1Function, instance=1) is ss1_function_1
    assert handler.get_function_instance(SS1Function, instance=2) is ss1_function_2
    with pytest.raises(IndexError) as error:
        # Instance 3 does not exist
        handler.get_function_instance(SS1Function, instance=3)
    assert error.value.args[0] == "Master handler does not contain SS1Function instance 3"


@pytest.fixture()
def mc_state_data(mc_with_fsoe):
    mc, handler = mc_with_fsoe

    mc.fsoe.configure_pdos(start_pdos=True)
    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=10)

    yield mc

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
def test_safe_inputs_value(mc_state_data):
    mc = mc_state_data

    value = mc.fsoe.get_safety_inputs_value()

    # Assume safe inputs are disconnected on the setup
    assert value == 0


@pytest.mark.fsoe
def test_safety_address(mc_with_fsoe, alias):
    mc, handler = mc_with_fsoe

    master_handler = mc.fsoe._handlers[alias]

    mc.fsoe.set_safety_address(0x7453)
    # Setting the safety address has effects on the master
    assert master_handler._master_handler.master.session.slave_address.value == 0x7453

    # And on the slave
    assert mc.communication.get_register("FSOE_MANUF_SAFETY_ADDRESS") == 0x7453

    # The getter also works
    assert mc.fsoe.get_safety_address() == 0x7453


def mc_state_to_fsoe_master_state(state: FSoEState):
    return {
        FSoEState.RESET: fsoe_master.StateReset,
        FSoEState.SESSION: fsoe_master.StateSession,
        FSoEState.CONNECTION: fsoe_master.StateConnection,
        FSoEState.PARAMETER: fsoe_master.StateParameter,
        FSoEState.DATA: fsoe_master.StateData,
    }[state]


@pytest.mark.fsoe
@pytest.mark.parametrize(
    "state_enum",
    [
        FSoEState.RESET,
        FSoEState.SESSION,
        FSoEState.CONNECTION,
        FSoEState.PARAMETER,
        FSoEState.DATA,
    ],
)
def test_get_master_state(mocker, mc_with_fsoe, state_enum):
    mc, handler = mc_with_fsoe

    # Master state is obtained as function
    # and not on the parametrize
    # to avoid depending on the optionally installed module
    # on pytest collection
    fsoe_master_state = mc_state_to_fsoe_master_state(state_enum)

    mocker.patch("fsoe_master.fsoe_master.MasterHandler.state", fsoe_master_state)

    assert mc.fsoe.get_fsoe_master_state() == state_enum


@pytest.mark.fsoe
def test_motor_enable(mc_state_data):
    mc = mc_state_data

    # Deactivate the SS1
    mc.fsoe.ss1_deactivate()
    # Deactivate the STO
    mc.fsoe.sto_deactivate()
    # Wait for the STO to be deactivated
    for _ in timeout_loop(
        timeout_sec=5, other=RuntimeError("Timeout waiting for STO deactivation")
    ):
        if not mc.fsoe.check_sto_active():
            break
    # Enable the motor
    mc.motion.motor_enable()
    # Disable the motor
    mc.motion.motor_disable()
    # Activate the SS1
    mc.fsoe.sto_activate()
    # Activate the STO
    mc.fsoe.sto_activate()

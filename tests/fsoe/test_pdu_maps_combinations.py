import time

import pytest

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController

if FSOE_MASTER_INSTALLED:
    import ingeniamotion.fsoe_master.safety_functions as safety_functions


def emergency_handler(servo_alias: str, message) -> None:
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


def error_handler(error) -> None:
    raise RuntimeError(f"FSoE error received: {error}")


# @pytest.fixture
# def delete_master_handler():
#     mc = MotionController()
#     yield
#     mc.fsoe._delete_master_handler()


def common_test(mc, handler):
    # Get the safety functions instances
    sto = handler.get_function_instance(safety_functions.STOFunction)
    safe_inputs = handler.get_function_instance(safety_functions.SafeInputsFunction)
    ss1 = handler.get_function_instance(safety_functions.SS1Function)
    ss2 = handler.get_function_instance(safety_functions.SS2Function, instance=1)
    sa = handler.get_function_instance(safety_functions.SAFunction)
    sv = handler.get_function_instance(safety_functions.SVFunction)
    sos = handler.get_function_instance(safety_functions.SOSFunction)

    # The handler comes with a default mapping read from the drive.
    # Clear it to create a new one
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()

    # # Configure Outputs map
    outputs = handler.maps.outputs
    outputs.add(sto.command)
    outputs.add(ss1.command)
    outputs.add(sos.command)
    outputs.add(ss2.command)
    outputs.add_padding(4 + 8)

    # # # Configure Inputs Map
    inputs = handler.maps.inputs
    inputs.add(sto.command)
    inputs.add(ss1.command)
    inputs.add(safe_inputs.value)
    inputs.add_padding(7)

    # Print the maps to check the configuration
    print("Inputs Map:")
    print(inputs.get_text_representation())
    print("Outputs Map:")
    print(outputs.get_text_representation())

    mc.fsoe.configure_pdos()

    # After reconfiguring the maps and configuring the pdos,
    # The PDOs can be printed to check the mapping
    print("Outputs PDO Map:")
    print(handler.safety_master_pdu_map.get_text_representation())
    print("Inputs PDO Map:")
    print(handler.safety_slave_pdu_map.get_text_representation())

    # Start pdo transmission
    mc.capture.pdo.start_pdos()

    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=10)

    for i in range(5):
        time.sleep(1)
        # During this time, commands can be changed
        sto.command.set(1)
        ss1.command.set(1)
        # And inputs can be read
        print(f"Safe Inputs Value: {safe_inputs.value.get()}")

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)
    mc.fsoe._delete_master_handler()


@pytest.mark.fsoe
def test_mappings(setup_descriptor) -> None:
    mc = MotionController()
    # mc.communication.subscribe_emergency_message(emergency_handler)
    # Configure error channel
    mc.communication.connect_servo_ethercat(
        setup_descriptor.ifname, setup_descriptor.slave, setup_descriptor.dictionary
    )
    mc.fsoe.subscribe_to_errors(lambda error: print(error))
    handler = mc.fsoe.create_fsoe_master_handler(use_sra=True)
    common_test(mc, handler)


@pytest.mark.fsoe
def test_mappings_with_fixture(mc_with_fsoe_with_sra) -> None:
    mc, handler = mc_with_fsoe_with_sra
    common_test(mc, handler)

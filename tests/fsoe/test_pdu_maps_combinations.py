import time

import pytest
from ingenialogger import get_logger

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

if FSOE_MASTER_INSTALLED:
    import ingeniamotion.fsoe_master.safety_functions as safety_functions


logger = get_logger(__name__)


@pytest.mark.fsoe
def test_mappings_with_mc_and_fsoe_fixture(mc_with_fsoe_with_sra) -> None:
    mc, handler = mc_with_fsoe_with_sra
    # Get the safety functions instances
    sto = handler.get_function_instance(safety_functions.STOFunction)
    safe_inputs = handler.get_function_instance(safety_functions.SafeInputsFunction)
    ss1 = handler.get_function_instance(safety_functions.SS1Function)
    ss2 = handler.get_function_instance(safety_functions.SS2Function, instance=1)
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

    # Configure Inputs Map
    inputs = handler.maps.inputs
    inputs.add(sto.command)
    inputs.add(ss1.command)
    inputs.add(safe_inputs.value)
    inputs.add_padding(7)

    # Print the maps to check the configuration
    logger.info("Inputs Map:")
    logger.info(inputs.get_text_representation())
    logger.info("Outputs Map:")
    logger.info(outputs.get_text_representation())

    mc.fsoe.configure_pdos()

    # After reconfiguring the maps and configuring the pdos,
    # The PDOs can be printed to check the mapping
    logger.info("Outputs PDO Map:")
    logger.info(handler.safety_master_pdu_map.get_text_representation())
    logger.info("Inputs PDO Map:")
    logger.info(handler.safety_slave_pdu_map.get_text_representation())

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
        logger.info(f"Safe Inputs Value: {safe_inputs.value.get()}")

    # Stop the FSoE master handler
    logger.info("stopping master handler")
    mc.fsoe.stop_master(stop_pdos=True)
    logger.info("master handler stopped")
    mc.fsoe._delete_master_handler()
    logger.info("master handler deleted")

import random
import time
from pathlib import Path

import pytest
from ingenialogger import get_logger

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController

if FSOE_MASTER_INSTALLED:
    import ingeniamotion.fsoe_master.safety_functions as safety_functions
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
    from ingeniamotion.fsoe_master.safety_functions import SafetyFunction
    from tests.fsoe.conftest import FSoERandomMappingGenerator


logger = get_logger(__name__)


@pytest.fixture(scope="session")
def fsoe_maps_dir(request: pytest.FixtureRequest) -> Path:
    """Returns the directory where FSoE maps are stored."""
    return Path(request.config.rootdir).resolve() / "fsoe_maps"


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


@pytest.mark.fsoe_phase_II
@pytest.mark.parametrize("iteration", range(5))  # Run 5 times
def test_map_safety_input_output_random(
    mc_with_fsoe_with_sra: tuple[MotionController, FSoEMasterHandler],
    mapping_generator: FSoERandomMappingGenerator,
    fsoe_maps_dir: Path,
    random_seed: int,
    random_max_items: int,
    random_paddings: bool,
    iteration: int,
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    mapping_file = (
        fsoe_maps_dir
        / f"test_mapping_{random_max_items}_{random_paddings}_{random_seed}_{iteration}.json"
    )

    # Generate a random mapping
    mapping_generator.generate_and_save_random_mapping(
        handler=handler,
        max_items=random_max_items,
        random_paddings=random_paddings,
        seed=random_seed,
        filename=mapping_file,
        override=True,
    )
    handler.maps.validate()

    mc.fsoe.configure_pdos()

    # After reconfiguring the maps and configuring the pdos,
    # The PDOs can be printed to check the mapping
    logger.info("Outputs PDO Map:")
    logger.info(handler.safety_master_pdu_map.get_text_representation())
    logger.info("Inputs PDO Map:")
    logger.info(handler.safety_slave_pdu_map.get_text_representation())

    mc.capture.pdo.start_pdos()
    logger.info("PDOs started")
    mc.fsoe.wait_for_state_data(timeout=10)
    logger.info("FSoE Master reached Data state")
    # Stay 3 seconds in Data state
    for i in range(3):
        time.sleep(1)
    logger.info("Stopping FSoE Master handler")
    mc.fsoe.stop_master(stop_pdos=True)

    mapping_file.unlink()


@pytest.mark.fsoe_phase_II
def test_map_all_safety_functions(
    mc_with_fsoe_with_sra: tuple[MotionController, FSoEMasterHandler],
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    inputs = handler.maps.inputs
    outputs = handler.maps.outputs

    # The handler comes with a default mapping read from the drive.
    # Clear it to create a new one
    inputs.clear()
    outputs.clear()

    for sf in SafetyFunction.for_handler(handler):
        if hasattr(sf, "command"):
            handler.maps.insert_in_best_position(sf.command)
        else:
            handler.maps.insert_in_best_position(sf.value)

    # Check that the maps are valid
    handler.maps.validate()
    mc.fsoe.configure_pdos()

    logger.info("Outputs PDO Map:")
    logger.info(handler.safety_master_pdu_map.get_text_representation())
    logger.info("Inputs PDO Map:")
    logger.info(handler.safety_slave_pdu_map.get_text_representation())

    mc.capture.pdo.start_pdos()
    mc.fsoe.wait_for_state_data(timeout=10)
    # Stay 3 seconds in Data state
    for i in range(3):
        time.sleep(1)
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe_phase_II
def test_mappings_with_mc_and_fsoe_fixture(
    mc_with_fsoe_with_sra: tuple[MotionController, FSoEMasterHandler],
) -> None:
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

    # Check that the maps are valid
    handler.maps.validate()

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

    logger.info("Test finished. Stopping FSoE Master handler")
    mc.fsoe.stop_master(stop_pdos=True)

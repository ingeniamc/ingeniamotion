import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from summit_testing_framework.setups.specifiers import DriveHwConfigSpecifier

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController

if FSOE_MASTER_INSTALLED:
    import ingeniamotion.fsoe_master.safety_functions as safety_functions
    from ingeniamotion.fsoe_master.safety_functions import SafetyFunction
    from tests.fsoe.map_json_serializer import FSoEDictionaryMapJSONSerializer

    if TYPE_CHECKING:
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
        from ingeniamotion.fsoe_master.maps import PDUMaps
        from tests.fsoe.conftest import FSoERandomMappingGenerator


def _check_mappings_have_the_same_length(maps: "PDUMaps") -> None:
    if maps.inputs.safety_bits > maps.outputs.safety_bits:
        maps.outputs.add_padding(maps.inputs.safety_bits - maps.outputs.safety_bits)
    elif maps.outputs.safety_bits > maps.inputs.safety_bits:
        maps.inputs.add_padding(maps.outputs.safety_bits - maps.inputs.safety_bits)
    assert maps.inputs.safety_bits == maps.outputs.safety_bits


@pytest.mark.fsoe_phase2
@pytest.mark.parametrize("iteration", range(10))  # Run 10 times
@pytest.mark.xfail(reason="Maybe not all random mappings are valid")
def test_map_safety_input_output_random(
    mc_with_fsoe_with_sra: tuple[MotionController, "FSoEMasterHandler"],
    map_generator: "FSoERandomMappingGenerator",
    fsoe_maps_dir: Path,
    timeout_for_data_sra: float,
    random_seed: int,
    random_max_items: int,
    random_paddings: bool,
    setup_specifier_with_esi: DriveHwConfigSpecifier,
    iteration: int,  # noqa: ARG001
) -> None:
    """Tests that random combinations of inputs and outputs are valid."""
    mc, handler = mc_with_fsoe_with_sra

    mapping_name = f"mapping_{random_max_items}_{random_paddings}_{random_seed}"
    json_file = fsoe_maps_dir / f"{mapping_name}.json"
    sci_file = fsoe_maps_dir / f"{mapping_name}.sci"

    # Generate a random mapping and validate it
    maps = map_generator.generate_and_save_random_mapping(
        dictionary=handler.dictionary,
        max_items=random_max_items,
        random_paddings=random_paddings,
        seed=random_seed,
        filename=json_file,
        override=True,
    )
    # Maps must be of the same size
    _check_mappings_have_the_same_length(maps)
    maps.validate()

    # Set the new mapping and serialize it for later analysis
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()
    handler.set_maps(maps)
    handler.serialize_mapping_to_sci(
        esi_file=setup_specifier_with_esi.extra_data["esi_file"], sci_file=sci_file, override=False
    )

    try:
        mc.fsoe.configure_pdos(start_pdos=True)
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
        json_file.unlink()
        sci_file.unlink()
    except Exception as e:
        pytest.fail(f"Failed to reach data state random mapping: {e}")
    finally:
        mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe_phase2
@pytest.mark.xfail(reason="Maybe mapping with all safety functions is not valid", strict=True)
def test_map_all_safety_functions(
    mc_with_fsoe_with_sra: tuple[MotionController, "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    fsoe_maps_dir: Path,
    setup_specifier_with_esi: DriveHwConfigSpecifier,
) -> None:
    """Test that data state can be reached by mapping everything."""
    mc, handler = mc_with_fsoe_with_sra

    # Set the new mapping
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()
    for sf in SafetyFunction.for_handler(handler):
        if hasattr(sf, "command"):
            handler.maps.insert_in_best_position(sf.command)
        else:
            handler.maps.insert_in_best_position(sf.value)

    # Maps must be of the same size
    _check_mappings_have_the_same_length(handler.maps)

    # Check that the maps are valid
    handler.maps.validate()

    # Save the mappings
    sci_file = fsoe_maps_dir / "complete_mapping.sci"
    json_file = fsoe_maps_dir / "complete_mapping.json"
    handler.serialize_mapping_to_sci(
        esi_file=setup_specifier_with_esi.extra_data["esi_file"], sci_file=sci_file, override=True
    )
    FSoEDictionaryMapJSONSerializer.save_mapping_to_json(handler.maps, json_file, override=True)

    mc.fsoe.configure_pdos(start_pdos=True)
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    # Stay 3 seconds in Data state
    for i in range(3):
        time.sleep(1)
    mc.fsoe.stop_master(stop_pdos=True)

    sci_file.unlink()
    json_file.unlink()


@pytest.mark.fsoe_phase2
def test_fixed_mapping_combination(
    mc_with_fsoe_with_sra: tuple[MotionController, "FSoEMasterHandler"], timeout_for_data_sra: float
) -> None:
    mc, handler = mc_with_fsoe_with_sra
    # Get the safety functions instances
    sto = handler.get_function_instance(safety_functions.STOFunction)
    safe_inputs = handler.get_function_instance(safety_functions.SafeInputsFunction)
    ss1 = handler.get_function_instance(safety_functions.SS1Function)

    # The handler comes with a default mapping read from the drive.
    # Clear it to create a new one
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()

    # # Configure Outputs map
    handler.maps.outputs.add(sto.command)
    handler.maps.outputs.add_padding(1)
    handler.maps.outputs.add(ss1.command)
    handler.maps.outputs.add_padding(7)

    # Configure Inputs Map
    handler.maps.inputs.add(sto.command)
    handler.maps.inputs.add_padding(7)
    handler.maps.inputs.add(safe_inputs.value)
    handler.maps.inputs.add_padding(7)

    # Check that mappings have the same length
    _check_mappings_have_the_same_length(handler.maps)

    # Check that the maps are valid
    handler.maps.validate()

    mc.fsoe.configure_pdos(start_pdos=True)

    # Wait for the master to reach the Data state
    try:
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)

        for i in range(5):
            time.sleep(1)
            # During this time, commands can be changed
            sto.command.set(1)
            ss1.command.set(1)
            # And inputs can be read
            safe_inputs.value.get()
    except TimeoutError as e:
        pytest.fail(f"Failed to reach data state: {e}")
    finally:
        mc.fsoe.stop_master(stop_pdos=True)

import time
import warnings
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


def move_test_files(files: list[Path], fsoe_maps_dir: Path, success: bool) -> None:
    """Move test files to success or failure subdirectories.

    Args:
        files: List of file paths to move.
        fsoe_maps_dir: Base FSoE maps directory.
        success: True for successful tests (move to 'passed'), False for failed (move to 'failed').

    Raises:
        RuntimeError: If moving the files fails.
    """
    target_dir = fsoe_maps_dir / ("passed" if success else "failed")
    target_dir.mkdir(exist_ok=True)

    for file_path in files:
        if file_path.exists():
            try:
                target_file = target_dir / file_path.name
                file_path.rename(target_file)
            except Exception as e:
                raise RuntimeError(f"Failed to move {file_path} to {target_dir}: {e}")


def save_maps_text_representation(maps: "PDUMaps", output_file: Path) -> None:
    """Save the text representation of FSoE maps to a file.

    Args:
        maps: The PDUMaps object to save
        output_file: Path where to save the text file
    """
    try:
        with output_file.open("w", encoding="utf-8") as f:
            f.write("\n\nInputs\n-------\n")
            f.write(maps.inputs.get_text_representation())
            f.write("\n\n" + "=" * 85 + "\n" + "=" * 85 + "\n\n")
            f.write("Outputs\n-------\n")
            f.write(maps.outputs.get_text_representation())
    except Exception as e:
        warnings.warn(f"Failed to save maps text representation: {e}")


def _check_mappings_have_the_same_length(maps: "PDUMaps") -> None:
    if maps.inputs.safety_bits > maps.outputs.safety_bits:
        maps.outputs.add_padding(maps.inputs.safety_bits - maps.outputs.safety_bits)
    elif maps.outputs.safety_bits > maps.inputs.safety_bits:
        maps.inputs.add_padding(maps.outputs.safety_bits - maps.inputs.safety_bits)
    assert maps.inputs.safety_bits == maps.outputs.safety_bits


@pytest.mark.fsoe_phase2
@pytest.mark.skip("Maps not working")
@pytest.mark.parametrize("iteration", range(10))  # Run 10 times
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
    txt_file = fsoe_maps_dir / f"{mapping_name}.txt"

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
        esi_file=setup_specifier_with_esi.extra_data["esi_file"], sci_file=sci_file, override=True
    )
    save_maps_text_representation(handler.maps, txt_file)

    test_success = False
    try:
        mc.fsoe.configure_pdos(start_pdos=True)
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
        test_success = True
    except Exception as e:
        warnings.warn(f"Failed to reach data state with random mapping: {e}")
    finally:
        # Move files to appropriate directory based on test result
        move_test_files([json_file, sci_file, txt_file], fsoe_maps_dir, test_success)

        # If there has been a failure and it tries to remove the PDO maps, it may fail
        # if the servo is not in preop state
        try:
            # Stop the FSoE master handler
            if mc.capture.pdo.is_active:
                mc.fsoe.stop_master(stop_pdos=True)
        except Exception:
            pass


@pytest.mark.fsoe_phase2
@pytest.mark.skip("Maps not working")
def test_map_all_safety_functions(
    mc_with_fsoe_with_sra: tuple[MotionController, "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    fsoe_maps_dir: Path,
    setup_specifier_with_esi: DriveHwConfigSpecifier,
) -> None:
    """Test that data state can be reached by mapping everything."""
    mc, handler = mc_with_fsoe_with_sra

    handler.maps.inputs.clear()
    handler.maps.outputs.clear()

    # Set the new mapping
    # STO must be mapped in the first position
    sto = handler.get_function_instance(safety_functions.STOFunction)
    handler.maps.inputs.add(sto.command)
    handler.maps.outputs.add(sto.command)
    # Add the rest of the safety functions
    for sf in SafetyFunction.for_handler(handler):
        if isinstance(sf, safety_functions.STOFunction):
            continue  # STO is already added
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
    txt_file = fsoe_maps_dir / "complete_mapping.txt"
    handler.serialize_mapping_to_sci(
        esi_file=setup_specifier_with_esi.extra_data["esi_file"], sci_file=sci_file, override=True
    )
    save_maps_text_representation(handler.maps, txt_file)
    FSoEDictionaryMapJSONSerializer.save_mapping_to_json(handler.maps, json_file, override=True)

    test_success = False
    try:
        mc.fsoe.configure_pdos(start_pdos=True)
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
        # Stay 3 seconds in Data state
        for i in range(3):
            time.sleep(1)
        test_success = True
    except Exception as e:
        warnings.warn(f"Failed to reach data state with all safety functions: {e}")
    finally:
        # Move files to appropriate directory based on test result
        move_test_files([sci_file, json_file, txt_file], fsoe_maps_dir, test_success)

        # If there has been a failure and it tries to remove the PDO maps, it may fail
        # if the servo is not in preop state
        try:
            # Stop the FSoE master handler
            if mc.capture.pdo.is_active:
                mc.fsoe.stop_master(stop_pdos=True)
        except Exception:
            pass


# This test will be used for debugging, will be removed after https://novantamotion.atlassian.net/browse/INGM-689
@pytest.mark.fsoe_phase2
@pytest.mark.skip("https://novantamotion.atlassian.net/browse/INGM-689")
def test_fixed_mapping_combination(
    mc_with_fsoe_with_sra: tuple[MotionController, "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    fsoe_maps_dir: Path,
    setup_specifier_with_esi: DriveHwConfigSpecifier,
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    sci_file = fsoe_maps_dir / "test_map.sci"

    # Suspicious maps
    # "mapping_6_False_587.json"
    # "mapping_7_True_186.json"

    mapping = FSoEDictionaryMapJSONSerializer.load_mapping_from_json(
        handler.dictionary, fsoe_maps_dir / "failed/mapping_6_False_587.json"
    )
    handler.set_maps(mapping)

    # Check that mappings have the same length
    _check_mappings_have_the_same_length(handler.maps)

    # Check that the maps are valid
    handler.maps.validate()
    handler.serialize_mapping_to_sci(
        esi_file=setup_specifier_with_esi.extra_data["esi_file"], sci_file=sci_file, override=True
    )
    save_maps_text_representation(handler.maps, fsoe_maps_dir / "mapping_7_True_186.txt")

    mc.fsoe.configure_pdos(start_pdos=True)

    # Wait for the master to reach the Data state
    try:
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)

        for i in range(5):
            time.sleep(1)
    except TimeoutError as e:
        pytest.fail(f"Failed to reach data state: {e}")
    finally:
        # If there has been a failure and it tries to remove the PDO maps, it may fail
        # if the servo is not in preop state
        try:
            # Stop the FSoE master handler
            if mc.capture.pdo.is_active:
                mc.fsoe.stop_master(stop_pdos=True)
        except Exception:
            pass

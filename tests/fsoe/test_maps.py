import time
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController

try:
    import pysoem
except ImportError:
    pysoem = None


if FSOE_MASTER_INSTALLED:
    import ingeniamotion.fsoe_master.safety_functions as safety_functions
    from ingeniamotion.fsoe_master.safety_functions import SafetyFunction
    from tests.fsoe.map_json_serializer import FSoEDictionaryMapJSONSerializer

if TYPE_CHECKING:
    from ingenialink.ethercat.servo import EthercatServo

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.errors import (
            ServoErrorQueue,
        )
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
        from ingeniamotion.fsoe_master.maps import PDUMaps
        from tests.fsoe.conftest import FSoERandomMappingGenerator


def __move_test_files(files: list[Path], fsoe_maps_dir: Path, success: bool) -> None:
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
                if target_file.exists():
                    target_file.unlink()
                file_path.rename(target_file)
            except Exception as e:
                raise RuntimeError(f"Failed to move {file_path} to {target_dir}: {e}")


def __save_maps_text_representation(maps: "PDUMaps", output_file: Path) -> None:
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


@pytest.fixture
def no_error_tracker(
    mcu_error_queue_a: "ServoErrorQueue", mcu_error_queue_b: "ServoErrorQueue"
) -> Iterator[None]:
    """Fixture to ensure no new errors are added to the error queues during a test."""
    previous_mcu_a_errors = mcu_error_queue_a.get_number_total_errors()
    previous_mcu_b_errors = mcu_error_queue_b.get_number_total_errors()
    yield
    assert mcu_error_queue_a.get_number_total_errors() == previous_mcu_a_errors
    assert mcu_error_queue_b.get_number_total_errors() == previous_mcu_b_errors


@pytest.mark.fsoe_phase2
@pytest.mark.parametrize("iteration", range(25))  # Run 25 times
def test_map_safety_input_output_random(
    mc_with_fsoe_with_sra_and_feedback_scenario: tuple[MotionController, "FSoEMasterHandler"],
    map_generator: "FSoERandomMappingGenerator",
    fsoe_maps_dir: Path,
    timeout_for_data_sra: float,
    random_seed: int,
    random_max_items: int,
    random_paddings: bool,
    fsoe_states: list[FSoEState],
    servo: "EthercatServo",
    no_error_tracker: None,  # noqa: ARG001
    iteration: int,  # noqa: ARG001
) -> None:
    """Tests that random combinations of inputs and outputs are valid."""
    mc, handler = mc_with_fsoe_with_sra_and_feedback_scenario

    mapping_name = f"mapping_{random_max_items}_{random_paddings}_{random_seed}"
    json_file = fsoe_maps_dir / f"{mapping_name}.json"
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
    maps.validate()

    # Set the new mapping and serialize it for later analysis
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()
    handler.set_maps(maps)
    __save_maps_text_representation(handler.maps, txt_file)

    test_success = False
    try:
        mc.fsoe.configure_pdos(start_pdos=True)
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
        test_success = fsoe_states[-1] is FSoEState.DATA and (servo.slave.state is pysoem.OP_STATE)
        if not test_success:
            pytest.fail(
                f"Unexpected FSoE state {fsoe_states[-1]} or servo state {servo.slave.state}"
            )
    except Exception as e:
        pytest.fail(
            f"Failed to reach data state with random mapping: {e}, servo state: {servo.slave.state}"
        )
    finally:
        # Move files to appropriate directory based on test result
        __move_test_files([json_file, txt_file], fsoe_maps_dir, test_success)

        # If there has been a failure and it tries to remove the PDO maps, it may fail
        # if the servo is not in preop state
        try:
            # Stop the FSoE master handler
            if mc.capture.pdo.is_active:
                mc.fsoe.stop_master(stop_pdos=True)
        except Exception:
            pass


@pytest.mark.fsoe_phase2
def test_map_all_safety_functions(
    mc_with_fsoe_with_sra_and_feedback_scenario: tuple[MotionController, "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    fsoe_maps_dir: Path,
    fsoe_states: list[FSoEState],
    alias: str,
    no_error_tracker: None,  # noqa: ARG001
) -> None:
    """Test that data state can be reached by mapping everything."""
    mc, handler = mc_with_fsoe_with_sra_and_feedback_scenario

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
            # SOUT command is not allowed if SOUT disable is set to 1
            if sf.command.name == "FSOE_SOUT":
                continue
            handler.maps.insert_in_best_position(sf.command)
        else:
            handler.maps.insert_in_best_position(sf.value)

    # Check that the maps are valid
    handler.maps.validate()

    # Save the mappings
    json_file = fsoe_maps_dir / "complete_mapping.json"
    txt_file = fsoe_maps_dir / "complete_mapping.txt"
    __save_maps_text_representation(handler.maps, txt_file)
    FSoEDictionaryMapJSONSerializer.save_mapping_to_json(handler.maps, json_file, override=True)

    test_success = False
    try:
        handler.maps.validate()
        mc.fsoe.configure_pdos(start_pdos=False)
        mc.capture.pdo.start_pdos(servo=alias)
        time.sleep(0.05)

        # Wait for the master to reach the Data state
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)

        for i in range(5):
            time.sleep(1)
        assert fsoe_states[-1] == FSoEState.DATA

        test_success = True
    except Exception as e:
        pytest.fail(f"Failed to reach data state with all safety functions: {e}")
    finally:
        # Move files to appropriate directory based on test result
        __move_test_files([json_file, txt_file], fsoe_maps_dir, test_success)

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
# @pytest.mark.skip("https://novantamotion.atlassian.net/browse/INGM-689")
@pytest.mark.parametrize(
    "check_map",
    [
        # "mapping_6_False_680.json",
        "mapping_6_False_587.json",
        "mapping_7_True_186.json",
        "mapping_6_False_861.json",
        "mapping_6_True_419.json",
        "mapping_7_False_774.json",
        "mapping_7_True_984.json",
        "mapping_8_False_247.json",
        "mapping_8_False_847.json",
        "mapping_8_True_349.json",
        "mapping_8_True_843.json",
        "mapping_8_True_924.json",
        "mapping_9_True_403.json",
        "mapping_10_False_3.json",
        "mapping_10_True_236.json",
        "mapping_10_True_659.json",
        "mapping_10_True_933.json",
    ],
)
def test_fixed_mapping_combination(
    mc_with_fsoe_with_sra_and_feedback_scenario: tuple[MotionController, "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    fsoe_maps_dir: Path,
    alias: str,
    fsoe_states: list[FSoEState],
    check_map: str,
    servo: "EthercatServo",
) -> None:
    mc, handler = mc_with_fsoe_with_sra_and_feedback_scenario

    test_map = f"old/failed/{check_map}"

    mapping = FSoEDictionaryMapJSONSerializer.load_mapping_from_json(
        handler.dictionary, fsoe_maps_dir / f"{test_map}"
    )
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()
    handler.set_maps(mapping)

    # Check that the maps are valid
    try:
        handler.maps.validate()
        mc.fsoe.configure_pdos(start_pdos=False)
        mc.capture.pdo.start_pdos(servo=alias)
        time.sleep(0.05)

        # Wait for the master to reach the Data state
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)

        for i in range(5):
            time.sleep(1)
        assert fsoe_states[-1] == FSoEState.DATA
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

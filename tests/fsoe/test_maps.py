import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController
from tests.dictionaries import SAMPLE_SAFE_PH2_XDFV3_DICTIONARY

try:
    import pysoem
except ImportError:
    pysoem = None


if FSOE_MASTER_INSTALLED:
    import ingeniamotion.fsoe_master.safety_functions as safety_functions
    from ingeniamotion.fsoe_master import PDUMaps
    from ingeniamotion.fsoe_master.safety_functions import (
        SafeInputsFunction,
        SafetyFunction,
        SS1Function,
        SSRFunction,
        STOFunction,
    )
    from tests.fsoe.map_json_serializer import FSoEDictionaryMapJSONSerializer
    from tests.test_fsoe_master import MockHandler

if TYPE_CHECKING:
    from ingenialink.ethercat.servo import EthercatServo

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.errors import (
            ServoErrorQueue,
        )
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
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
    assert mcu_error_queue_a.get_number_total_errors() == previous_mcu_a_errors, (
        f"MCUA error queue changed: {previous_mcu_a_errors} -> "
        f"{mcu_error_queue_a.get_number_total_errors()}. "
        f"\nLast error: {mcu_error_queue_a.get_last_error()}"
    )
    assert mcu_error_queue_b.get_number_total_errors() == previous_mcu_b_errors, (
        f"MCUB error queue changed: {previous_mcu_b_errors} -> "
        f"{mcu_error_queue_b.get_number_total_errors()}. "
        f"\nLast error: {mcu_error_queue_b.get_last_error()}"
    )


@pytest.mark.fsoe_phase2
@pytest.mark.parametrize("iteration", range(25))  # Run 25 times
@pytest.mark.skip("https://novantamotion.atlassian.net/browse/INGM-710")
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
    mcu_error_queue_a: "ServoErrorQueue",
    mcu_error_queue_b: "ServoErrorQueue",
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
                f"\nMCUA last error: {mcu_error_queue_a.get_last_error()}"
                f"\nMCUB last error: {mcu_error_queue_b.get_last_error()}"
            )
    except Exception as e:
        pytest.fail(
            f"Failed to reach data state with random mapping: {e}, servo state: {servo.slave.state}"
            f"\nMCUA last error: {mcu_error_queue_a.get_last_error()}"
            f"\nMCUB last error: {mcu_error_queue_b.get_last_error()}"
        )
    finally:
        __move_test_files([json_file, txt_file], fsoe_maps_dir, test_success)


@pytest.mark.fsoe_phase2
@pytest.mark.skip("https://novantamotion.atlassian.net/browse/INGM-710")
def test_map_all_safety_functions(
    mc_with_fsoe_with_sra_and_feedback_scenario: tuple[MotionController, "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    fsoe_maps_dir: Path,
    fsoe_states: list[FSoEState],
    alias: str,
    servo: "EthercatServo",
    no_error_tracker: None,  # noqa: ARG001
    mcu_error_queue_a: "ServoErrorQueue",
    mcu_error_queue_b: "ServoErrorQueue",
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
        elif hasattr(sf, "command_positive"):
            handler.maps.insert_in_best_position(sf.command_positive)
        elif hasattr(sf, "command_negative"):
            handler.maps.insert_in_best_position(sf.command_negative)
        else:
            handler.maps.insert_in_best_position(sf.value)

    # Check that the maps are valid
    handler.maps.validate()
    json_file = fsoe_maps_dir / "complete_mapping.json"
    txt_file = fsoe_maps_dir / "complete_mapping.txt"
    __save_maps_text_representation(handler.maps, txt_file)
    FSoEDictionaryMapJSONSerializer.save_mapping_to_json(handler.maps, json_file, override=True)

    test_success = False
    try:
        mc.fsoe.configure_pdos(start_pdos=False)
        mc.capture.pdo.start_pdos(servo=alias)
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
        test_success = fsoe_states[-1] is FSoEState.DATA and (servo.slave.state is pysoem.OP_STATE)
        if not test_success:
            pytest.fail(
                f"Unexpected FSoE state {fsoe_states[-1]} or servo state {servo.slave.state}"
                f"\nMCUA last error: {mcu_error_queue_a.get_last_error()}"
                f"\nMCUB last error: {mcu_error_queue_b.get_last_error()}"
            )
    except Exception as e:
        pytest.fail(
            f"Failed to reach data state with all safety functions: {e}"
            f"\nMCUA last error: {mcu_error_queue_a.get_last_error()}"
            f"\nMCUB last error: {mcu_error_queue_b.get_last_error()}"
        )
    finally:
        __move_test_files([json_file, txt_file], fsoe_maps_dir, test_success)


@pytest.mark.fsoe_phase2
def test_is_safety_function_mapped():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sfs = handler.safety_functions_by_type()
    maps = PDUMaps.empty(handler.dictionary)
    sto_func = sfs[STOFunction][0]
    sto_ios = list(sto_func.ios.values())
    assert maps.is_safety_function_mapped(sto_func) is False
    assert maps.is_safety_function_mapped(sto_func, strict=False) is False
    maps.inputs.add(sto_ios[0])
    assert maps.is_safety_function_mapped(sto_func) is False
    assert maps.is_safety_function_mapped(sto_func, strict=False) is True
    maps.outputs.add(sto_ios[0])
    assert maps.is_safety_function_mapped(sto_func) is True
    assert maps.is_safety_function_mapped(sto_func, strict=False) is True

    si_func = sfs[SafeInputsFunction][0]
    si_ios = list(si_func.ios.values())
    assert maps.is_safety_function_mapped(si_func) is False
    assert maps.is_safety_function_mapped(si_func, strict=False) is False
    maps.inputs.add(si_ios[0])
    assert maps.is_safety_function_mapped(si_func) is True
    assert maps.is_safety_function_mapped(si_func, strict=False) is True

    ss1_func = sfs[SS1Function][0]
    ss1_ios = list(ss1_func.ios.values())
    assert maps.is_safety_function_mapped(ss1_func) is False
    assert maps.is_safety_function_mapped(ss1_func, strict=False) is False
    maps.outputs.add(ss1_ios[0])
    assert maps.is_safety_function_mapped(ss1_func) is True
    assert maps.is_safety_function_mapped(ss1_func, strict=False) is True
    maps.inputs.add(ss1_ios[0])
    assert maps.is_safety_function_mapped(ss1_func) is True
    assert maps.is_safety_function_mapped(ss1_func, strict=False) is True


@pytest.mark.fsoe_phase2
def test_insert_safety_function():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sto_func = handler.safety_functions_by_type()[STOFunction][0]

    maps = PDUMaps.empty(handler.dictionary)
    maps.insert_safety_function(sto_func)
    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                "
    )


@pytest.mark.fsoe_phase2
def test_insert_safety_functions_by_type():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sfs = handler.safety_functions_by_type()
    maps = PDUMaps.empty(handler.dictionary)
    sto_func = sfs[STOFunction][0]
    sto_ios = list(sto_func.ios.values())
    maps.inputs.add(sto_ios[0])
    maps.insert_safety_functions_by_type(handler, STOFunction)
    maps.insert_safety_functions_by_type(handler, SSRFunction)
    maps.insert_safety_functions_by_type(handler, SSRFunction)
    maps.insert_safety_functions_by_type(handler, SSRFunction)
    maps.insert_safety_functions_by_type(handler, SSRFunction)
    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "FSOE_SSR_COMMAND_1             | 0..1                 | 0..1                \n"
        "FSOE_SSR_COMMAND_2             | 0..2                 | 0..1                \n"
        "FSOE_SSR_COMMAND_3             | 0..3                 | 0..1                \n"
        "FSOE_SSR_COMMAND_4             | 0..4                 | 0..1                "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "FSOE_SSR_COMMAND_1             | 0..1                 | 0..1                \n"
        "FSOE_SSR_COMMAND_2             | 0..2                 | 0..1                \n"
        "FSOE_SSR_COMMAND_3             | 0..3                 | 0..1                \n"
        "FSOE_SSR_COMMAND_4             | 0..4                 | 0..1                "
    )


@pytest.mark.fsoe_phase2
def test_remove_safety_functions_by_type_1():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)

    maps = PDUMaps.empty(handler.dictionary)
    maps.insert_safety_functions_by_type(handler, STOFunction)
    maps.insert_safety_functions_by_type(handler, SSRFunction)
    maps.remove_safety_functions_by_type(handler, SSRFunction)
    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "Padding                        | 0..1                 | 0..1                "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "Padding                        | 0..1                 | 0..1                "
    )


@pytest.mark.fsoe_phase2
def test_remove_safety_functions_by_type_2():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    ssr_funcs = handler.safety_functions_by_type()[SSRFunction]
    maps = PDUMaps.empty(handler.dictionary)
    maps.insert_safety_functions_by_type(handler, STOFunction)
    maps.insert_safety_function(ssr_funcs[5])
    maps.insert_safety_function(ssr_funcs[3])
    maps.remove_safety_functions_by_type(handler, SSRFunction)
    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "Padding                        | 0..1                 | 0..1                \n"
        "FSOE_SSR_COMMAND_4             | 0..2                 | 0..1                "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "Padding                        | 0..1                 | 0..1                \n"
        "FSOE_SSR_COMMAND_4             | 0..2                 | 0..1                "
    )


@pytest.mark.fsoe_phase2
def test_unmap_safety_function():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sfs = handler.safety_functions_by_type()
    maps = PDUMaps.empty(handler.dictionary)
    maps.insert_safety_function(sfs[STOFunction][0])
    maps.insert_safety_function(sfs[SSRFunction][0])
    maps.insert_safety_function(sfs[SafeInputsFunction][0])
    maps.unmap_safety_function(sfs[STOFunction][0])
    maps.unmap_safety_function(sfs[SafeInputsFunction][0])
    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "Padding                        | 0..0                 | 0..1                \n"
        "FSOE_SSR_COMMAND_1             | 0..1                 | 0..1                \n"
        "Padding                        | 0..2                 | 0..1                "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "Padding                        | 0..0                 | 0..1                \n"
        "FSOE_SSR_COMMAND_1             | 0..1                 | 0..1                "
    )


@pytest.mark.fsoe_phase2
def test_unmap_safety_function_warring(caplog):
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sfs = handler.safety_functions_by_type()
    maps = PDUMaps.empty(handler.dictionary)
    si_func = sfs[SafeInputsFunction][0]
    with caplog.at_level("WARNING"):
        maps.unmap_safety_function(si_func)
    assert any("The safety function is not mapped" in record.message for record in caplog.records)


@pytest.mark.fsoe_phase2
def test_unmap_safety_function_partial():
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sfs = handler.safety_functions_by_type()
    maps = PDUMaps.empty(handler.dictionary)

    sto_func = sfs[STOFunction][0]
    sto_ios = list(sto_func.ios.values())
    maps.outputs.add(sto_ios[0])
    maps.unmap_safety_function(sto_func)

    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "Padding                        | 0..0                 | 0..1                "
    )

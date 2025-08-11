import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
    from tests.fsoe.map_generator import FSoERandomMappingGenerator
    from tests.fsoe.map_json_serializer import FSoEDictionaryMapJSONSerializer


@pytest.fixture
def temp_mapping_files_dir() -> Generator[Path, None, None]:
    """Creates an empty mapping files directory.

    Yields:
        mapping files directory path.
    """
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    if temp_dir.exists() and temp_dir.is_dir():
        shutil.rmtree(temp_dir.as_posix())


@pytest.mark.fsoe_phase2
def test_save_load_random_mapping(
    mc_with_fsoe_with_sra: tuple[MotionController, FSoEMasterHandler],
    map_generator: FSoERandomMappingGenerator,
    temp_mapping_files_dir: Path,
) -> None:
    _, handler = mc_with_fsoe_with_sra
    mapping_file = temp_mapping_files_dir / "test_mapping.json"

    # Generate a random mapping to save it
    original_mapping = map_generator.generate_and_save_random_mapping(
        dictionary=handler.dictionary,
        max_items=5,
        random_paddings=True,
        filename=mapping_file,
        seed=42,
    )
    original_json = FSoEDictionaryMapJSONSerializer.serialize_mapping_to_dict(original_mapping)
    assert mapping_file.exists()

    # Check that there is something in the mapping
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()
    handler.set_maps(original_mapping)
    n_original_inputs = len(handler.maps.inputs._items)
    n_original_outputs = len(handler.maps.outputs._items)
    assert n_original_inputs > 0
    assert n_original_outputs > 0

    # Clear the current mapping and load the mapping from JSON
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()
    assert len(handler.maps.inputs._items) == 0
    assert len(handler.maps.outputs._items) == 0
    new_mapping = FSoEDictionaryMapJSONSerializer.load_mapping_from_json(
        handler.dictionary, mapping_file
    )
    handler.set_maps(new_mapping)
    assert len(handler.maps.inputs._items) == n_original_inputs
    assert len(handler.maps.outputs._items) == n_original_outputs
    new_json = FSoEDictionaryMapJSONSerializer.serialize_mapping_to_dict(new_mapping)

    # Verify the loaded mapping matches the original
    assert new_json == original_json

from pathlib import Path

import pytest

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
    from ingeniamotion.fsoe_master.maps_validator import (
        FSoEFrameConstructionError,
    )
    from tests.fsoe.map_generator import FSoERandomMappingGenerator


@pytest.mark.fsoe_phase2
@pytest.mark.parametrize("iteration", range(100))  # Run 30 times
def test_random_map_validation(
    mc_with_fsoe_with_sra: tuple[MotionController, FSoEMasterHandler],
    map_generator: FSoERandomMappingGenerator,
    fsoe_maps_dir: Path,
    random_seed: int,
    random_max_items: int,
    random_paddings: bool,
    iteration: int,  # noqa: ARG001
) -> None:
    _, handler = mc_with_fsoe_with_sra

    mapping_file = (
        fsoe_maps_dir / f"mapping_{random_max_items}_{random_paddings}_{random_seed}.json"
    )

    maps = map_generator.generate_and_save_random_mapping(
        dictionary=handler.dictionary,
        max_items=random_max_items,
        random_paddings=random_paddings,
        seed=random_seed,
        filename=mapping_file,
        override=False,
    )
    assert mapping_file.exists()

    try:
        maps.validate()
        mapping_file.unlink()
        assert not mapping_file.exists()
    except FSoEFrameConstructionError as e:
        pytest.fail(f"Map validation failed with error: {e}. ")

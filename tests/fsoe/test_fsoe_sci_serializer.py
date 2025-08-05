import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from summit_testing_framework.setups.specifiers import DriveHwConfigSpecifier

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
    from ingeniamotion.fsoe_master.sci_serializer import FSoEDictionaryMapSciSerializer


@pytest.fixture(scope="module")
def temp_sci_files_dir() -> Generator[Path, None, None]:
    """Creates an empty mapping files directory.

    Yields:
        mapping files directory path.
    """
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    if temp_dir.exists() and temp_dir.is_dir():
        shutil.rmtree(temp_dir.as_posix())


@pytest.mark.fsoe_phaseII
def test_save_sci_mapping(
    temp_sci_files_dir: Path,
    mc_with_fsoe_with_sra: tuple[MotionController, FSoEMasterHandler],
    setup_specifier: DriveHwConfigSpecifier,
) -> None:
    """Test saving the FSoE mapping to a .sci file."""
    _, handler = mc_with_fsoe_with_sra
    serializer = FSoEDictionaryMapSciSerializer(esi_file=setup_specifier.extra_data["esi_file"])
    sci_file = Path("C:\\git_repo\\ingeniamotion\\sci_files") / "test_mapping.sci"
    serializer.save_mapping_to_sci(
        handler=handler,
        filename=sci_file,
        override=True,
    )
    assert sci_file.exists()

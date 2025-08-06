import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path
from xml.etree import ElementTree

import pytest
from ingenialink.dictionary import XMLBase
from summit_testing_framework.setups.specifiers import DriveHwConfigSpecifier

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.sci_serializer import (
        FSoEDictionaryMapSciSerializer,
        read_xml_file,
    )


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


@pytest.mark.fsoe
def test_sci_serializes_single_safety_module(setup_specifier: DriveHwConfigSpecifier) -> None:
    """Test that the SCI serializer serializes only the safety module being used.

    ESI files can contain multiple safety modules, but the SCI file should only
    contain the one that is actually being used by the FSoE master handler.
    """

    def __find_safety_modules(root: ElementTree.Element) -> list[ElementTree.Element]:
        description_element = XMLBase._find_and_check(
            root,
            FSoEDictionaryMapSciSerializer._FSoEDictionaryMapSciSerializer__DESCRIPTIONS_ELEMENT,
        )
        modules_element = XMLBase._find_and_check(
            description_element,
            FSoEDictionaryMapSciSerializer._FSoEDictionaryMapSciSerializer__MODULES_ELEMENT,
        )
        return XMLBase._findall_and_check(
            modules_element,
            FSoEDictionaryMapSciSerializer._FSoEDictionaryMapSciSerializer__MODULE_ELEMENT,
        )

    handler = None  # TODO: use handler from fixture
    # module_ident_used = int(handler.__get_configured_module_ident_1())
    module_ident_used = int("0x3b00002", 16)

    serializer: FSoEDictionaryMapSciSerializer = FSoEDictionaryMapSciSerializer(
        esi_file=setup_specifier.extra_data["esi_file"]
    )
    esi_root: ElementTree.Element = read_xml_file(setup_specifier.extra_data["esi_file"])
    sci_root: ElementTree.Element = serializer.serialize_mapping_to_sci(handler=handler).getroot()

    esi_safety_modules = __find_safety_modules(esi_root)
    sci_safety_modules = __find_safety_modules(sci_root)

    # All safety modules are present in the ESI file (same than dictionary)
    assert len(esi_safety_modules) > 1
    # TODO: with servo connection check that the number of safety modules in ESI are the same than in dictionary

    # Only the safety module being used is present in the SCI file
    assert len(sci_safety_modules) == 1
    assert serializer._get_module_ident_from_module(sci_safety_modules[0]) == module_ident_used


@pytest.mark.fsoe
def test_save_sci_mapping(
    temp_sci_files_dir: Path,
    # mc_with_fsoe_with_sra: tuple[MotionController, FSoEMasterHandler],
    setup_specifier: DriveHwConfigSpecifier,
) -> None:
    """Test saving the FSoE mapping to a .sci file."""
    # _, handler = mc_with_fsoe_with_sra
    serializer = FSoEDictionaryMapSciSerializer(esi_file=setup_specifier.extra_data["esi_file"])
    sci_file = Path("C:\\git_repo\\ingeniamotion\\sci_files") / "test_mapping.sci"
    serializer.save_mapping_to_sci(
        handler=None,
        filename=sci_file,
        override=True,
    )
    assert sci_file.exists()

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree

import pytest
from ingenialink.dictionary import XMLBase
from summit_testing_framework.setups.specifiers import DriveHwConfigSpecifier

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController

if TYPE_CHECKING:
    from ingenialink.ethercat.servo import EthercatServo

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.handler import FSoEMasterHandler

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import (
        SafeInputsFunction,
        SS1Function,
        STOFunction,
    )
    from ingeniamotion.fsoe_master.sci_serializer import (
        SCISerializer,
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
def test_sci_serializes_single_safety_module(
    setup_specifier_with_esi: DriveHwConfigSpecifier,
    mc_with_fsoe_with_sra: tuple[MotionController, "FSoEMasterHandler"],
    servo: "EthercatServo",
) -> None:
    """Test that the SCI serializer serializes only the safety module being used.

    ESI files can contain multiple safety modules, but the SCI file should only
    contain the one that is actually being used by the FSoE master handler.
    """

    def __find_safety_modules(root: ElementTree.Element) -> list[ElementTree.Element]:
        description_element = XMLBase._find_and_check(
            root,
            SCISerializer._SCISerializer__DESCRIPTIONS_ELEMENT,
        )
        modules_element = XMLBase._find_and_check(
            description_element,
            SCISerializer._SCISerializer__MODULES_ELEMENT,
        )
        return XMLBase._findall_and_check(
            modules_element,
            SCISerializer._SCISerializer__MODULE_ELEMENT,
        )

    _, handler = mc_with_fsoe_with_sra
    module_ident_used = int(handler._FSoEMasterHandler__get_configured_module_ident_1())

    sci_serializer: SCISerializer = SCISerializer()
    esi_root: ElementTree.Element = read_xml_file(setup_specifier_with_esi.extra_data["esi_file"])
    sci_root: ElementTree.Element = sci_serializer.serialize_mapping_to_sci(
        esi_file=setup_specifier_with_esi.extra_data["esi_file"],
        rpdo=handler._FSoEMasterHandler__safety_master_pdu,
        tpdo=handler._FSoEMasterHandler__safety_slave_pdu,
        assigned_rpdos=[
            servo.dictionary.get_register(uid).idx for uid in servo.ETG_COMMS_RPDO_MAP1_TOTAL
        ],
        assigned_tpdos=[
            servo.dictionary.get_register(uid).idx for uid in servo.ETG_COMMS_TPDO_MAP1_TOTAL
        ],
        module_ident=module_ident_used,
    ).getroot()

    esi_safety_modules = __find_safety_modules(esi_root)
    sci_safety_modules = __find_safety_modules(sci_root)

    # All safety modules are present in the ESI file (same than dictionary)
    assert len(esi_safety_modules) > 1
    assert len(esi_safety_modules) == len(
        handler._FSoEMasterHandler__servo.dictionary.safety_modules
    )

    # Only the safety module being used is present in the SCI file
    assert len(sci_safety_modules) == 1
    assert sci_serializer._get_module_ident_from_module(sci_safety_modules[0]) == module_ident_used


@pytest.mark.fsoe
def test_sci_serializes_assigned_pdos(
    setup_specifier_with_esi: DriveHwConfigSpecifier,
    mc_with_fsoe_with_sra: tuple[MotionController, "FSoEMasterHandler"],
    servo: "EthercatServo",
) -> None:
    """Test that the SCI serializer serializes only the assigned RPDOs and TPDOs.

    ESI files can contain multiple rxpdo/txpdo, but the SCI file should only
    contain the one that is actually mapped.
    """

    def __find_pdos(root: ElementTree.Element, pdo_type: str) -> list[ElementTree.Element]:
        description_element = XMLBase._find_and_check(
            root,
            SCISerializer._SCISerializer__DESCRIPTIONS_ELEMENT,
        )
        devices_element = XMLBase._find_and_check(
            description_element,
            SCISerializer._SCISerializer__DEVICES_ELEMENT,
        )
        device_element = XMLBase._find_and_check(
            devices_element, SCISerializer._SCISerializer__DEVICE_ELEMENT
        )
        if pdo_type == "rxpdo":
            return XMLBase._findall_and_check(
                device_element, SCISerializer._SCISerializer__RXPDO_ELEMENT
            )
        elif pdo_type == "txpdo":
            return XMLBase._findall_and_check(
                device_element, SCISerializer._SCISerializer__TXPDO_ELEMENT
            )
        raise ValueError(f"Unknown PDO type: {pdo_type}")

    _, handler = mc_with_fsoe_with_sra
    module_ident_used = int(handler._FSoEMasterHandler__get_configured_module_ident_1())

    sci_serializer: SCISerializer = SCISerializer()
    esi_root: ElementTree.Element = read_xml_file(setup_specifier_with_esi.extra_data["esi_file"])
    sci_root: ElementTree.Element = sci_serializer.serialize_mapping_to_sci(
        esi_file=setup_specifier_with_esi.extra_data["esi_file"],
        rpdo=handler._FSoEMasterHandler__safety_master_pdu,
        tpdo=handler._FSoEMasterHandler__safety_slave_pdu,
        assigned_rpdos=[
            servo.dictionary.get_register(uid).idx for uid in servo.ETG_COMMS_RPDO_MAP1_TOTAL
        ],
        assigned_tpdos=[
            servo.dictionary.get_register(uid).idx for uid in servo.ETG_COMMS_TPDO_MAP1_TOTAL
        ],
        module_ident=module_ident_used,
    ).getroot()

    for pdo_type in ["rxpdo", "txpdo"]:
        esi_pdos = __find_pdos(esi_root, pdo_type)
        sci_pdos = __find_pdos(sci_root, pdo_type)
        # All pdos are present in the ESI file
        assert len(esi_pdos) > 1
        # Only the assigned PDO is present in the SCI file
        assert len(sci_pdos) == 1


@pytest.mark.fsoe_phase2
def test_save_sci_mapping(
    temp_sci_files_dir: Path,
    mc_with_fsoe_with_sra: tuple[MotionController, "FSoEMasterHandler"],
    setup_specifier_with_esi: DriveHwConfigSpecifier,
) -> None:
    """Test saving the FSoE mapping to a .sci file."""
    _, handler = mc_with_fsoe_with_sra

    sto = handler.get_function_instance(STOFunction)
    safe_inputs = handler.get_function_instance(SafeInputsFunction)
    ss1 = handler.get_function_instance(SS1Function)

    handler.maps.inputs.clear()
    handler.maps.inputs.add(sto.command)
    handler.maps.inputs.add_padding(7)
    handler.maps.inputs.add(safe_inputs.value)
    handler.maps.inputs.add_padding(7)

    handler.maps.outputs.clear()
    handler.maps.outputs.add(sto.command)
    handler.maps.outputs.add_padding(1)
    handler.maps.outputs.add(ss1.command)
    handler.maps.outputs.add_padding(7)

    handler.maps.validate()
    handler.configure_pdo_maps()

    sci_file = temp_sci_files_dir / "test_mapping.sci"
    handler.serialize_mapping_to_sci(
        esi_file=setup_specifier_with_esi.extra_data["esi_file"], sci_file=sci_file
    )
    assert sci_file.exists()

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

from ingenialink.dictionary import Interface, XMLBase
from ingenialink.pdo import RPDOMap, TPDOMap
from ingenialink.servo import DictionaryFactory
from ingenialink.utils._utils import convert_dtype_to_bytes

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from tests.dictionaries import SAMPLE_SAFE_PH2_XDFV3_DICTIONARY

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import (
        FSoEMasterHandler,
        PDUMaps,
        SS1Function,
        SS2Function,
        STOFunction,
    )
    from ingeniamotion.fsoe_master.frame import MASTER_FRAME_ELEMENTS, SLAVE_FRAME_ELEMENTS
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
    from ingeniamotion.fsoe_master.maps import PDUMaps


class EsiFileParseError(Exception):
    """ESI file parse error."""


def read_xml_file(file_path: Path) -> ElementTree.Element:
    """Read the content of an XML file.

    Args:
        file_path: Path to the XML file.

    Returns:
        The root element of the parsed XML tree.

    Raises:
        EsiFileParseError: If the XML file does not exist.
    """
    try:
        with open(file_path, encoding="utf-8") as xml_file:
            tree = ElementTree.parse(xml_file)
    except FileNotFoundError as e:
        raise EsiFileParseError(f"There is not any XML file in the path: {file_path}") from e
    return tree.getroot()


@dataclass(frozen=True)
class MappedPDO(XMLBase):
    """Data class to represent a mapped PDO."""

    complete_access: Optional[str]
    transition: str
    index: str
    subindex: str
    data: str
    data_adapt_automatically: Optional[str]

    ELEMENT: str = "InitCmd"
    __COMPLETE_ACCESS_ATTR: str = "CompleteAccess"
    __TRANSITION_ELEMENT: str = "Transition"
    __INDEX_ELEMENT: str = "Index"
    __SUB_INDEX_ELEMENT: str = "SubIndex"
    __DATA_ELEMENT: str = "Data"
    __DATA_ADAPT_AUTOMATICALLY_ATTR: str = "AdaptAutomatically"

    def serialize(self) -> ElementTree.Element:
        """Serialize the MappedPDO instance to an XML element.

        Returns:
            XML element representing the MappedPDO instance.
        """
        root = ElementTree.Element(self.ELEMENT)
        if self.complete_access is not None:
            root.set(self.__COMPLETE_ACCESS_ATTR, self.complete_access)
        transition_element = ElementTree.SubElement(root, self.__TRANSITION_ELEMENT)
        transition_element.text = self.transition
        index_element = ElementTree.SubElement(root, self.__INDEX_ELEMENT)
        index_element.text = self.index
        subindex_element = ElementTree.SubElement(root, self.__SUB_INDEX_ELEMENT)
        subindex_element.text = self.subindex
        data_element = ElementTree.SubElement(root, self.__DATA_ELEMENT)
        data_element.text = self.data
        if self.data_adapt_automatically is not None:
            data_element.set(self.__DATA_ADAPT_AUTOMATICALLY_ATTR, self.data_adapt_automatically)
        return root


class SCISerializer(XMLBase):
    """Class to handle serialization and deserialization of FSoE dictionary maps."""

    __VERSION_ELEMENT: str = "Version"
    __DESCRIPTIONS_ELEMENT: str = "Descriptions"
    __DEVICES_ELEMENT: str = "Devices"
    __DEVICE_ELEMENT: str = "Device"

    # Vendor
    __VENDOR_ELEMENT: str = "Vendor"
    __VENDOR_ID_ELEMENT: str = "Id"
    __VENDOR_IMAGE_DATA_ELEMENT: str = "ImageData16x14"

    # Safety Modules
    __MODULES_ELEMENT: str = "Modules"
    __MODULE_ELEMENT: str = "Module"
    __MODULE_TYPE_ELEMENT: str = "Type"
    __MODULE_IDENT_ELEMENT: str = "ModuleIdent"

    # Slots
    __SLOTS_ELEMENT: str = "Slots"
    __SLOT_ELEMENT: str = "Slot"
    __SLOT_NAME_ELEMENT: str = "Name"
    __SLOT_MODULE_IDENT_ELEMENT: str = "ModuleIdent"
    __SLOT_MODULE_IDENT_DEFAULT_ATTR: str = "Default"

    # CoE
    __MAILBOX_ELEMENT: str = "Mailbox"
    __COE_ELEMENT: str = "CoE"

    def __init__(self, esi_file: Path):
        if not esi_file.exists():
            raise FileNotFoundError(f"ESI file {esi_file} does not exist.")
        self._esi_file_path: Path = esi_file

    def __set_sci_vendor(self, root: ElementTree.Element) -> None:
        """Set the vendor information in the SCI file.

        Args:
            root: The root XML element.
        """
        vendor_elem = self._find_and_check(root, self.__VENDOR_ELEMENT)
        id_elem = self._find_and_check(vendor_elem, self.__VENDOR_ID_ELEMENT)
        # Convert hex to decimal
        id_elem.text = str(int(id_elem.text.replace("#x", "0x"), 16))

        # Convert image data to uppercase
        img_elem = self._find_and_check(vendor_elem, self.__VENDOR_IMAGE_DATA_ELEMENT)
        img_elem.text = img_elem.text.upper()

    def _get_module_ident_from_module(self, safety_module: ElementTree.Element) -> int:
        """Get the module identifier from the module element.

        Returns:
            Module identifier as an integer.
        """
        type_element = self._find_and_check(safety_module, self.__MODULE_TYPE_ELEMENT)
        module_ident = type_element.attrib[self.__MODULE_IDENT_ELEMENT]
        return int(module_ident.replace("#x", "0x"), 16)

    def _filter_slots_by_module_ident(self, root: ElementTree.Element, module_ident: int) -> None:
        """Filter slots based on the configured module identifier.

        ESI file contains multiple module identifiers, but the SCI file should only
        contain the one that is actually being used by the FSoE master handler.

        Args:
            root: The root XML element.
            module_ident: The module identifier to filter by.
        """
        devices_element = self._find_and_check(root, self.__DEVICES_ELEMENT)
        device_element = self._find_and_check(devices_element, self.__DEVICE_ELEMENT)
        slots_element = self._find_and_check(device_element, self.__SLOTS_ELEMENT)

        for slot in self._findall_and_check(slots_element, self.__SLOT_ELEMENT):
            # Remove all module idents
            for remove_module_ident in self._findall_and_check(
                slot, self.__SLOT_MODULE_IDENT_ELEMENT
            ):
                slot.remove(remove_module_ident)

            # Add the corresponding module ident
            ElementTree.SubElement(slot, self.__SLOT_NAME_ELEMENT).text = "Slot 1"
            module_ident_element = ElementTree.SubElement(slot, self.__SLOT_MODULE_IDENT_ELEMENT)
            module_ident_element.text = str(hex(module_ident).replace("0x", "#x"))
            module_ident_element.set(self.__SLOT_MODULE_IDENT_DEFAULT_ATTR, "1")

    def _filter_safety_modules(self, handler: FSoEMasterHandler, root: ElementTree.Element) -> None:
        """Filter safety modules based on the configured module identifier.

        ESI file contains multiple safety modules, but the SCI file should only
        contain the one that is actually being used by the FSoE master handler.

        Args:
            handler: The FSoE master handler.
            root: The root XML element.

        Raises:
            EsiFileParseError: If no safety modules are found or if the configured module is
                not found in the ESI file.
            EsiFileParseError: if no safety module matching the configured module is found.
        """
        # Find the module used by the handler
        # module_ident_used = int(handler.__get_configured_module_ident_1())
        module_ident_used = int("0x3b00002", 16)

        description_element = self._find_and_check(root, self.__DESCRIPTIONS_ELEMENT)
        modules_element = self._find_and_check(description_element, self.__MODULES_ELEMENT)

        # Loop over the ESI modules and remove those not matching the configured module
        remove = []
        modules = self._findall_and_check(modules_element, self.__MODULE_ELEMENT)
        n_modules = len(modules)
        if n_modules == 0:
            raise EsiFileParseError(
                "No safety modules found in the ESI file. "
                "Please ensure the ESI file contains valid safety module definitions."
            )
        for module in modules:
            module_ident = self._get_module_ident_from_module(module)
            if module_ident != module_ident_used:
                remove.append(module)

        if len(remove) == n_modules:
            raise EsiFileParseError(
                f"No safety modules found in the ESI file with identifier {module_ident_used}. "
                "Please ensure the ESI file contains valid safety module definitions."
            )

        for remove_module in remove:
            modules_element.remove(remove_module)

        self._filter_slots_by_module_ident(description_element, module_ident_used)

    def _set_pdo_data(self, handler: FSoEMasterHandler, root: ElementTree.Element) -> None:
        """Set the PDO data in the SCI file.

        Args:
            handler: The FSoE master handler.
            root: The root XML element.
        """
        # TODO: use handler maps
        safe_dict = DictionaryFactory.create_dictionary(
            SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, interface=Interface.ECAT
        )
        fsoe_dict = FSoEMasterHandler.create_safe_dictionary(safe_dict)
        maps = PDUMaps.empty(fsoe_dict)
        maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        maps.inputs.add_padding(bits=6)
        maps.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
        maps.inputs.add(fsoe_dict.name_map[SS2Function.COMMAND_UID.format(i=1)])
        tpdo = TPDOMap()
        maps.fill_tpdo_map(tpdo, safe_dict)
        rpdo = RPDOMap()

        # Get the mapped registers ignoring
        # CMD, CRCs and CONNID
        mapped_registers = {}
        for map_key, pdo_map, frame_elements in zip(
            ["inputs", "outputs"], [tpdo, rpdo], [SLAVE_FRAME_ELEMENTS, MASTER_FRAME_ELEMENTS]
        ):
            mapped_registers[map_key] = []
            for item in pdo_map.items:
                if (
                    frame_elements.command_uid == item.register.identifier
                    or frame_elements.crcs_prefix in item.register.identifier
                    or frame_elements.connection_id_uid == item.register.identifier
                ):
                    continue
                mapped_registers[map_key].append(item)

        description_element = self._find_and_check(root, self.__DESCRIPTIONS_ELEMENT)
        devices_element = self._find_and_check(description_element, self.__DEVICES_ELEMENT)
        device_element = self._find_and_check(devices_element, self.__DEVICE_ELEMENT)
        mailbox_element = self._find_and_check(device_element, self.__MAILBOX_ELEMENT)
        coe_element = self._find_and_check(mailbox_element, self.__COE_ELEMENT)

        # Write the setup commands
        # The PS transition is when the device goes from PreOP to SafeOP
        for items in mapped_registers.values():
            for item in items:
                if item.register.default is None:
                    data = int.to_bytes(0, 1, "little")  # padding
                else:
                    data = convert_dtype_to_bytes(item.register.default, item.register.dtype)
                mapped_pdo = MappedPDO(
                    complete_access="true",
                    transition="PS",
                    index=str(item.register.idx),
                    subindex=str(item.register.subidx),
                    data=data.hex(),
                    data_adapt_automatically=None,
                )
                coe_element.append(mapped_pdo.serialize())

    def serialize_mapping_to_sci(self, handler: FSoEMasterHandler) -> ElementTree.ElementTree:
        """Serialize the FSoE mapping to a .sci file.

        Args:
            handler: The FSoE master handler.
            esi_file: Path to the ESI file to use for serialization.

        Returns:
            XML data.

        Raises:
            FileNotFoundError: If the ESI file does not exist.
        """
        # Read the ESI file and modify it for SCI
        root = read_xml_file(self._esi_file_path)

        root.set(self.__VERSION_ELEMENT, "1.9")
        self.__set_sci_vendor(root)
        self._filter_safety_modules(handler, root)
        self._set_pdo_data(handler, root)

        tree = ElementTree.ElementTree(root)
        ElementTree.indent(root)
        return tree

    def save_mapping_to_sci(
        self, handler: FSoEMasterHandler, filename: Path, override: bool = False
    ) -> None:
        """Save the current mapping to a .sci file.

        Args:
            handler: The FSoE master handler with the mapping to save.
            filename: Path to the .sci file to save.
            override: If True, will overwrite existing file. Defaults to False.

        Raises:
            FileExistsError: If override is False and the file already exists.
        """
        mapping_data = self.serialize_mapping_to_sci(handler)
        if override:
            filename.unlink(missing_ok=True)
        if filename.exists():
            raise FileExistsError(f"File {filename} already exists.")

        filename.parent.mkdir(parents=True, exist_ok=True)
        with filename.open("wb") as f:
            mapping_data.write(f, encoding="utf-8", xml_declaration=True)

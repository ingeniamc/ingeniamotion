import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

from ingenialink.dictionary import XMLBase
from ingenialink.pdo import PDOMap


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
class StartupCommand(XMLBase):
    """Data class to represent a startup command."""

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

    @classmethod
    def from_pdo_map(cls, pdo_map: PDOMap) -> "StartupCommand":
        """Create a StartupCommand instance from a PDOMap.

        Args:
            pdo_map: The PDOMap to convert.

        Returns:
            An instance of StartupCommand.
        """
        return cls(
            complete_access="true",
            transition="PS",  # The PS transition is when the device goes from PreOP to SafeOP
            index=str(pdo_map.map_register_index),
            subindex=str(0),
            data=pdo_map.to_pdo_value().hex(),
            data_adapt_automatically=None,
        )

    def serialize(self) -> ElementTree.Element:
        """Serialize the StartupCommand instance to an XML element.

        Returns:
            XML element representing the StartupCommand instance.
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

    # SCI
    __SCI_ELEMENT: str = "Sci"
    __SCI_VERSION_ATTR: str = "SciVersion"
    __NAME_ELEMENT: str = "Name"
    __GUID_ELEMENT: str = "Guid"
    __CREATED_BY_ELEMENT: str = "CreatedBy"
    __COMPANY_ELEMENT: str = "Company"

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

    # PDOs
    __RXPDO_ELEMENT: str = "RxPdo"
    __TXPDO_ELEMENT: str = "TxPdo"
    __PDO_FIXED_ATTR: str = "Fixed"
    __PDO_MANDATORY_ATTR: str = "Mandatory"
    __PDO_SM_ATTR: str = "Sm"
    __PDO_ENTRY_ELEMENT: str = "Entry"
    __PDO_INDEX_ELEMENT: str = "Index"
    __PDO_INDEX_DEPEND_ON_SLOT_ATTR: str = "DependOnSlot"
    __PDO_EXCLUDE_ELEMENT: str = "Exclude"

    def __init__(self) -> None:
        pass

    def __set_sci_vendor(self, root: ElementTree.Element) -> None:
        """Set the vendor information in the SCI file.

        Args:
            root: The root XML element.

        Raises:
            EsiFileParseError: If the vendor ID element is missing in the ESI file.
            EsiFileParseError: If the vendor image data element is missing in the ESI file.
        """
        vendor_elem = self._find_and_check(root, self.__VENDOR_ELEMENT)
        id_elem = self._find_and_check(vendor_elem, self.__VENDOR_ID_ELEMENT)
        if id_elem.text is None:
            raise EsiFileParseError(
                "Vendor ID element is missing in the ESI file. "
                "Please ensure the ESI file contains a valid Vendor ID."
            )
        # Convert hex to decimal
        id_elem.text = str(int(id_elem.text.replace("#x", "0x"), 16))

        # Convert image data to uppercase
        img_elem = self._find_and_check(vendor_elem, self.__VENDOR_IMAGE_DATA_ELEMENT)
        if img_elem.text is None:
            raise EsiFileParseError(
                "Vendor image data element is missing in the ESI file. "
                "Please ensure the ESI file contains a valid Vendor image data."
            )
        img_elem.text = img_elem.text.upper()

    def __set_sci_info(self, root: ElementTree.Element, part_number: Optional[str] = None) -> None:
        """Set the SCI file information.

        Args:
            root: The root XML element.
            part_number: Optional part number for the device.
        """
        description_element = self._find_and_check(root, self.__DESCRIPTIONS_ELEMENT)
        devices_element = self._find_and_check(description_element, self.__DEVICES_ELEMENT)
        device_element = self._find_and_check(devices_element, self.__DEVICE_ELEMENT)

        sci_element = ElementTree.Element(self.__SCI_ELEMENT)
        sci_element.set(self.__SCI_VERSION_ATTR, "1.0.13")
        ElementTree.SubElement(sci_element, self.__NAME_ELEMENT).text = (
            "Drive 1" if part_number is None else f"Drive 1 ({part_number})"
        )
        ElementTree.SubElement(sci_element, self.__GUID_ELEMENT).text = str(uuid.uuid4())
        created_by_element = ElementTree.SubElement(sci_element, self.__CREATED_BY_ELEMENT)
        ElementTree.SubElement(created_by_element, self.__COMPANY_ELEMENT).text = "Novanta"

        device_element.insert(0, sci_element)  # Insert as first child

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

    def _filter_safety_modules(self, module_ident: int, root: ElementTree.Element) -> None:
        """Filter safety modules based on the configured module identifier.

        ESI file contains multiple safety modules, but the SCI file should only
        contain the one that is actually being used by the FSoE master handler.

        Args:
            module_ident: module identifier to filter by.
            root: The root XML element.

        Raises:
            EsiFileParseError: If no safety modules are found or if the configured module is
                not found in the ESI file.
            EsiFileParseError: if no safety module matching the configured module is found.
        """
        description_element = self._find_and_check(root, self.__DESCRIPTIONS_ELEMENT)
        modules_element = self._find_and_check(description_element, self.__MODULES_ELEMENT)
        modules = self._findall_and_check(modules_element, self.__MODULE_ELEMENT)

        # Loop over the ESI modules and remove those not matching the configured module
        remove = []
        n_modules = len(modules)
        if n_modules == 0:
            raise EsiFileParseError(
                "No safety modules found in the ESI file. "
                "Please ensure the ESI file contains valid safety module definitions."
            )

        for module in modules:
            module_module_ident = self._get_module_ident_from_module(module)
            if module_module_ident != module_ident:
                remove.append(module)

        if len(remove) == n_modules:
            raise EsiFileParseError(
                f"No safety modules found in the ESI file with identifier {module_ident}. "
                "Please ensure the ESI file contains valid safety module definitions."
            )

        for remove_module in remove:
            modules_element.remove(remove_module)

        self._filter_slots_by_module_ident(description_element, module_ident)

    def _set_startup_commands(self, rpdo: PDOMap, tpdo: PDOMap, root: ElementTree.Element) -> None:
        """Set the startup commands in the SCI file.

        Args:
            rpdo: The RPDO map.
            tpdo: The TPDO map.
            root: The root XML element.
        """
        description_element = self._find_and_check(root, self.__DESCRIPTIONS_ELEMENT)
        devices_element = self._find_and_check(description_element, self.__DEVICES_ELEMENT)
        device_element = self._find_and_check(devices_element, self.__DEVICE_ELEMENT)
        mailbox_element = self._find_and_check(device_element, self.__MAILBOX_ELEMENT)
        coe_element = self._find_and_check(mailbox_element, self.__COE_ELEMENT)

        # Write the setup commands
        for pdo_map in [tpdo, rpdo]:
            coe_element.append(StartupCommand.from_pdo_map(pdo_map).serialize())

    def _modify_pdos(self, root: ElementTree.Element) -> None:
        """Modifies the PDOs to include the attributes required by the SCI.

        Args:
            root: The root XML element.
        """
        description_element = self._find_and_check(root, self.__DESCRIPTIONS_ELEMENT)
        devices_element = self._find_and_check(description_element, self.__DEVICES_ELEMENT)
        device_element = self._find_and_check(devices_element, self.__DEVICE_ELEMENT)
        rxpdo_elements = self._findall_and_check(device_element, self.__RXPDO_ELEMENT)
        txpdo_elements = self._findall_and_check(device_element, self.__TXPDO_ELEMENT)

        for pdo_elements in [rxpdo_elements, txpdo_elements]:
            for pdo in pdo_elements:
                sm_value = pdo.attrib.get(self.__PDO_SM_ATTR, None)
                if sm_value is not None:
                    pdo.attrib.pop(self.__PDO_SM_ATTR, None)
                pdo.set(self.__PDO_FIXED_ATTR, "true")
                pdo.set(self.__PDO_MANDATORY_ATTR, "true")
                if sm_value is not None:
                    pdo.set(self.__PDO_SM_ATTR, sm_value)

                exclude_elements = self._findall_and_check(pdo, self.__PDO_EXCLUDE_ELEMENT)
                for exclude_element in exclude_elements:
                    pdo.remove(exclude_element)

                index_element = self._find_and_check(pdo, self.__PDO_INDEX_ELEMENT)
                index_element.attrib.pop(self.__PDO_INDEX_DEPEND_ON_SLOT_ATTR, None)

                entry_elements = self._findall_and_check(pdo, self.__PDO_ENTRY_ELEMENT)
                for entry in entry_elements:
                    index_element = self._find_and_check(entry, self.__PDO_INDEX_ELEMENT)
                    index_element.attrib.pop(self.__PDO_INDEX_DEPEND_ON_SLOT_ATTR, None)

    def serialize_mapping_to_sci(
        self,
        esi_file: Path,
        rpdo: PDOMap,
        tpdo: PDOMap,
        module_ident: int,
        part_number: Optional[str] = None,
    ) -> ElementTree.ElementTree:
        """Serialize the FSoE mapping to a .sci file.

        Args:
            esi_file: Path to the ESI file to use for serialization.
            rpdo: The RPDO map to serialize.
            tpdo: The TPDO map to serialize.
            module_ident: The module identifier.
            part_number: Optional part number for the device.

        Returns:
            XML data.

        Raises:
            FileNotFoundError: If the ESI file does not exist.
        """
        if not esi_file.exists():
            raise FileNotFoundError(f"ESI file {esi_file} does not exist.")

        # Read the ESI file and modify it for SCI
        root = read_xml_file(esi_file)

        root.set(self.__VERSION_ELEMENT, "1.9")
        self.__set_sci_vendor(root)
        self.__set_sci_info(root, part_number=part_number)
        self._filter_safety_modules(module_ident=module_ident, root=root)
        self._modify_pdos(root=root)
        self._set_startup_commands(rpdo=rpdo, tpdo=tpdo, root=root)

        tree = ElementTree.ElementTree(root)
        ElementTree.indent(root, space="    ")
        return tree

    def save_mapping_to_sci(
        self,
        esi_file: Path,
        sci_file: Path,
        rpdo: PDOMap,
        tpdo: PDOMap,
        module_ident: int,
        part_number: Optional[str] = None,
        override: bool = False,
    ) -> None:
        """Save the current mapping to a .sci file.

        Args:
            esi_file: Path to the ESI file to use for serialization.
            sci_file: Path to the .sci file to save.
            rpdo: The RPDO map to save.
            tpdo: The TPDO map to save.
            module_ident: The module identifier.
            part_number: Optional part number for the device.
            override: If True, will overwrite existing file. Defaults to False.

        Raises:
            FileExistsError: If override is False and the file already exists.
        """
        if override:
            sci_file.unlink(missing_ok=True)
        if sci_file.exists():
            raise FileExistsError(f"File {sci_file} already exists.")
        sci_file.parent.mkdir(parents=True, exist_ok=True)

        mapping_data = self.serialize_mapping_to_sci(
            esi_file=esi_file,
            rpdo=rpdo,
            tpdo=tpdo,
            module_ident=module_ident,
            part_number=part_number,
        )
        with sci_file.open("wb") as f:
            mapping_data.write(f, encoding="utf-8", xml_declaration=True)

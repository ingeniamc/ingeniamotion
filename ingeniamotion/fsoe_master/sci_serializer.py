from pathlib import Path
from xml.etree import ElementTree

from ingenialink.dictionary import XMLBase
from ingenialogger import get_logger

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler


logger = get_logger(__name__)


class EsiFileParseError(Exception):
    """ESI file parse error."""


def read_xml_file(file_path: Path) -> ElementTree.Element:
    """Read the content of an XML file.

    Args:
        file_path: Path to the XML file.

    Raises:
        FileNotFoundError: If the XML file does not exist.

    Returns:
        The root element of the parsed XML tree.
    """
    try:
        with open(file_path, encoding="utf-8") as xml_file:
            tree = ElementTree.parse(xml_file)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"There is not any XML file in the path: {file_path}") from e
    return tree.getroot()


class FSoEDictionaryMapSciSerializer(XMLBase):
    """Class to handle serialization and deserialization of FSoE dictionary maps."""

    __VERSION_ELEMENT: str = "Version"
    __DESCRIPTIONS_ELEMENT: str = "Descriptions"
    __DEVICES_ELEMENT: str = "Devices"
    __DEVICE_ELEMENT: str = "Device"

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

    def __init__(self, esi_file: Path):
        if not esi_file.exists():
            raise FileNotFoundError(f"ESI file {esi_file} does not exist.")
        self._esi_file_path: Path = esi_file

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

        Args:
            handler: The FSoE master handler.

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
        # Create the root SCI XML structure
        root = read_xml_file(self._esi_file_path)
        root.set(self.__VERSION_ELEMENT, "1.9")

        vendor_elem = root.find("Vendor")
        id_elem = vendor_elem.find("Id")
        if id_elem is not None and id_elem.text:
            # Convert hex to decimal
            id_elem.text = str(int(id_elem.text.replace("#x", "0x"), 16))
        # Convert image data to uppercase if needed
        img_elem = vendor_elem.find("ImageData16x14")
        if img_elem is not None and img_elem.text:
            img_elem.text = img_elem.text.upper()

        self._filter_safety_modules(handler, root)

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

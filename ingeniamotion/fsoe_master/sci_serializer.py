from dataclasses import dataclass
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


@dataclass(frozen=True)
class XMLParsedElement(XMLBase):
    """Base class for XML elements parsed from ESI files."""

    def _read_element(self, root: ElementTree.Element, element: str) -> None:
        found_element = self._find_and_check(root, element)
        if found_element.text is None:
            raise EsiFileParseError(f"'{element}' is empty")
        return found_element.text.strip()


@dataclass(frozen=True)
class Vendor(XMLParsedElement):
    """Class to represent a vendor in the ESI file."""

    id: str
    name: str
    image_data: str

    __VENDOR_ELEMENT: str = "Vendor"
    __VENDOR_ID_ELEMENT: str = "Id"
    __VENDOR_NAME_ELEMENT: str = "Name"
    __VENDOR_IMAGE_ELEMENT: str = "ImageData16x14"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "Vendor":
        """Create a Vendor instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        return cls(
            id=cls._read_element(cls, element, cls.__VENDOR_ID_ELEMENT),
            name=cls._read_element(cls, element, cls.__VENDOR_NAME_ELEMENT),
            image_data=cls._read_element(cls, element, cls.__VENDOR_IMAGE_ELEMENT),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the Vendor instance to a SCI XML element.

        Returns:
            Vendor XML element.
        """
        root = ElementTree.Element(self.__VENDOR_ELEMENT)
        ElementTree.SubElement(root, self.__VENDOR_ID_ELEMENT).text = str(
            int(self.id.replace("#x", "0x"), 16)
        )  # ESI file represantion is hex
        ElementTree.SubElement(root, self.__VENDOR_NAME_ELEMENT).text = self.name
        ElementTree.SubElement(root, self.__VENDOR_IMAGE_ELEMENT).text = self.image_data
        return root


class EsiFile(XMLBase):
    """Class to handle ESI file operations."""

    __VENDOR_ELEMENT = "Vendor"

    def __init__(self, esi_file_path: Path):
        self.path = esi_file_path

        self.root: ElementTree.Element
        self.vendor: Vendor

        self._read_esi_file()

    def _read_esi_file(self) -> None:
        """Read the content of an ESI file.

        Raises:
            FileNotFoundError: If the ESI file does not exist.
        """
        try:
            with open(self.path, encoding="utf-8") as esi_file:
                tree = ElementTree.parse(esi_file)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"There is not any esi file in the path: {self.path}") from e

        self.root = tree.getroot()
        vendor_element = self.root.find(self.__VENDOR_ELEMENT)
        self.vendor = Vendor.from_element(vendor_element)


class FSoEDictionaryMapSciSerializer:
    """Class to handle serialization and deserialization of FSoE dictionary maps."""

    def __init__(self, esi_file: Path):
        if not esi_file.exists():
            raise FileNotFoundError(f"ESI file {esi_file} does not exist.")
        self.esi_file: EsiFile = EsiFile(esi_file)

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
        root = ElementTree.Element("EtherCATInfo")
        root.set("Version", "1.9")
        root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
        root.set("xsi:noNamespaceSchemaLocation", "EtherCATInfo.xsd")

        vendor_elem = self.esi_file.vendor.to_sci()
        root.append(vendor_elem)

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

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

    ELEMENT: str = "Vendor"
    __ID_ELEMENT: str = "Id"
    __NAME_ELEMENT: str = "Name"
    __IMAGE_ELEMENT: str = "ImageData16x14"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "Vendor":
        """Create a Vendor instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        return cls(
            id=cls._read_element(cls, element, cls.__ID_ELEMENT),
            name=cls._read_element(cls, element, cls.__NAME_ELEMENT),
            image_data=cls._read_element(cls, element, cls.__IMAGE_ELEMENT),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the Vendor instance to a SCI XML element.

        Returns:
            Vendor XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        ElementTree.SubElement(root, self.__ID_ELEMENT).text = str(
            int(self.id.replace("#x", "0x"), 16)
        )  # ESI file represantion is hex
        ElementTree.SubElement(root, self.__NAME_ELEMENT).text = self.name
        ElementTree.SubElement(
            root, self.__IMAGE_ELEMENT
        ).text = self.image_data.upper()  # Capital letters for SCI format
        return root


@dataclass(frozen=True)
class Group(XMLParsedElement):
    """Class to represent a group in the ESI file."""

    sort_order: str
    group_type: str
    name: str
    name_lcid: str
    image_data: str

    ELEMENT: str = "Group"
    __SORTORDER_ATTR: str = "SortOrder"
    __TYPE_ELEMENT: str = "Type"
    __NAME_ELEMENT: str = "Name"
    __NAME_LCID_ATTR: str = "LcId"
    __IMAGE_ELEMENT: str = "ImageData16x14"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "Group":
        """Create a Group instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        name_element = cls._find_and_check(element, cls.__NAME_ELEMENT)
        return cls(
            sort_order=element.attrib[cls.__SORTORDER_ATTR],
            group_type=cls._read_element(cls, element, cls.__TYPE_ELEMENT),
            name=name_element.text,
            name_lcid=name_element.attrib[cls.__NAME_LCID_ATTR],
            image_data=cls._read_element(cls, element, cls.__IMAGE_ELEMENT),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the Group instance to a SCI XML element.

        Returns:
            Group XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        root.set(self.__SORTORDER_ATTR, self.sort_order)
        ElementTree.SubElement(root, self.__TYPE_ELEMENT).text = self.group_type
        name_element = ElementTree.SubElement(root, self.__NAME_ELEMENT)
        name_element.text = self.name
        name_element.set(self.__NAME_LCID_ATTR, self.name_lcid)
        ElementTree.SubElement(
            root, self.__IMAGE_ELEMENT
        ).text = self.image_data.upper()  # Capital letters for SCI format
        return root


@dataclass(frozen=True)
class Groups(XMLParsedElement):
    """Class to represent Groups in the ESI file."""

    groups: list[Group]

    ELEMENT: str = "Groups"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "Groups":
        """Create a Groups instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        groups_elements = cls._findall_and_check(element, Group.ELEMENT)
        groups = [Group.from_element(group) for group in groups_elements]
        return cls(groups=groups)

    def to_sci(self) -> ElementTree.Element:
        """Convert the Groups instance to a SCI XML element.

        Returns:
            Groups XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        for group in self.groups:
            root.append(group.to_sci())
        return root


@dataclass(frozen=True)
class Device(XMLParsedElement):
    """Class to represent a device in the ESI file."""

    device_type: str
    product_code: str
    revision_no: str
    name: str
    name_lcid: str
    # TODO: continue parsing stuff

    ELEMENT: str = "Device"
    __TYPE_ELEMENT: str = "Type"
    __PRODUCT_CODE_ATTR: str = "ProductCode"
    __REVISION_NO_ATTR: str = "RevisionNo"
    __NAME_ELEMENT: str = "Name"
    __NAME_LCID_ATTR: str = "LcId"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "Device":
        """Create a Device instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        type_element = cls._find_and_check(element, cls.__TYPE_ELEMENT)
        name_element = cls._find_and_check(element, cls.__NAME_ELEMENT)
        return cls(
            device_type=cls._read_element(cls, element, cls.__TYPE_ELEMENT),
            product_code=type_element.attrib[cls.__PRODUCT_CODE_ATTR],
            revision_no=type_element.attrib[cls.__REVISION_NO_ATTR],
            name=name_element.text,
            name_lcid=name_element.attrib[cls.__NAME_LCID_ATTR],
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the Device instance to a SCI XML element.

        Returns:
            Device XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        type_element = ElementTree.SubElement(root, self.__TYPE_ELEMENT)
        type_element.text = self.device_type
        type_element.set(self.__PRODUCT_CODE_ATTR, self.product_code)
        type_element.set(self.__REVISION_NO_ATTR, self.revision_no)
        name_element = ElementTree.SubElement(root, self.__NAME_ELEMENT)
        name_element.text = self.name
        name_element.set(self.__NAME_LCID_ATTR, self.name_lcid)
        return root


@dataclass(frozen=True)
class Devices(XMLParsedElement):
    """Class to represent Devices in the ESI file."""

    devices: list[Device]

    ELEMENT: str = "Devices"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "Devices":
        """Create a Devices instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        devices_elements = cls._findall_and_check(element, Device.ELEMENT)
        devices = [Device.from_element(device) for device in devices_elements]
        return cls(devices=devices)

    def to_sci(self) -> ElementTree.Element:
        """Convert the Devices instance to a SCI XML element.

        Returns:
            Devices XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        for device in self.devices:
            root.append(device.to_sci())
        return root


@dataclass(frozen=True)
class Descriptions(XMLParsedElement):
    """Class to represent Descriptions in the ESI file."""

    groups: Groups
    devices: Devices

    ELEMENT: str = "Descriptions"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "Descriptions":
        """Create a Descriptions instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        groups_element = cls._find_and_check(element, Groups.ELEMENT)
        groups = Groups.from_element(groups_element)
        devices_element = cls._find_and_check(element, Devices.ELEMENT)
        devices = Devices.from_element(devices_element)
        return cls(groups=groups, devices=devices)

    def to_sci(self) -> ElementTree.Element:
        """Convert the Descriptions instance to a SCI XML element.

        Returns:
            Descriptions XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        root.append(self.groups.to_sci())
        root.append(self.devices.to_sci())
        return root


class EsiFile(XMLBase):
    """Class to handle ESI file operations."""

    def __init__(self, esi_file_path: Path):
        self.path = esi_file_path

        self.vendor: Vendor
        self.descriptions: Descriptions

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

        root = tree.getroot()
        self.vendor = Vendor.from_element(self._find_and_check(root, Vendor.ELEMENT))
        self.descriptions = Descriptions.from_element(
            self._find_and_check(root, Descriptions.ELEMENT)
        )


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

        root.append(self.esi_file.vendor.to_sci())
        root.append(self.esi_file.descriptions.to_sci())

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

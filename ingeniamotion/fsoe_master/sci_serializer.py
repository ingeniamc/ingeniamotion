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

    def _read_element(self, root: ElementTree.Element, element: str) -> str:
        found_element = self._find_and_check(root, element)
        if found_element.text is None:
            raise EsiFileParseError(f"'{element}' is empty")
        return found_element.text.strip()

    def _read_optional_element(self, root: ElementTree.Element, element: str) -> str:
        try:
            found_element = self._find_and_check(root, element)
            if found_element.text is None:
                return None
            return found_element.text.strip()
        except Exception:
            return None


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
class DeviceInfo(XMLParsedElement):
    """Class to represent info from a device in the ESI file."""

    preop_timeout: str
    safeop_timeout: str
    back_to_init_timeout: str
    back_to_safeop_timeout: str
    request_timeout: str
    response_timeout: str
    dpram_size: str
    sm_count: str
    fmmu_count: str

    ELEMENT: str = "Info"

    __TIMEOUT_ELEMENT: str = "Timeout"

    __STATEMACHINE_ELEMENT: str = "StateMachine"
    __PREOP_TIMEOUT_ELEMENT: str = "PreopTimeout"
    __SAFEOP_TIMEOUT_ELEMENT: str = "SafeopOpTimeout"
    __BACK_TO_INIT_TIMEOUT_ELEMENT: str = "BackToInitTimeout"
    __BACK_TO_SAFEOP_TIMEOUT_ELEMENT: str = "BackToSafeopTimeout"

    __MAILBOX_ELEMENT: str = "Mailbox"
    __REQUEST_TIMEOUT_ELEMENT: str = "RequestTimeout"
    __RESPONSE_TIMEOUT_ELEMENT: str = "ResponseTimeout"

    __ETHERCAT_CONTROLLER_ELEMENT: str = "EtherCATController"
    __DPRAM_SIZE_ELEMENT: str = "DpramSize"
    __SMCOUNT_ELEMENT: str = "SmCount"
    __FMMU_COUNT_ELEMENT: str = "FmmuCount"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "DeviceInfo":
        """Create a DeviceInfo instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        state_machine = cls._find_and_check(element, cls.__STATEMACHINE_ELEMENT)
        state_machine_timeout = cls._find_and_check(state_machine, cls.__TIMEOUT_ELEMENT)
        mailbox_element = cls._find_and_check(element, cls.__MAILBOX_ELEMENT)
        mailbox_timeout = cls._find_and_check(mailbox_element, cls.__TIMEOUT_ELEMENT)
        ethercat_controller = cls._find_and_check(element, cls.__ETHERCAT_CONTROLLER_ELEMENT)

        return cls(
            preop_timeout=cls._read_element(
                cls, state_machine_timeout, cls.__PREOP_TIMEOUT_ELEMENT
            ),
            safeop_timeout=cls._read_element(
                cls, state_machine_timeout, cls.__SAFEOP_TIMEOUT_ELEMENT
            ),
            back_to_init_timeout=cls._read_element(
                cls, state_machine_timeout, cls.__BACK_TO_INIT_TIMEOUT_ELEMENT
            ),
            back_to_safeop_timeout=cls._read_element(
                cls, state_machine_timeout, cls.__BACK_TO_SAFEOP_TIMEOUT_ELEMENT
            ),
            request_timeout=cls._read_element(cls, mailbox_timeout, cls.__REQUEST_TIMEOUT_ELEMENT),
            response_timeout=cls._read_element(
                cls, mailbox_timeout, cls.__RESPONSE_TIMEOUT_ELEMENT
            ),
            dpram_size=cls._read_element(cls, ethercat_controller, cls.__DPRAM_SIZE_ELEMENT),
            sm_count=cls._read_element(cls, ethercat_controller, cls.__SMCOUNT_ELEMENT),
            fmmu_count=cls._read_element(cls, ethercat_controller, cls.__FMMU_COUNT_ELEMENT),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the DeviceInfo instance to a SCI XML element.

        Returns:
            DeviceInfo XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        state_machine = ElementTree.SubElement(root, self.__STATEMACHINE_ELEMENT)
        state_machine_timeout = ElementTree.SubElement(state_machine, self.__TIMEOUT_ELEMENT)
        ElementTree.SubElement(
            state_machine_timeout, self.__PREOP_TIMEOUT_ELEMENT
        ).text = self.preop_timeout
        ElementTree.SubElement(
            state_machine_timeout, self.__SAFEOP_TIMEOUT_ELEMENT
        ).text = self.safeop_timeout
        ElementTree.SubElement(
            state_machine_timeout, self.__BACK_TO_INIT_TIMEOUT_ELEMENT
        ).text = self.back_to_init_timeout
        ElementTree.SubElement(
            state_machine_timeout, self.__BACK_TO_SAFEOP_TIMEOUT_ELEMENT
        ).text = self.back_to_safeop_timeout
        mailbox = ElementTree.SubElement(root, self.__MAILBOX_ELEMENT)
        mailbox_timeout = ElementTree.SubElement(mailbox, self.__TIMEOUT_ELEMENT)
        ElementTree.SubElement(
            mailbox_timeout, self.__REQUEST_TIMEOUT_ELEMENT
        ).text = self.request_timeout
        ElementTree.SubElement(
            mailbox_timeout, self.__RESPONSE_TIMEOUT_ELEMENT
        ).text = self.response_timeout
        ethercat_controller = ElementTree.SubElement(root, self.__ETHERCAT_CONTROLLER_ELEMENT)
        ElementTree.SubElement(
            ethercat_controller, self.__DPRAM_SIZE_ELEMENT
        ).text = self.dpram_size
        ElementTree.SubElement(ethercat_controller, self.__SMCOUNT_ELEMENT).text = self.sm_count
        ElementTree.SubElement(
            ethercat_controller, self.__FMMU_COUNT_ELEMENT
        ).text = self.fmmu_count
        return root


@dataclass(frozen=True)
class DictionaryDataType(XMLParsedElement):
    """Class to represent a data type in the profile dictionary."""

    name: str
    bit_size: str

    ELEMENT: str = "DataType"
    __NAME_ELEMENT: str = "Name"
    __BITSIZE_ELEMENT: str = "BitSize"
    # TODO: are extra elements

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "DictionaryDataType":
        """Create a DictionaryDataType instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        return cls(
            name=cls._read_element(cls, element, cls.__NAME_ELEMENT),
            bit_size=cls._read_element(cls, element, cls.__BITSIZE_ELEMENT),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the DictionaryDataType instance to a SCI XML element.

        Returns:
            DictionaryDataType XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        ElementTree.SubElement(root, self.__NAME_ELEMENT).text = self.name
        ElementTree.SubElement(root, self.__BITSIZE_ELEMENT).text = self.bit_size
        return root


@dataclass(frozen=True)
class DictionaryObject(XMLParsedElement):
    """Class to represent an object in the profile dictionary."""

    index: str
    name: str
    type: str
    bit_size: str

    ELEMENT: str = "Object"
    __INDEX_ELEMENT: str = "Index"
    __NAME_ELEMENT: str = "Name"
    __TYPE_ELEMENT: str = "Type"
    __BITSIZE_ELEMENT: str = "BitSize"

    # TODO: are extra elements

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "DictionaryObject":
        """Create a DictionaryObject instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        return cls(
            index=cls._read_element(cls, element, cls.__INDEX_ELEMENT),
            name=cls._read_element(cls, element, cls.__NAME_ELEMENT),
            type=cls._read_element(cls, element, cls.__TYPE_ELEMENT),
            bit_size=cls._read_element(cls, element, cls.__BITSIZE_ELEMENT),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the DictionaryObject instance to a SCI XML element.

        Returns:
            DictionaryObject XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        ElementTree.SubElement(root, self.__INDEX_ELEMENT).text = self.index
        ElementTree.SubElement(root, self.__NAME_ELEMENT).text = self.name
        ElementTree.SubElement(root, self.__TYPE_ELEMENT).text = self.type
        ElementTree.SubElement(root, self.__BITSIZE_ELEMENT).text = self.bit_size
        return root


@dataclass(frozen=True)
class ProfileDictionary(XMLParsedElement):
    """Class to represent a profile dictionary in the ESI file."""

    datatypes: list[DictionaryDataType]
    objects: list[DictionaryObject]

    ELEMENT: str = "Dictionary"
    __DATATYPES_ELEMENT: str = "DataTypes"
    __OBJECTS_ELEMENT: str = "Objects"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "ProfileDictionary":
        """Create a ProfileDictionary instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        datatypes_element = cls._find_and_check(element, cls.__DATATYPES_ELEMENT)
        datatypes = [
            DictionaryDataType.from_element(dt)
            for dt in cls._findall_and_check(datatypes_element, DictionaryDataType.ELEMENT)
        ]
        objects_elements = cls._find_and_check(element, cls.__OBJECTS_ELEMENT)
        objects = [
            DictionaryObject.from_element(obj)
            for obj in cls._findall_and_check(objects_elements, DictionaryObject.ELEMENT)
        ]
        return cls(datatypes=datatypes, objects=objects)

    def to_sci(self) -> ElementTree.Element:
        """Convert the ProfileDictionary instance to a SCI XML element.

        Returns:
            ProfileDictionary XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        datatypes_element = ElementTree.SubElement(root, self.__DATATYPES_ELEMENT)
        for data_type in self.datatypes:
            datatype_element = ElementTree.SubElement(datatypes_element, DictionaryDataType.ELEMENT)
            datatype_element.append(data_type.to_sci())
        objects_element = ElementTree.SubElement(root, self.__OBJECTS_ELEMENT)
        for obj in self.objects:
            obj_element = ElementTree.SubElement(objects_element, DictionaryObject.ELEMENT)
            obj_element.append(obj.to_sci())
        return root


@dataclass(frozen=True)
class DeviceProfile(XMLParsedElement):
    """Class to represent a device profile in the ESI file."""

    profile_no: str
    dictionary: ProfileDictionary

    ELEMENT = "Profile"
    __PROFILE_NO_ELEMENT: str = "ProfileNo"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "DeviceProfile":
        """Create a DeviceProfile instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        return cls(
            profile_no=cls._read_element(cls, element, cls.__PROFILE_NO_ELEMENT),
            dictionary=ProfileDictionary.from_element(
                cls._find_and_check(element, ProfileDictionary.ELEMENT)
            ),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the DeviceProfile instance to a SCI XML element.

        Returns:
            DeviceProfile XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        ElementTree.SubElement(root, self.__PROFILE_NO_ELEMENT).text = self.profile_no
        root.append(self.dictionary.to_sci())
        return root


@dataclass(frozen=True)
class Device(XMLParsedElement):
    """Class to represent a device in the ESI file."""

    physics: str
    device_type: str
    product_code: str
    revision_no: str
    name: str
    name_lcid: str

    info: DeviceInfo
    group_type: str
    profile: DeviceProfile

    ELEMENT: str = "Device"
    __PHYSICS_ATTR: str = "Physics"
    __TYPE_ELEMENT: str = "Type"
    __PRODUCT_CODE_ATTR: str = "ProductCode"
    __REVISION_NO_ATTR: str = "RevisionNo"
    __NAME_ELEMENT: str = "Name"
    __NAME_LCID_ATTR: str = "LcId"
    __GROUP_TYPE_ATTR: str = "GroupType"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "Device":
        """Create a Device instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        type_element = cls._find_and_check(element, cls.__TYPE_ELEMENT)
        name_element = cls._find_and_check(element, cls.__NAME_ELEMENT)
        return cls(
            physics=element.attrib[cls.__PHYSICS_ATTR],
            device_type=cls._read_element(cls, element, cls.__TYPE_ELEMENT),
            product_code=type_element.attrib[cls.__PRODUCT_CODE_ATTR],
            revision_no=type_element.attrib[cls.__REVISION_NO_ATTR],
            name=name_element.text,
            name_lcid=name_element.attrib[cls.__NAME_LCID_ATTR],
            info=DeviceInfo.from_element(cls._find_and_check(element, DeviceInfo.ELEMENT)),
            group_type=cls._read_element(cls, element, cls.__GROUP_TYPE_ATTR),
            profile=DeviceProfile.from_element(cls._find_and_check(element, DeviceProfile.ELEMENT)),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the Device instance to a SCI XML element.

        Returns:
            Device XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        root.set(self.__PHYSICS_ATTR, self.physics)
        type_element = ElementTree.SubElement(root, self.__TYPE_ELEMENT)
        type_element.text = self.device_type
        type_element.set(self.__PRODUCT_CODE_ATTR, self.product_code)
        type_element.set(self.__REVISION_NO_ATTR, self.revision_no)
        name_element = ElementTree.SubElement(root, self.__NAME_ELEMENT)
        name_element.text = self.name
        name_element.set(self.__NAME_LCID_ATTR, self.name_lcid)
        root.append(self.info.to_sci())
        ElementTree.SubElement(root, self.__GROUP_TYPE_ATTR).text = self.group_type
        root.append(self.profile.to_sci())
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

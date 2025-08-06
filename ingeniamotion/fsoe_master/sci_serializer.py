from dataclasses import dataclass
from pathlib import Path
from typing import Optional
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

    @classmethod
    def _find_and_check_optional(
        cls, root: ElementTree.Element, path: str
    ) -> Optional[ElementTree.Element]:
        return root.find(path)

    @classmethod
    def _findall_and_check_optional(
        cls, root: ElementTree.Element, path: str
    ) -> Optional[list[ElementTree.Element]]:
        return root.findall(path)

    def _read_optional_element(self, root: ElementTree.Element, element: str) -> str:
        found_element = self._find_and_check_optional(root, element)
        if found_element is None or found_element.text is None:
            return None
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
class ArrayInfo(XMLParsedElement):
    """Class to represent array information in the profile dictionary."""

    lbound: str
    elements: str

    ELEMENT: str = "ArrayInfo"
    __LBOUND_ELEMENT: str = "LBound"
    __ELEMENTS_ELEMENT: str = "Elements"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "ArrayInfo":
        """Create an ArrayInfo instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        return cls(
            lbound=cls._read_element(cls, element, cls.__LBOUND_ELEMENT),
            elements=cls._read_element(cls, element, cls.__ELEMENTS_ELEMENT),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the ArrayInfo instance to a SCI XML element.

        Returns:
            ArrayInfo XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        ElementTree.SubElement(root, self.__LBOUND_ELEMENT).text = self.lbound
        ElementTree.SubElement(root, self.__ELEMENTS_ELEMENT).text = self.elements
        return root


@dataclass(frozen=True)
class SubItemFlags(XMLParsedElement):
    """Class to represent flags for a subitem in the profile dictionary."""

    access: Optional[str]
    read_restrictions: Optional[str]
    write_restrictions: Optional[str]
    category: Optional[str]
    pdo_mapping: Optional[str]
    attribute: Optional[str]
    backup: Optional[str]
    setting: Optional[str]

    ELEMENT: str = "Flags"
    __ACCESS_ELEMENT: str = "Access"
    __READ_RESTRICTIONS_ATTR: str = "ReadRestrictions"
    __WRITE_RESTRICTIONS_ATTR: str = "WriteRestrictions"
    __CATEGORY_ELEMENT: str = "Category"
    __PDO_MAPPING_ELEMENT: str = "PdoMapping"
    __ATTRIBS_ELEMENT: str = "Attribute"
    __BACKUP_ELEMENT: str = "Backup"
    __SETTING_ELEMENT: str = "Setting"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "SubItemFlags":
        """Create a SubItemFlags instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        access_element = cls._find_and_check_optional(element, cls.__ACCESS_ELEMENT)
        return cls(
            access=access_element.text.strip() if access_element is not None else None,
            read_restrictions=access_element.attrib.get(cls.__READ_RESTRICTIONS_ATTR, None)
            if access_element is not None
            else None,
            write_restrictions=access_element.attrib.get(cls.__WRITE_RESTRICTIONS_ATTR, None)
            if access_element is not None
            else None,
            category=cls._read_optional_element(cls, element, cls.__CATEGORY_ELEMENT),
            pdo_mapping=cls._read_optional_element(cls, element, cls.__PDO_MAPPING_ELEMENT),
            attribute=cls._read_optional_element(cls, element, cls.__ATTRIBS_ELEMENT),
            backup=cls._read_optional_element(cls, element, cls.__BACKUP_ELEMENT),
            setting=cls._read_optional_element(cls, element, cls.__SETTING_ELEMENT),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the SubItemFlags instance to a SCI XML element.

        Returns:
            SubItemFlags XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        if self.access is not None:
            access_element = ElementTree.SubElement(root, self.__ACCESS_ELEMENT)
            access_element.text = self.access
            if self.read_restrictions is not None:
                access_element.set(self.__READ_RESTRICTIONS_ATTR, self.read_restrictions)
            if self.write_restrictions is not None:
                access_element.set(self.__WRITE_RESTRICTIONS_ATTR, self.write_restrictions)
        if self.category is not None:
            ElementTree.SubElement(root, self.__CATEGORY_ELEMENT).text = self.category
        if self.pdo_mapping is not None:
            ElementTree.SubElement(
                root, self.__PDO_MAPPING_ELEMENT
            ).text = self.pdo_mapping.upper()  # Capital letters for SCI format
        if self.attribute is not None:
            ElementTree.SubElement(root, self.__ATTRIBS_ELEMENT).text = self.attribute
        if self.backup is not None:
            ElementTree.SubElement(root, self.__BACKUP_ELEMENT).text = self.backup
        if self.setting is not None:
            ElementTree.SubElement(root, self.__SETTING_ELEMENT).text = self.setting
        return root


@dataclass(frozen=True)
class DataTypeSubitem(XMLParsedElement):
    """Class to represent a subitem in the profile dictionary."""

    subidx: Optional[str]
    name: str
    type: str
    bit_size: str
    bit_offs: str
    default_str: Optional[str]
    default_data: Optional[str]
    min_value: Optional[str]
    max_value: Optional[str]
    default_value: Optional[str]
    flags: Optional[SubItemFlags]

    ELEMENT: str = "SubItem"
    __SUBIDX_ELEMENT: str = "SubIdx"
    __NAME_ELEMENT: str = "Name"
    __TYPE_ELEMENT: str = "Type"
    __BITSIZE_ELEMENT: str = "BitSize"
    __BITOFFS_ELEMENT: str = "BitOffs"
    __DEFAULT_STR_ELEMENT: str = "DefaultString"
    __DEFAULT_DATA_ELEMENT: str = "DefaultData"
    __MIN_VALUE_ELEMENT: str = "MinValue"
    __MAX_VALUE_ELEMENT: str = "MaxValue"
    __DEFAULT_VALUE_ELEMENT: str = "DefaultValue"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "DataTypeSubitem":
        """Create a Subitem instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        flags_element = cls._find_and_check_optional(element, SubItemFlags.ELEMENT)
        return cls(
            subidx=cls._read_optional_element(cls, element, cls.__SUBIDX_ELEMENT),
            name=cls._read_element(cls, element, cls.__NAME_ELEMENT),
            type=cls._read_element(cls, element, cls.__TYPE_ELEMENT),
            bit_size=cls._read_element(cls, element, cls.__BITSIZE_ELEMENT),
            bit_offs=cls._read_element(cls, element, cls.__BITOFFS_ELEMENT),
            default_str=cls._read_optional_element(cls, element, cls.__DEFAULT_STR_ELEMENT),
            default_data=cls._read_optional_element(cls, element, cls.__DEFAULT_DATA_ELEMENT),
            min_value=cls._read_optional_element(cls, element, cls.__MIN_VALUE_ELEMENT),
            max_value=cls._read_optional_element(cls, element, cls.__MAX_VALUE_ELEMENT),
            default_value=cls._read_optional_element(cls, element, cls.__DEFAULT_VALUE_ELEMENT),
            flags=SubItemFlags.from_element(flags_element) if flags_element is not None else None,
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the Subitem instance to a SCI XML element.

        Returns:
            Subitem XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        if self.subidx is not None:
            ElementTree.SubElement(root, self.__SUBIDX_ELEMENT).text = self.subidx
        ElementTree.SubElement(root, self.__NAME_ELEMENT).text = self.name
        ElementTree.SubElement(root, self.__TYPE_ELEMENT).text = self.type
        ElementTree.SubElement(root, self.__BITSIZE_ELEMENT).text = self.bit_size
        ElementTree.SubElement(root, self.__BITOFFS_ELEMENT).text = self.bit_offs
        if self.default_str is not None:
            ElementTree.SubElement(root, self.__DEFAULT_STR_ELEMENT).text = self.default_str
        if self.default_data is not None:
            ElementTree.SubElement(root, self.__DEFAULT_DATA_ELEMENT).text = self.default_data
        if self.min_value is not None:
            ElementTree.SubElement(root, self.__MIN_VALUE_ELEMENT).text = self.min_value
        if self.max_value is not None:
            ElementTree.SubElement(root, self.__MAX_VALUE_ELEMENT).text = self.max_value
        if self.default_value is not None:
            ElementTree.SubElement(root, self.__DEFAULT_VALUE_ELEMENT).text = self.default_value
        if self.flags is not None:
            root.append(self.flags.to_sci())
        return root


@dataclass(frozen=True)
class DictionaryDataType(XMLParsedElement):
    """Class to represent a data type in the profile dictionary."""

    index: Optional[str]
    name: str
    base_type: Optional[str]
    bit_size: str
    array_info: Optional[ArrayInfo]
    subitems: Optional[list[DataTypeSubitem]]

    ELEMENT: str = "DataType"
    __INDEX_ELEMENT: str = "Index"
    __NAME_ELEMENT: str = "Name"
    __BASE_TYPE_ELEMENT: str = "BaseType"
    __BITSIZE_ELEMENT: str = "BitSize"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "DictionaryDataType":
        """Create a DictionaryDataType instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        array_info_element = cls._find_and_check_optional(element, ArrayInfo.ELEMENT)
        subitem_elements = cls._findall_and_check_optional(element, DataTypeSubitem.ELEMENT)
        return cls(
            index=cls._read_optional_element(cls, element, cls.__INDEX_ELEMENT),
            name=cls._read_element(cls, element, cls.__NAME_ELEMENT),
            base_type=cls._read_optional_element(cls, element, cls.__BASE_TYPE_ELEMENT),
            bit_size=cls._read_element(cls, element, cls.__BITSIZE_ELEMENT),
            array_info=ArrayInfo.from_element(array_info_element)
            if array_info_element is not None
            else None,
            subitems=[DataTypeSubitem.from_element(el) for el in subitem_elements]
            if subitem_elements
            else None,
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the DictionaryDataType instance to a SCI XML element.

        Returns:
            DictionaryDataType XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        if self.index is not None:
            ElementTree.SubElement(root, self.__INDEX_ELEMENT).text = self.index
        ElementTree.SubElement(root, self.__NAME_ELEMENT).text = self.name
        if self.base_type is not None:
            ElementTree.SubElement(root, self.__BASE_TYPE_ELEMENT).text = self.base_type
        ElementTree.SubElement(root, self.__BITSIZE_ELEMENT).text = self.bit_size
        if self.array_info is not None:
            root.append(self.array_info.to_sci())
        if self.subitems is not None:
            for subitem in self.subitems:
                root.append(subitem.to_sci())
        return root


@dataclass(frozen=True)
class ObjectInfoSubitem(XMLParsedElement):
    """Class to represent subitem info in the profile dictionary."""

    name: str
    info: "ObjectInfo"

    ELEMENT: str = "Subitem"
    __NAME_ELEMENT: str = "Name"
    __INFO_ELEMENT: str = "Info"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "ObjectInfoSubitem":
        """Create an ObjectInfoSubitem instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        return cls(
            name=cls._read_element(cls, element, cls.__NAME_ELEMENT),
            info=ObjectInfo.from_element(cls._find_and_check(element, cls.__INFO_ELEMENT)),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the ObjectInfoSubitem instance to a SCI XML element.

        Returns:
            ObjectInfoSubitem XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        ElementTree.SubElement(root, self.__NAME_ELEMENT).text = self.name
        root.append(self.info.to_sci())
        return root


@dataclass(frozen=True)
class ObjectInfo(XMLParsedElement):
    """Class to represent object info in the profile dictionary."""

    default_str: Optional[str]
    min_data: Optional[str]
    max_data: Optional[str]
    default_data: Optional[str]
    min_value: Optional[str]
    max_value: Optional[str]
    default_value: Optional[str]
    subitems: Optional[list[ObjectInfoSubitem]]
    display_name: Optional[str]
    unit: Optional[str]

    ELEMENT = "Info"

    __DEFAULT_STR_ELEMENT: str = "DefaultString"
    __MIN_DATA_ELEMENT: str = "MinData"
    __MAX_DATA_ELEMENT: str = "MaxData"
    __DEFAULT_DATA_ELEMENT: str = "DefaultData"
    __MIN_VALUE_ELEMENT: str = "MinValue"
    __MAX_VALUE_ELEMENT: str = "MaxValue"
    __DEFAULT_VALUE_ELEMENT: str = "DefaultValue"
    __SUBITEM_ELEMENT: str = "SubItem"
    __DISPLAY_NAME_ELEMENT: str = "DisplayName"
    __UNIT_ELEMENT: str = "Unit"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "ObjectInfo":
        """Create an ObjectInfo instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        subitem_elements = cls._findall_and_check_optional(element, cls.__SUBITEM_ELEMENT)
        return cls(
            default_str=cls._read_optional_element(cls, element, cls.__DEFAULT_STR_ELEMENT),
            min_data=cls._read_optional_element(cls, element, cls.__MIN_DATA_ELEMENT),
            max_data=cls._read_optional_element(cls, element, cls.__MAX_DATA_ELEMENT),
            default_data=cls._read_optional_element(cls, element, cls.__DEFAULT_DATA_ELEMENT),
            min_value=cls._read_optional_element(cls, element, cls.__MIN_VALUE_ELEMENT),
            max_value=cls._read_optional_element(cls, element, cls.__MAX_VALUE_ELEMENT),
            default_value=cls._read_optional_element(cls, element, cls.__DEFAULT_VALUE_ELEMENT),
            subitems=[ObjectInfoSubitem.from_element(el) for el in subitem_elements]
            if subitem_elements
            else None,
            display_name=cls._read_optional_element(cls, element, cls.__DISPLAY_NAME_ELEMENT),
            unit=cls._read_optional_element(cls, element, cls.__UNIT_ELEMENT),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the ObjectInfo instance to a SCI XML element.

        Returns:
            ObjectInfo XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        if self.default_str is not None:
            ElementTree.SubElement(root, self.__DEFAULT_STR_ELEMENT).text = self.default_str
        if self.min_data is not None:
            ElementTree.SubElement(root, self.__MIN_DATA_ELEMENT).text = self.min_data
        if self.max_data is not None:
            ElementTree.SubElement(root, self.__MAX_DATA_ELEMENT).text = self.max_data
        if self.default_data is not None:
            ElementTree.SubElement(root, self.__DEFAULT_DATA_ELEMENT).text = self.default_data
        if self.min_value is not None:
            ElementTree.SubElement(root, self.__MIN_VALUE_ELEMENT).text = self.min_value
        if self.max_value is not None:
            ElementTree.SubElement(root, self.__MAX_VALUE_ELEMENT).text = self.max_value
        if self.default_value is not None:
            ElementTree.SubElement(root, self.__DEFAULT_VALUE_ELEMENT).text = self.default_value
        if self.subitems is not None:
            for subitem in self.subitems:
                root.append(subitem.to_sci())
        if self.display_name is not None:
            ElementTree.SubElement(root, self.__DISPLAY_NAME_ELEMENT).text = self.display_name
        if self.unit is not None:
            ElementTree.SubElement(root, self.__UNIT_ELEMENT).text = self.unit
        return root


@dataclass(frozen=True)
class ObjectFlags(XMLParsedElement):
    """Class to represent flags for an object in the profile dictionary."""

    transition: Optional[str]
    sdo_access: Optional[str]
    base_flags: SubItemFlags

    ELEMENT: str = "Flags"
    __TRANSITION_ELEMENT: str = "Transition"
    __SDO_ACCESS_ELEMENT: str = "SdoAccess"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "ObjectFlags":
        """Create an ObjectFlags instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        return cls(
            transition=cls._read_optional_element(cls, element, cls.__TRANSITION_ELEMENT),
            sdo_access=cls._read_optional_element(cls, element, cls.__SDO_ACCESS_ELEMENT),
            base_flags=SubItemFlags.from_element(element),
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the ObjectFlags instance to a SCI XML element.

        Returns:
            ObjectFlags XML element.
        """
        root = self.base_flags.to_sci()
        if self.transition is not None:
            ElementTree.SubElement(root, self.__TRANSITION_ELEMENT).text = self.transition
        if self.sdo_access is not None:
            ElementTree.SubElement(root, self.__SDO_ACCESS_ELEMENT).text = self.sdo_access
        return root


@dataclass(frozen=True)
class DictionaryObject(XMLParsedElement):
    """Class to represent an object in the profile dictionary."""

    index: str
    overwritten_by_module: Optional[str]
    name: str
    lcid: Optional[str]
    type: str
    bit_size: str
    info: Optional[ObjectInfo]
    flags: Optional[ObjectFlags]

    ELEMENT: str = "Object"
    __INDEX_ELEMENT: str = "Index"
    __OVERWRITTEN_BY_MODULE_ATTR: str = "OverwrittenByModule"
    __NAME_ELEMENT: str = "Name"
    __LCID_ATTR: str = "LcId"
    __TYPE_ELEMENT: str = "Type"
    __BITSIZE_ELEMENT: str = "BitSize"

    @classmethod
    def from_element(cls, element: ElementTree.Element) -> "DictionaryObject":
        """Create a DictionaryObject instance from an XML element.

        Returns:
            class instance created from the XML element.
        """
        index_element = cls._find_and_check(element, cls.__INDEX_ELEMENT)
        name_element = cls._find_and_check(element, cls.__NAME_ELEMENT)
        info_element = cls._find_and_check_optional(element, ObjectInfo.ELEMENT)
        flags_element = cls._find_and_check_optional(element, ObjectFlags.ELEMENT)
        return cls(
            index=index_element.text.strip(),
            overwritten_by_module=index_element.attrib.get(cls.__OVERWRITTEN_BY_MODULE_ATTR, None),
            name=name_element.text.strip(),
            lcid=name_element.attrib.get(cls.__LCID_ATTR, None),
            type=cls._read_element(cls, element, cls.__TYPE_ELEMENT),
            bit_size=cls._read_element(cls, element, cls.__BITSIZE_ELEMENT),
            info=ObjectInfo.from_element(info_element) if info_element is not None else None,
            flags=ObjectFlags.from_element(flags_element) if flags_element is not None else None,
        )

    def to_sci(self) -> ElementTree.Element:
        """Convert the DictionaryObject instance to a SCI XML element.

        Returns:
            DictionaryObject XML element.
        """
        root = ElementTree.Element(self.ELEMENT)
        index_element = ElementTree.SubElement(root, self.__INDEX_ELEMENT)
        index_element.text = self.index
        if self.overwritten_by_module is not None:
            index_element.set(self.__OVERWRITTEN_BY_MODULE_ATTR, self.overwritten_by_module)
        name_element = ElementTree.SubElement(root, self.__NAME_ELEMENT)
        name_element.text = self.name
        if self.lcid is not None:
            name_element.set(self.__LCID_ATTR, self.lcid)
        ElementTree.SubElement(root, self.__TYPE_ELEMENT).text = self.type
        ElementTree.SubElement(root, self.__BITSIZE_ELEMENT).text = self.bit_size
        if self.info is not None:
            root.append(self.info.to_sci())
        if self.flags is not None:
            root.append(self.flags.to_sci())
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
            datatypes_element.append(data_type.to_sci())
        objects_element = ElementTree.SubElement(root, self.__OBJECTS_ELEMENT)
        for obj in self.objects:
            objects_element.append(obj.to_sci())
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

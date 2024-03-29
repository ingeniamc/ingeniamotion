import io
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element
from enum import Enum
from typing import Optional
from xml.dom import minidom
import tempfile

FILE_EXT_DICTIONARY = ".xdf"
DICT_DEVICE_PRODUCT_CODE = "ProductCode"
DICT_DEVICE_PART_NUMBER = "PartNumber"
DICT_DEVICE_PART_NUMBER_COCO = "PartNumberCoco"
DICT_DEVICE_PART_NUMBER_MOCO = "PartNumberMoco"

MOCO_SUBNODE = 1
SUBNODE_ATTRIBUTE = "subnode"
REGISTER_SECTION = "Body/Device/Registers"
DEVICE_SECTION = "Body/Device"
ERRORS_SECTION = "Body/Errors"
IMAGE_SECTION = "DriveImage"


class CORE(Enum):
    """Core type enum"""

    COMMUNICATION_CORE = "Coco"
    MOTION_CORE = "Moco"


def create_comkit_dictionary(
    coco_dict_path: str, moco_dict_path: str, dest_file: Optional[str] = None
) -> str:
    """Create a dictionary for COMKIT by merging a COCO dictionary and a MOCO dictionary.

    Args:
        coco_dict_path : COCO dictionary path.
        moco_dict_path : MOCO dictionary path.
        dest_file: Path to store the COMKIT dictionary. If it's not provided the
            merged dictionary is stored in the temporary system's folder.

    Returns:
        Path to the COMKIT dictionary.

    Raises:
        ValueError: If destination file has a wrong extension.

    """
    if dest_file is None:
        dest_file = tempfile.NamedTemporaryFile(suffix=FILE_EXT_DICTIONARY).name
    elif not dest_file.endswith(FILE_EXT_DICTIONARY):
        raise ValueError(
            f"Destination file {dest_file} needs to have an {FILE_EXT_DICTIONARY} extension."
        )
    moco_tree_root = get_tree_root(moco_dict_path)
    coco_tree_root = get_tree_root(coco_dict_path)
    comkit_tree_root = coco_tree_root
    comkit_tree_root = merge_registers(moco_tree_root, comkit_tree_root)
    comkit_tree_root = merge_images(moco_tree_root, comkit_tree_root)
    comkit_tree_root = merge_errors(moco_tree_root, comkit_tree_root)
    comkit_tree_root = set_attributes(moco_tree_root, comkit_tree_root)
    save_to_file(comkit_tree_root, dest_file)
    return dest_file


def get_tree_root(dict_path: str) -> Element:
    """Get XML root element.

    Args:
        dict_path : dictionary path.

    Returns:
        Root element.

    """
    tree = ET.parse(dict_path)
    return tree.getroot()


def merge_registers(src_root: Element, dest_root: Element) -> Element:
    """Append registers from source tree to destination tree.

    Args:
        src_root: Source tree.
        dest_root: Destination tree.

    Returns:
        Destination tree.

    """
    src_registers = src_root.findall(f"{REGISTER_SECTION}/Register")
    dest_register_section = dest_root.find(REGISTER_SECTION)
    if not isinstance(dest_register_section, Element):
        return dest_root
    for register in src_registers:
        if SUBNODE_ATTRIBUTE in register.attrib and register.attrib[SUBNODE_ATTRIBUTE] == str(
            MOCO_SUBNODE
        ):
            dest_register_section.append(register)
    return dest_root


def merge_errors(src_root: Element, dest_root: Element) -> Element:
    """Append errors from source tree to destination tree.

    Args:
        src_root: Source tree.
        dest_root: Destination tree.

    Returns:
        Destination tree.

    """
    dest_errors = dest_root.findall(f"{ERRORS_SECTION}/Error")
    dest_errors_section = dest_root.find(ERRORS_SECTION)
    if not isinstance(dest_errors_section, Element):
        return dest_root
    dest_errors_ids = [error.attrib["id"] for error in dest_errors]
    src_errors = src_root.findall(f"{ERRORS_SECTION}/Error")
    for error in src_errors:
        if error.attrib["id"] not in dest_errors_ids:
            dest_errors_section.append(error)
    return dest_root


def merge_images(src_root: Element, dest_root: Element) -> Element:
    """Append image from source tree to destination tree.

    Args:
        src_root: Source tree.
        dest_root: Destination tree.

    Returns:
        Destination tree.

    """
    src_drive_image = src_root.find(IMAGE_SECTION)
    if not isinstance(src_drive_image, Element):
        return dest_root
    if src_drive_image is not None:
        src_drive_image.set("type", CORE.MOTION_CORE.value.lower())
    dest_drive_image = dest_root.find(IMAGE_SECTION)
    if dest_drive_image is not None:
        dest_drive_image.set("type", CORE.COMMUNICATION_CORE.value.lower())
    dest_root.append(src_drive_image)
    return dest_root


def set_attributes(src_tree: Element, dest_tree: Element) -> Element:
    """Set COCO and MOCO part numbers and product codes in destination tree.

    Args:
        src_tree: Source tree.
        dest_tree: Destination tree.

    Returns:
        Destination tree.

    """
    create_attribute(DICT_DEVICE_PART_NUMBER, src_tree, dest_tree, CORE.MOTION_CORE)
    create_attribute(DICT_DEVICE_PART_NUMBER, dest_tree, dest_tree, CORE.COMMUNICATION_CORE)
    create_attribute(DICT_DEVICE_PRODUCT_CODE, src_tree, dest_tree, CORE.MOTION_CORE)
    create_attribute(DICT_DEVICE_PRODUCT_CODE, dest_tree, dest_tree, CORE.COMMUNICATION_CORE)
    return dest_tree


def create_attribute(attribute: str, src_root: Element, dest_root: Element, core: CORE) -> None:
    """Create an attribute in the destination tree.

    Args:
        attribute: Name of the attribute.
        src_root: Source tree.
        dest_root: Destination tree.
        core: Type of core attribute.

    """
    src_device_elem = src_root.find(DEVICE_SECTION)
    dst_device_elem = dest_root.find(DEVICE_SECTION)
    if not isinstance(dst_device_elem, Element):
        return
    if src_device_elem is not None and attribute in src_device_elem.attrib:
        dst_device_elem.set(f"{attribute}{core.value}", src_device_elem.attrib[attribute])


def save_to_file(tree_root: Element, dest_path: str) -> None:
    """Save XML tree to file.

    Args:
        tree_root: XML tree.
        dest_path: Destination path.

    """
    xml_str = minidom.parseString(ET.tostring(tree_root)).toprettyxml(
        indent="  ", newl="", encoding="UTF-8"
    )
    merged_file = io.open(dest_path, "wb")
    merged_file.write(xml_str)
    merged_file.close()

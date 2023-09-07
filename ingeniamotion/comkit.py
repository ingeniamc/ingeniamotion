import os
import io
import xml.etree.ElementTree as ET
from typing import Optional
from xml.dom import minidom
from shutil import copyfile
import tempfile

import ntpath

FILE_EXT_DICTIONARY = ".xdf"
DICT_DEVICE_PRODUCT_CODE = "ProductCode"
DICT_DEVICE_PART_NUMBER = "PartNumber"
DICT_DEVICE_PART_NUMBER_COCO = "PartNumberCoco"
DICT_DEVICE_PART_NUMBER_MOCO = "PartNumberMoco"


def create_comkit_dictionary(coco_dict_path: str, moco_dict_path: str, dest_path: Optional[str] = None) -> str:
    """Create a dictionary for COMKIT by merging a COCO dictionary and a MOCO dictionary.

    Args:
        coco_dict_path : COCO dictionary path.
        moco_dict_path : MOCO dictionary path.
        dest_path: Path to store the COMKIT dictionary. If it's not provided the merged
        dictionary is stored in the temporary system's folder.

    Returns:
        Path to the COMKIT dictionary.

    """
    register_section = "Body/Device/Registers"
    register_element = "Body/Device/Registers/Register"
    drive_image_element = "DriveImage"
    device_element = "Body/Device"
    errors_element = "Body/Errors"

    dict_coco_filename, dict_coco_extension = os.path.splitext(coco_dict_path)
    dict_coco_filename = ntpath.basename(dict_coco_filename)

    dict_moco_filename, dict_moco_extension = os.path.splitext(moco_dict_path)
    dict_moco_filename = ntpath.basename(dict_moco_filename)

    if dest_path is None:
        dest_path = f"{tempfile.gettempdir()}/{dict_coco_filename}-{dict_moco_filename}{FILE_EXT_DICTIONARY}"
    else:
        dest_path = f"{dest_path}/{dict_coco_filename}-{dict_moco_filename}{FILE_EXT_DICTIONARY}"

    copyfile(coco_dict_path, dest_path)

    tree_dict_moco = ET.parse(moco_dict_path)
    root_dict_moco = tree_dict_moco.getroot()

    tree_dict_merged = ET.parse(coco_dict_path)
    root_dict_merged = tree_dict_merged.getroot()

    moco_registers = root_dict_moco.findall(register_element)

    merged_dict_registers_section = root_dict_merged.find(register_section)

    for moco_register in moco_registers:
        if "subnode" in moco_register.attrib and moco_register.attrib["subnode"] == "1":
            merged_dict_registers_section.append(moco_register)

    device_moco = root_dict_moco.find(device_element)
    device_coco = root_dict_merged.find(device_element)

    if device_moco is not None and DICT_DEVICE_PART_NUMBER in device_moco.attrib:
        device_coco.set("PartNumberMoco", device_moco.attrib[DICT_DEVICE_PART_NUMBER])

    if device_coco is not None and DICT_DEVICE_PART_NUMBER in device_coco.attrib:
        device_coco.set("PartNumberCoco", device_coco.attrib[DICT_DEVICE_PART_NUMBER])

    if device_moco is not None and DICT_DEVICE_PRODUCT_CODE in device_moco.attrib:
        device_coco.set("ProductCodeMoco", device_moco.attrib[DICT_DEVICE_PRODUCT_CODE])

    if device_coco is not None and DICT_DEVICE_PRODUCT_CODE in device_coco.attrib:
        device_coco.set("ProductCodeCoco", device_coco.attrib[DICT_DEVICE_PRODUCT_CODE])

    drive_image_coco = root_dict_merged.find(drive_image_element)
    if drive_image_coco is not None:
        drive_image_coco.set("type", "coco")

    drive_image_moco = root_dict_moco.find(drive_image_element)
    if drive_image_moco is not None:
        drive_image_moco.set("type", "moco")
        root_dict_merged.append(drive_image_moco)

    errors_moco = root_dict_moco.find(errors_element)
    root_dict_merged.append(errors_moco)

    xmlstr = minidom.parseString(ET.tostring(root_dict_merged)).toprettyxml(
        indent="  ", newl="", encoding="UTF-8"
    )

    merged_file = io.open(dest_path, "wb")
    merged_file.write(xmlstr)
    merged_file.close()

    return dest_path

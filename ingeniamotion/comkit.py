import os
import io
import xml.etree.ElementTree as ET
from xml.dom import minidom
from shutil import copyfile
import tempfile

import ntpath

FILE_EXT_DICTIONARY = ".xdf"
DICT_DEVICE_PRODUCT_CODE = "ProductCode"
DICT_DEVICE_PART_NUMBER = "PartNumber"
DICT_DEVICE_PART_NUMBER_COCO = "PartNumberCoco"
DICT_DEVICE_PART_NUMBER_MOCO = "PartNumberMoco"
COMKIT_PRODUCT_CODE = 52510721


def merge_dictionaries(dict_path_a, dict_path_b):
    """
    Merges a dictionary containing COCO registers with a dictionary that contains MOCO registers.
    """
    register_section = "Body/Device/Registers"
    register_element = "Body/Device/Registers/Register"
    drive_image_element = "DriveImage"
    device_element = "Body/Device"
    errors_element = "Body/Errors"
    dicts = [dict_path_a, dict_path_b]
    for dict_idx, dict_path in enumerate(dicts):
        tree_dict = ET.parse(dict_path)
        root_dict = tree_dict.getroot()
        device_elem = root_dict.find(device_element)
        if (
            DICT_DEVICE_PRODUCT_CODE in device_elem.attrib
            and int(device_elem.attrib[DICT_DEVICE_PRODUCT_CODE]) == COMKIT_PRODUCT_CODE
        ):
            dict_coco_path = dict_path
            dict_moco_path = dicts[abs(dict_idx - 1)]
            break

    dict_coco_filename, dict_coco_extension = os.path.splitext(dict_coco_path)
    dict_coco_filename = ntpath.basename(dict_coco_filename)

    dict_moco_filename, dict_moco_extension = os.path.splitext(dict_moco_path)
    dict_moco_filename = ntpath.basename(dict_moco_filename)

    merged_dict_path = f"{tempfile.gettempdir()}/{dict_coco_filename}-{dict_moco_filename}{FILE_EXT_DICTIONARY}"

    copyfile(dict_coco_path, merged_dict_path)

    tree_dict_moco = ET.parse(dict_moco_path)
    root_dict_moco = tree_dict_moco.getroot()

    tree_dict_merged = ET.parse(dict_coco_path)
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

    merged_file = io.open(merged_dict_path, "wb")
    merged_file.write(xmlstr)
    merged_file.close()

    return merged_dict_path

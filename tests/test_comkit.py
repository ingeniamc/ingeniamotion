import os.path
from os import remove
import xml.etree.ElementTree as ET
from xml.dom import minidom

import pytest

from ingeniamotion.comkit import (
    create_comkit_dictionary,
    get_tree_root,
    merge_registers,
    merge_errors,
    merge_images,
    create_attribute,
    save_to_file,
    REGISTER_SECTION,
    ERRORS_SECTION,
    IMAGE_SECTION,
    DEVICE_SECTION,
    DICT_DEVICE_PART_NUMBER,
    CORE,
)


@pytest.mark.smoke
def test_create_comkit_dictionary():
    coco_path = "./tests/resources/com-kit.xdf"
    moco_path = "./tests/resources//core.xdf"
    reference_dict = "./tests/resources/com-kit-core.xdf"
    comkit_dict = create_comkit_dictionary(coco_path, moco_path)
    comkit_root = get_tree_root(comkit_dict)
    reference_root = get_tree_root(reference_dict)
    comkit_xml_str = minidom.parseString(ET.tostring(comkit_root)).toprettyxml(
        indent="  ", newl="", encoding="UTF-8"
    )
    reference_xml_str = minidom.parseString(ET.tostring(reference_root)).toprettyxml(
        indent="  ", newl="", encoding="UTF-8"
    )
    assert comkit_xml_str == reference_xml_str


@pytest.mark.smoke
def test_create_comkit_dictionary_wrong_file_extension():
    coco_path = "./tests/resources/com-kit.xdf"
    moco_path = "./tests/resources//core.xdf"
    dest_path = "com-kit-core.txt"
    with pytest.raises(ValueError):
        create_comkit_dictionary(coco_path, moco_path, dest_path)


@pytest.mark.parametrize(
    "element, merge_function",
    [
        (f"{REGISTER_SECTION}/Register", merge_registers),
        (f"{ERRORS_SECTION}/Error", merge_errors),
        (IMAGE_SECTION, merge_images),
    ],
)
@pytest.mark.smoke
@pytest.mark.virtual
def test_merge_elements(element, merge_function):
    coco_path = "./tests/resources/com-kit.xdf"
    moco_path = "./tests/resources/core.xdf"
    src_root = get_tree_root(moco_path)
    dst_root = get_tree_root(coco_path)
    src_elems = src_root.findall(element)
    dst_elems = dst_root.findall(element)
    merged_root = merge_function(src_root, dst_root)
    merged_root_elems = merged_root.findall(element)
    assert len(merged_root_elems) == len(src_elems) + len(dst_elems)


@pytest.mark.parametrize(
    "core_type",
    [
        CORE.MOTION_CORE,
        CORE.COMMUNICATION_CORE,
    ],
)
@pytest.mark.smoke
@pytest.mark.virtual
def test_create_attribute(core_type):
    coco_path = "./tests/resources/com-kit.xdf"
    moco_path = "./tests/resources/core.xdf"
    src_root = get_tree_root(moco_path)
    dst_root = get_tree_root(coco_path)
    create_attribute(DICT_DEVICE_PART_NUMBER, src_root, dst_root, core_type)
    device_elem = dst_root.find(DEVICE_SECTION)
    assert DICT_DEVICE_PART_NUMBER + core_type.value in device_elem.attrib


@pytest.mark.smoke
@pytest.mark.virtual
def test_save_file():
    coco_path = "./tests/resources/com-kit.xdf"
    dest_path = "temp.xdf"
    src_root = get_tree_root(coco_path)
    assert not os.path.exists(dest_path)
    save_to_file(src_root, dest_path)
    assert os.path.exists(dest_path)
    remove(dest_path)

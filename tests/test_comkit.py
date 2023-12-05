import xml.etree.ElementTree as ET
from xml.dom import minidom

import pytest

from ingeniamotion.comkit import create_comkit_dictionary, get_tree_root


@pytest.mark.virtual
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


@pytest.mark.virtual
@pytest.mark.smoke
def test_create_comkit_dictionary_wrong_file_extension():
    coco_path = "./tests/resources/com-kit.xdf"
    moco_path = "./tests/resources//core.xdf"
    dest_path = "com-kit-core.txt"
    with pytest.raises(ValueError):
        create_comkit_dictionary(coco_path, moco_path, dest_path)

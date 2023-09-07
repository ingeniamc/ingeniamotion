import pytest

from ingeniamotion.comkit import create_comkit_dictionary, get_tree_root


@pytest.mark.smoke
def test_create_comkit_dictionary():
    coco_path = "test//resources//com-kit.xdf"
    moco_path = "test//resources//core.xdf"
    reference_dict = "test//resources//com-kit-core.xdf"
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

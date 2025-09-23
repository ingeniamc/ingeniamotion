from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from ingenialink import RegAccess, RegDtype
from ingenialink.dictionary import Interface
from ingenialink.enums.register import RegCyclicType
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.servo import DictionaryFactory
from pytest_mock import MockerFixture

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController
from tests.dictionaries import SAMPLE_SAFE_PH2_XDFV3_DICTIONARY

if TYPE_CHECKING:
    from ingenialink.ethercat.dictionary import EthercatDictionary

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import ProcessImage
    from ingeniamotion.fsoe_master.frame import FSoEFrame
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
    from ingeniamotion.fsoe_master.maps_validator import (
        FSoEFrameConstructionError,
        FSoEFrameRules,
        InvalidFSoEFrameRule,
    )
    from ingeniamotion.fsoe_master.safety_functions import (
        SS1Function,
        STOFunction,
    )

    if TYPE_CHECKING:
        from ingeniamotion.fsoe import FSoEDictionary
        from tests.fsoe.utils.map_generator import FSoERandomMappingGenerator


@pytest.mark.fsoe
def test_validate_safe_data_blocks_invalid_size(
    mocker: MockerFixture, fsoe_dict: "FSoEDictionary"
) -> None:
    """Test that SafeDataBlocksValidator fails when safe data blocks are not 16 bits."""
    maps = ProcessImage.empty(fsoe_dict)

    # Create a map with safe data blocks that are not 16 bits
    test_st_u8_item = maps.inputs.add(fsoe_dict.name_map["TEST_SI_U8"])  # 8 bits

    # Use a dummy slot width to simulate that the safe data block is wrongly sized
    dummy_slot_width = 2

    mocker.patch.object(FSoEFrame, "_FSoEFrame__SLOT_WIDTH", dummy_slot_width)
    # Only validate the safe data blocks rule
    output = maps.are_inputs_valid(rules=[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID])
    assert len(output.exceptions) == 1
    assert FSoEFrameRules.SAFE_DATA_BLOCKS_VALID in output.exceptions
    exception = output.exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID]
    assert isinstance(exception, InvalidFSoEFrameRule)
    assert f"Safe data block 0 must be 16 bits. Found {dummy_slot_width}" in exception.exception
    assert exception.items == [test_st_u8_item]
    assert output.is_rule_valid(FSoEFrameRules.SAFE_DATA_BLOCKS_VALID) is False


@pytest.mark.fsoe
def test_validate_safe_data_blocks_pdu_empty(fsoe_dict: "FSoEDictionary") -> None:
    """Test that SafeDataBlocksValidator passes when no safe data blocks are present."""
    maps = ProcessImage.empty(fsoe_dict)
    output = maps.are_inputs_valid(rules=[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID])
    assert len(output.exceptions) == 0
    assert output.is_rule_valid(FSoEFrameRules.SAFE_DATA_BLOCKS_VALID) is True


@pytest.mark.fsoe
def test_validate_safe_data_blocks_too_many_blocks() -> None:
    """Test that SafeDataBlocksValidator fails when there are more than 8 safe data blocks."""
    # Add 9 different 16-bit safe inputs -> 9 blocks
    safe_dict = DictionaryFactory.create_dictionary(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, interface=Interface.ECAT
    )
    for idx in range(9):
        test_uid = f"TEST_SI_U16_{idx}"
        safe_dict._registers[1][test_uid] = EthercatRegister(
            idx=0xF010 + idx,
            subidx=0,
            dtype=RegDtype.U16,
            access=RegAccess.RO,
            identifier=test_uid,
            pdo_access=RegCyclicType.SAFETY_INPUT,
            cat_id="FSOE",
        )
    # Check the CRCs that are already present in the sample dictionary and add the missing ones
    existing_crcs = [
        key for key in safe_dict._registers[1] if key.startswith("FSOE_SLAVE_FRAME_ELEM_CRC")
    ]
    added_crc = 0
    for idx in range(9):
        crc_uid = f"FSOE_SLAVE_FRAME_ELEM_CRC{idx}"
        if crc_uid in existing_crcs:
            continue
        safe_dict._registers[1][crc_uid] = EthercatRegister(
            idx=0x6760,
            subidx=len(existing_crcs) + added_crc,
            dtype=RegDtype.U16,
            access=RegAccess.RO,
            identifier=crc_uid,
            pdo_access=RegCyclicType.SAFETY_INPUT,
            cat_id="FSOE",
        )
        added_crc += 1
    # Create safe dictionary
    fsoe_dict = FSoEMasterHandler.create_safe_dictionary(safe_dict)

    maps = ProcessImage.empty(fsoe_dict)

    test_si_u16_items = []
    for idx in range(9):
        test_uid = f"TEST_SI_U16_{idx}"
        item = maps.inputs.add(fsoe_dict.name_map[test_uid])
        test_si_u16_items.append(item)

    output = maps.are_inputs_valid(rules=[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID])
    assert len(output.exceptions) == 1
    assert FSoEFrameRules.SAFE_DATA_BLOCKS_VALID in output.exceptions
    exception = output.exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID]
    assert isinstance(exception, InvalidFSoEFrameRule)
    assert "Expected 1-8 safe data blocks, found 9" in exception.exception
    assert exception.items == test_si_u16_items
    assert output.is_rule_valid(FSoEFrameRules.SAFE_DATA_BLOCKS_VALID) is False


@pytest.mark.fsoe
def test_validate_safe_data_blocks_objects_split_across_blocks(fsoe_dict: "FSoEDictionary") -> None:
    """Test that SafeDataBlocksValidator fails when <= 16 bits objects are split."""
    maps = ProcessImage.empty(fsoe_dict)

    maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
    maps.inputs.add_padding(bits=6)
    maps.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
    maps.inputs.add(fsoe_dict.name_map["FSOE_SS2_1"])
    test_si_u8_item = maps.inputs.add(fsoe_dict.name_map["TEST_SI_U8"])

    # Test that rule fails because the 8-bit object is split across blocks
    output = maps.are_inputs_valid(rules=[FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED])
    assert len(output.exceptions) == 1
    assert FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED in output.exceptions
    exception = output.exceptions[FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED]
    assert isinstance(exception, InvalidFSoEFrameRule)
    assert exception.exception == (
        "Make sure that 8 bit objects belong to the same data block. "
        f"Data slot 0 contains split object {test_si_u8_item.item.name}."
    )
    assert exception.items == [test_si_u8_item]  # Split item
    assert output.is_rule_valid(FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED) is False

    # Test that rule passes when the object is not split
    maps.inputs.clear()
    maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
    maps.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
    maps.inputs.add(fsoe_dict.name_map["FSOE_SS2_1"])
    maps.inputs.add(fsoe_dict.name_map["TEST_SI_U8"])
    output = maps.are_inputs_valid(rules=[FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED])
    assert not output.exceptions
    assert output.is_rule_valid(FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED) is True


@pytest.mark.fsoe
def test_validate_safe_data_blocks_valid_cases(fsoe_dict: "FSoEDictionary") -> None:
    """Test that SafeDataBlocksValidator passes for valid safe data block configurations."""
    for items_to_add in [
        ["TEST_SI_U8"],  # single 8-bit block
        ["TEST_SI_U16"],  # single 16-bit block
        ["TEST_SI_U16", "FSOE_SAFE_POSITION"],  # multiple 16-bit blocks
    ]:
        maps = ProcessImage.empty(fsoe_dict)
        for item_uid in items_to_add:
            maps.inputs.add(fsoe_dict.name_map[item_uid])

        output = maps.are_inputs_valid(rules=[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID])
        assert FSoEFrameRules.SAFE_DATA_BLOCKS_VALID not in output.exceptions
        assert output.is_rule_valid(FSoEFrameRules.SAFE_DATA_BLOCKS_VALID) is True


@pytest.mark.fsoe
def test_validate_number_of_objects_in_frame(
    safe_dict: "EthercatDictionary", fsoe_dict: "FSoEDictionary"
) -> None:
    """Test that SafeDataBlocksValidator fails if the number of objects is exceeded."""

    for idx in range(45):
        test_uid = f"TEST_SI_BOOL_{idx}"
        safe_dict._registers[1][test_uid] = EthercatRegister(
            idx=0xF010 + idx,
            subidx=0,
            dtype=RegDtype.BOOL,
            access=RegAccess.RO,
            identifier=test_uid,
            pdo_access=RegCyclicType.SAFETY_INPUT,
            cat_id="FSOE",
        )
    # Check the CRCs that are already present in the sample dictionary and add the missing ones
    existing_crcs = [
        key for key in safe_dict._registers[1] if key.startswith("FSOE_SLAVE_FRAME_ELEM_CRC")
    ]
    added_crc = 0
    for idx in range(45):
        crc_uid = f"FSOE_SLAVE_FRAME_ELEM_CRC{idx}"
        if crc_uid in existing_crcs:
            continue
        safe_dict._registers[1][crc_uid] = EthercatRegister(
            idx=0x6760,
            subidx=len(existing_crcs) + added_crc,
            dtype=RegDtype.U16,
            access=RegAccess.RO,
            identifier=crc_uid,
            pdo_access=RegCyclicType.SAFETY_INPUT,
            cat_id="FSOE",
        )
        added_crc += 1
    # Create safe dictionary
    fsoe_dict = FSoEMasterHandler.create_safe_dictionary(safe_dict)

    maps = ProcessImage.empty(fsoe_dict)

    test_si_bool_items = []
    for idx in range(45):
        test_uid = f"TEST_SI_BOOL_{idx}"
        item = maps.inputs.add(fsoe_dict.name_map[test_uid])
        test_si_bool_items.append(item)

    # Expected data blocks
    # CMD + DATA BLOCKS + CRC + CONNID
    data_blocks = FSoEFrame.generate_slot_structure(
        dict_map=maps.inputs, slot_width=FSoEFrame._FSoEFrame__SLOT_WIDTH
    )
    expected_crcs = len(list(data_blocks))
    n_objects = 1 + len(maps.inputs) + expected_crcs + 1

    output = maps.are_inputs_valid(
        rules=[FSoEFrameRules.OBJECTS_IN_FRAME, FSoEFrameRules.SAFE_DATA_BLOCKS_VALID]
    )
    assert len(output.exceptions) == 1
    assert FSoEFrameRules.SAFE_DATA_BLOCKS_VALID not in output.exceptions
    assert FSoEFrameRules.OBJECTS_IN_FRAME in output.exceptions
    exception = output.exceptions[FSoEFrameRules.OBJECTS_IN_FRAME]
    assert isinstance(exception, InvalidFSoEFrameRule)
    assert exception.exception == (f"Total objects in frame exceeds limit: {n_objects} > 45")
    assert exception.items == test_si_bool_items
    assert output.is_rule_valid(FSoEFrameRules.OBJECTS_IN_FRAME) is False


@pytest.mark.fsoe
def test_validate_safe_data_objects_word_aligned(fsoe_dict: "FSoEDictionary") -> None:
    """Test that validation fails when safe data objects >= 16 bits are not word aligned."""
    process_image = ProcessImage.empty(fsoe_dict)

    process_image.inputs.add(fsoe_dict.name_map["TEST_SI_U8"])
    test_si_u16_item = process_image.inputs.add(fsoe_dict.name_map["TEST_SI_U16"])

    output = process_image.are_inputs_valid(rules=[FSoEFrameRules.OBJECTS_ALIGNED])
    assert len(output.exceptions) == 1
    assert FSoEFrameRules.OBJECTS_ALIGNED in output.exceptions
    exception = output.exceptions[FSoEFrameRules.OBJECTS_ALIGNED]
    assert isinstance(exception, InvalidFSoEFrameRule)
    assert exception.exception == (
        "Objects larger than 16-bit must be word-aligned. "
        f"Object '{test_si_u16_item.item.name}' found at position 8, "
        f"next alignment is at 16."
    )
    assert exception.items == [test_si_u16_item]
    assert output.is_rule_valid(FSoEFrameRules.OBJECTS_ALIGNED) is False

    # Check that the rule passes when the object is word-aligned
    process_image.inputs.clear()
    process_image.inputs.add(fsoe_dict.name_map["TEST_SI_U8"])
    process_image.inputs.add_padding(bits=8)
    process_image.inputs.add(fsoe_dict.name_map["TEST_SI_U16"])
    output = process_image.are_inputs_valid(rules=[FSoEFrameRules.OBJECTS_ALIGNED])
    assert not output.exceptions
    assert output.is_rule_valid(FSoEFrameRules.OBJECTS_ALIGNED) is True


@pytest.mark.fsoe
def test_validate_sto_command_first_in_outputs(fsoe_dict: "FSoEDictionary") -> None:
    """Test that STO command is the first item in the maps."""
    process_image = ProcessImage.empty(fsoe_dict)
    ss1_item_outputs = process_image.outputs.add(
        fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)]
    )
    process_image.outputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
    # STO command can be anywhere in the inputs map
    ss1_item_inputs = process_image.inputs.add(
        fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)]
    )
    process_image.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])

    output = process_image.are_outputs_valid(rules=[FSoEFrameRules.STO_COMMAND_FIRST])
    assert len(output.exceptions) == 1
    assert FSoEFrameRules.STO_COMMAND_FIRST in output.exceptions
    exception = output.exceptions[FSoEFrameRules.STO_COMMAND_FIRST]
    assert isinstance(exception, InvalidFSoEFrameRule)
    assert "STO command must be mapped to the first position" in exception.exception
    assert exception.items == [ss1_item_outputs]
    assert output.is_rule_valid(FSoEFrameRules.STO_COMMAND_FIRST) is False

    output = process_image.are_inputs_valid(rules=[FSoEFrameRules.STO_COMMAND_FIRST])
    assert len(output.exceptions) == 1
    assert FSoEFrameRules.STO_COMMAND_FIRST in output.exceptions
    exception = output.exceptions[FSoEFrameRules.STO_COMMAND_FIRST]
    assert isinstance(exception, InvalidFSoEFrameRule)
    assert "STO command must be mapped to the first position" in exception.exception
    assert exception.items == [ss1_item_inputs]
    assert output.is_rule_valid(FSoEFrameRules.STO_COMMAND_FIRST) is False

    process_image.outputs.clear()
    process_image.outputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
    process_image.outputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
    output = process_image.are_outputs_valid(rules=[FSoEFrameRules.STO_COMMAND_FIRST])
    assert not output.exceptions
    assert output.is_rule_valid(FSoEFrameRules.STO_COMMAND_FIRST) is True

    process_image.inputs.clear()
    process_image.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
    process_image.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
    output = process_image.are_inputs_valid(rules=[FSoEFrameRules.STO_COMMAND_FIRST])
    assert not output.exceptions
    assert output.is_rule_valid(FSoEFrameRules.STO_COMMAND_FIRST) is True


@pytest.mark.fsoe
def test_validate_empty_map(fsoe_dict: "FSoEDictionary") -> None:
    """Test that an empty FSoE map is invalid."""
    process_image = ProcessImage.empty(fsoe_dict)
    output = process_image.are_outputs_valid()
    assert FSoEFrameRules.STO_COMMAND_FIRST in output.exceptions
    output = process_image.are_inputs_valid()
    assert FSoEFrameRules.STO_COMMAND_FIRST in output.exceptions


@pytest.mark.fsoe
def test_validate_dictionary_map_fsoe_frame_rules(fsoe_dict: "FSoEDictionary") -> None:
    """Test that FSoE frames pass all validation rules."""
    process_image = ProcessImage.empty(fsoe_dict)
    process_image.outputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
    process_image.outputs.add_padding(7)
    process_image.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
    process_image.inputs.add_padding(7)

    is_valid = process_image.validate()
    assert is_valid is True


@pytest.mark.fsoe_phase2
@pytest.mark.parametrize("iteration", range(100))  # Run 100 times
def test_random_map_validation(
    mc_with_fsoe_with_sra: tuple[MotionController, "FSoEMasterHandler"],
    map_generator: "FSoERandomMappingGenerator",
    fsoe_maps_dir: Path,
    random_seed: int,
    random_max_items: int,
    random_paddings: bool,
    iteration: int,  # noqa: ARG001
) -> None:
    _, handler = mc_with_fsoe_with_sra

    mapping_file = (
        fsoe_maps_dir / f"mapping_{random_max_items}_{random_paddings}_{random_seed}.json"
    )

    maps = map_generator.generate_and_save_random_mapping(
        dictionary=handler.dictionary,
        max_items=random_max_items,
        random_paddings=random_paddings,
        seed=random_seed,
        filename=mapping_file,
        override=False,
    )
    assert mapping_file.exists()

    # If the mapping is invalid, the mapping file will be kept for posterior analysis
    try:
        maps.validate()
        mapping_file.unlink()
        assert not mapping_file.exists()
    except FSoEFrameConstructionError as e:
        pytest.fail(f"Map validation failed with error: {e}. ")

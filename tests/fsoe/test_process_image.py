import time
import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import pytest
from ingenialink import RegAccess
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.pdo import RPDOMap, TPDOMap

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEError
from ingeniamotion.motion_controller import MotionController
from tests.dictionaries import SAMPLE_SAFE_PH1_XDFV3_DICTIONARY, SAMPLE_SAFE_PH2_XDFV3_DICTIONARY
from tests.fsoe.conftest import MockNetwork, MockServo

try:
    import pysoem
except ImportError:
    pysoem = None


if FSOE_MASTER_INSTALLED:
    from fsoe_master import fsoe_master

    import ingeniamotion.fsoe_master.safety_functions as safety_functions
    from ingeniamotion.fsoe_master import ProcessImage
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
    from ingeniamotion.fsoe_master.safety_functions import (
        SafeInputsFunction,
        SafetyFunction,
        SS1Function,
        SSRFunction,
        STOFunction,
    )
    from tests.fsoe.conftest import MockHandler
    from tests.fsoe.utils.map_json_serializer import FSoEDictionaryMapJSONSerializer

if TYPE_CHECKING:
    from ingenialink.ethercat.dictionary import EthercatDictionary
    from ingenialink.ethercat.servo import EthercatServo

    from ingeniamotion.fsoe import FSoEDictionary

    if FSOE_MASTER_INSTALLED:
        from ingeniamotion.fsoe_master.errors import (
            ServoErrorQueue,
        )
        from tests.fsoe.conftest import FSoERandomMappingGenerator


@pytest.mark.fsoe
@pytest.mark.parametrize(
    "dictionary, editable",
    [(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY, False), (SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, True)],
)
def test_mapping_locked(
    dictionary: str, editable: bool, fsoe_error_monitor: Callable[[FSoEError], None]
) -> None:
    mock_servo = MockServo(dictionary)

    if not editable:
        # First xdf v3 and esi files of phase 1 had the PDOs set to RW as a mistake
        # for XDF V2, the hard-coded pdo maps are created with RO access
        for obj in [
            mock_servo.dictionary.get_object("ETG_COMMS_RPDO_MAP256", 1),
            mock_servo.dictionary.get_object("ETG_COMMS_TPDO_MAP256", 1),
        ]:
            for reg in obj.registers:
                reg._access = RegAccess.RO

    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            report_error_callback=fsoe_error_monitor,
        )
        assert handler.process_image.editable is editable

        if editable:
            handler.process_image.inputs.clear()
        else:
            with pytest.raises(fsoe_master.FSOEMasterMappingLockedException):
                handler.process_image.inputs.clear()

        new_pi = handler.process_image.copy()
        assert new_pi.editable is editable

        if editable:
            new_pi.outputs.clear()
        else:
            with pytest.raises(fsoe_master.FSOEMasterMappingLockedException):
                new_pi.outputs.clear()

    finally:
        handler.delete()


@pytest.mark.fsoe
def test_copy_modify_and_set_map(
    mc_with_fsoe: tuple["MotionController", "FSoEMasterHandler"],
) -> None:
    _, handler = mc_with_fsoe

    # Obtain one safety input
    si = handler.safe_inputs_function().value

    # Create a copy of the map
    new_pi = handler.process_image.copy()

    # The new map can be modified
    new_pi.inputs.remove(si)
    assert new_pi.inputs.get_text_representation() == (
        "Item                                     | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                                 | 0..0                 | 0..1                \n"
        "FSOE_SS1_1                               | 0..1                 | 0..1                \n"
        "Padding                                  | 0..2                 | 0..6                \n"
        "Padding                                  | 1..0                 | 0..7                "
    )

    # Without affecting the original map of the handler
    assert handler.process_image.inputs.get_text_representation() == (
        "Item                                     | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                                 | 0..0                 | 0..1                \n"
        "FSOE_SS1_1                               | 0..1                 | 0..1                \n"
        "Padding                                  | 0..2                 | 0..6                \n"
        "FSOE_SAFE_INPUTS_VALUE                   | 1..0                 | 0..1                \n"
        "Padding                                  | 1..1                 | 0..7                "
    )

    # The new map can be set to the handler
    handler.set_process_image(new_pi)

    # And is set to the backend of the real master
    assert handler._master_handler.master.dictionary_map == new_pi.outputs
    assert handler._master_handler.slave.dictionary_map == new_pi.inputs


@pytest.mark.fsoe_phase2
def test_maps_different_length(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    alias: str,
    timeout_for_data_sra: float,
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    sto = handler.get_function_instance(STOFunction)
    safe_inputs = handler.get_function_instance(SafeInputsFunction)
    ss1 = handler.get_function_instance(SS1Function)

    handler.process_image.inputs.clear()
    handler.process_image.inputs.add(sto.command)
    handler.process_image.inputs.add(ss1.command)
    handler.process_image.inputs.add_padding(6)
    handler.process_image.inputs.add(safe_inputs.value)
    handler.process_image.inputs.add_padding(7)

    handler.process_image.outputs.clear()
    handler.process_image.outputs.add(sto.command)
    handler.process_image.outputs.add(ss1.command)
    handler.process_image.outputs.add_padding(6)

    assert handler.process_image.inputs.safety_bits == 16
    assert handler.process_image.outputs.safety_bits == 8

    # Configure the FSoE master handler
    mc.fsoe.configure_pdos(start_pdos=False)

    # Inputs: 1 byte command + 2 bytes safety data + 2 bytes CRC + 2 bytes connection ID
    # 7 bytes -> 56 bits
    assert handler.safety_slave_pdu_map.data_length_bits == 56
    # Outputs: 1 byte command + 1 bytes safety data + 2 bytes CRC + 2 bytes connection ID
    # 6 bytes -> 48 bits
    assert handler.safety_master_pdu_map.data_length_bits == 48

    mc.fsoe.start_master()
    mc.capture.pdo.start_pdos(servo=alias)
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    assert handler.state == FSoEState.DATA
    # Check that it stays in Data state
    for i in range(2):
        time.sleep(1)
    assert handler.state == FSoEState.DATA

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
def test_map_phase_1(
    safe_dict: tuple["EthercatDictionary", "FSoEDictionary"], fsoe_dict: "FSoEDictionary"
) -> None:
    maps = ProcessImage.empty(fsoe_dict)

    maps.outputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
    maps.outputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
    maps.outputs.add_padding(bits=6 + 8)

    maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
    maps.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
    maps.inputs.add_padding(bits=6)
    maps.inputs.add(fsoe_dict.name_map[SafeInputsFunction.SAFE_INPUTS_UID])
    maps.inputs.add_padding(bits=7)

    rpdo = RPDOMap()
    # Registers that are present in the map,
    # are cleared when the map is filled
    rpdo.add_registers(safe_dict.get_register("DRV_OP_CMD"))
    maps.fill_rpdo_map(rpdo, safe_dict)

    assert rpdo.items[0].register.identifier == "FSOE_MASTER_FRAME_ELEM_CMD"
    assert rpdo.items[0].register.idx == 0x6770
    assert rpdo.items[0].register.subidx == 0x01
    assert rpdo.items[0].size_bits == 8

    assert rpdo.items[1].register.identifier == "FSOE_STO"
    assert rpdo.items[1].register.idx == 0x6640
    assert rpdo.items[1].register.subidx == 0x0
    assert rpdo.items[1].size_bits == 1

    assert rpdo.items[2].register.identifier == "FSOE_SS1_1"
    assert rpdo.items[2].register.idx == 0x6650
    assert rpdo.items[2].register.subidx == 0x1
    assert rpdo.items[2].size_bits == 1

    assert rpdo.items[3].register.identifier == "PADDING"
    assert rpdo.items[3].register.idx == 0
    assert rpdo.items[3].register.subidx == 0
    assert rpdo.items[3].size_bits == 14

    assert rpdo.items[4].register.identifier == "FSOE_MASTER_FRAME_ELEM_CRC0"
    assert rpdo.items[4].register.idx == 0x6770
    assert rpdo.items[4].register.subidx == 0x03
    assert rpdo.items[4].size_bits == 16

    assert rpdo.items[5].register.identifier == "FSOE_MASTER_FRAME_ELEM_CONNID"
    assert rpdo.items[5].register.idx == 0x6770
    assert rpdo.items[5].register.subidx == 0x02
    assert rpdo.items[5].size_bits == 16

    assert len(rpdo.items) == 6

    tpdo = TPDOMap()
    maps.fill_tpdo_map(tpdo, safe_dict)

    assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
    assert tpdo.items[0].register.idx == 0x6760
    assert tpdo.items[0].register.subidx == 0x01
    assert tpdo.items[0].size_bits == 8

    assert tpdo.items[1].register.identifier == "FSOE_STO"
    assert tpdo.items[1].register.idx == 0x6640
    assert tpdo.items[1].register.subidx == 0x0
    assert tpdo.items[1].size_bits == 1

    assert tpdo.items[2].register.identifier == "FSOE_SS1_1"
    assert tpdo.items[2].register.idx == 0x6650
    assert tpdo.items[2].register.subidx == 0x1
    assert tpdo.items[2].size_bits == 1

    assert tpdo.items[3].register.identifier == "PADDING"
    assert tpdo.items[3].register.idx == 0
    assert tpdo.items[3].register.subidx == 0
    assert tpdo.items[3].size_bits == 6

    assert tpdo.items[4].register.identifier == "FSOE_SAFE_INPUTS_VALUE"
    assert tpdo.items[4].register.idx == 0x46D1
    assert tpdo.items[4].register.subidx == 0x0
    assert tpdo.items[4].size_bits == 1

    assert tpdo.items[5].register.identifier == "PADDING"
    assert tpdo.items[5].register.idx == 0
    assert tpdo.items[5].register.subidx == 0
    assert tpdo.items[5].size_bits == 7

    assert tpdo.items[6].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
    assert tpdo.items[6].register.idx == 0x6760
    assert tpdo.items[6].register.subidx == 0x03
    assert tpdo.items[6].size_bits == 16

    assert tpdo.items[7].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
    assert tpdo.items[7].register.idx == 0x6760
    assert tpdo.items[7].register.subidx == 0x02
    assert tpdo.items[7].size_bits == 16

    assert len(tpdo.items) == 8

    recreated_pdu_maps = ProcessImage.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
    assert (
        recreated_pdu_maps.outputs.get_text_representation()
        == maps.outputs.get_text_representation()
    )
    assert (
        recreated_pdu_maps.inputs.get_text_representation() == maps.inputs.get_text_representation()
    )


@pytest.mark.fsoe
def test_map_8_safe_bits(
    safe_dict: tuple["EthercatDictionary", "FSoEDictionary"], fsoe_dict: "FSoEDictionary"
) -> None:
    maps = ProcessImage.empty(fsoe_dict)

    maps.inputs.add(fsoe_dict.name_map["TEST_SI_U8"])

    # Create the rpdo map
    tpdo = TPDOMap()
    maps.fill_tpdo_map(tpdo, safe_dict)

    assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
    assert tpdo.items[0].size_bits == 8

    assert tpdo.items[1].register.identifier == "TEST_SI_U8"
    assert tpdo.items[1].size_bits == 8

    assert tpdo.items[2].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
    assert tpdo.items[2].size_bits == 16

    assert tpdo.items[3].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
    assert tpdo.items[3].size_bits == 16

    assert len(tpdo.items) == 4

    rpdo = RPDOMap()
    maps.fill_rpdo_map(rpdo, safe_dict)

    recreated_pdu_maps = ProcessImage.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
    assert (
        recreated_pdu_maps.outputs.get_text_representation()
        == maps.outputs.get_text_representation()
    )
    assert (
        recreated_pdu_maps.inputs.get_text_representation() == maps.inputs.get_text_representation()
    )


@pytest.mark.fsoe
def test_empty_map_8_bits(
    safe_dict: tuple["EthercatDictionary", "FSoEDictionary"], fsoe_dict: "FSoEDictionary"
) -> None:
    maps = ProcessImage.empty(fsoe_dict)
    tpdo = TPDOMap()
    maps.fill_tpdo_map(tpdo, safe_dict)

    assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
    assert tpdo.items[0].size_bits == 8

    assert tpdo.items[1].register.identifier == "PADDING"
    assert tpdo.items[1].size_bits == 8

    assert tpdo.items[2].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
    assert tpdo.items[2].size_bits == 16

    assert tpdo.items[3].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
    assert tpdo.items[3].size_bits == 16

    assert len(tpdo.items) == 4


@pytest.mark.fsoe
def test_map_with_32_bit_vars(
    safe_dict: tuple["EthercatDictionary", "FSoEDictionary"], fsoe_dict: "FSoEDictionary"
) -> None:
    maps = ProcessImage.empty(fsoe_dict)

    # Append a 32-bit variable
    maps.inputs.add(fsoe_dict.name_map["FSOE_SAFE_POSITION"])

    # Create the rpdo map
    tpdo = TPDOMap()
    maps.fill_tpdo_map(tpdo, safe_dict)

    assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
    assert tpdo.items[0].size_bits == 8

    assert tpdo.items[1].register.identifier == "FSOE_SAFE_POSITION"
    assert tpdo.items[1].size_bits == 16

    assert tpdo.items[2].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
    assert tpdo.items[2].size_bits == 16

    # On this padding, the 32-bit variable will continue to be transmitted
    assert tpdo.items[3].register.identifier == "PADDING"
    assert tpdo.items[3].size_bits == 16

    assert tpdo.items[4].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC1"
    assert tpdo.items[4].size_bits == 16

    assert tpdo.items[5].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
    assert tpdo.items[5].size_bits == 16

    assert len(tpdo.items) == 6

    rpdo = RPDOMap()
    maps.fill_rpdo_map(rpdo, safe_dict)

    recreated_pdu_maps = ProcessImage.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
    assert (
        recreated_pdu_maps.outputs.get_text_representation()
        == maps.outputs.get_text_representation()
    )
    assert (
        recreated_pdu_maps.inputs.get_text_representation() == maps.inputs.get_text_representation()
    )


@pytest.mark.fsoe
def test_map_with_32_bit_vars_offset_8(
    safe_dict: tuple["EthercatDictionary", "FSoEDictionary"], fsoe_dict: "FSoEDictionary"
) -> None:
    maps = ProcessImage.empty(fsoe_dict)

    # Add a first 8-bit variable that will shift the 32-bit variable
    maps.inputs.add(fsoe_dict.name_map["TEST_SI_U8"])
    # Append a 32-bit variable
    maps.inputs.add(fsoe_dict.name_map["FSOE_SAFE_POSITION"])
    maps.inputs.add_padding(bits=8)

    # Create the rpdo map
    tpdo = TPDOMap()
    maps.fill_tpdo_map(tpdo, safe_dict)

    assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
    assert tpdo.items[0].size_bits == 8

    assert tpdo.items[1].register.identifier == "TEST_SI_U8"
    assert tpdo.items[1].size_bits == 8

    # Variable cut to what fills on the slot (8 bits of 32 bits, 24 remaining)
    assert tpdo.items[2].register.identifier == "FSOE_SAFE_POSITION"
    assert tpdo.items[2].size_bits == 8

    assert tpdo.items[3].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
    assert tpdo.items[3].size_bits == 16

    # On this padding, the 32-bit variable will continue to be transmitted
    # (16 bits of 32 bits, 8 remaining)
    assert tpdo.items[4].register.identifier == "PADDING"
    assert tpdo.items[4].size_bits == 16

    assert tpdo.items[5].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC1"
    assert tpdo.items[5].size_bits == 16

    # On this padding, the 32-bit variable will continue to be transmitted
    # (8 bits of 32 bits, 0 remaining)
    assert tpdo.items[6].register.identifier == "PADDING"
    assert tpdo.items[6].size_bits == 8

    # 8 bits of regular padding to fill the 16 bits of the data last slot.
    assert tpdo.items[7].register.identifier == "PADDING"
    assert tpdo.items[7].size_bits == 8

    assert tpdo.items[8].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC2"
    assert tpdo.items[8].size_bits == 16

    assert tpdo.items[9].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
    assert tpdo.items[9].size_bits == 16

    assert len(tpdo.items) == 10

    rpdo = RPDOMap()
    maps.fill_rpdo_map(rpdo, safe_dict)

    recreated_pdu_maps = ProcessImage.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
    assert (
        recreated_pdu_maps.outputs.get_text_representation()
        == maps.outputs.get_text_representation()
    )
    assert (
        recreated_pdu_maps.inputs.get_text_representation() == maps.inputs.get_text_representation()
    )


@pytest.mark.fsoe
def test_map_with_32_bit_vars_offset_16(
    safe_dict: "EthercatDictionary", fsoe_dict: "FSoEDictionary"
) -> None:
    maps = ProcessImage.empty(fsoe_dict)

    # Add a first 16-bit variable that will shift the 32-bit variable
    maps.inputs.add(fsoe_dict.name_map["TEST_SI_U16"])
    # Append a 32-bit variable
    maps.inputs.add(fsoe_dict.name_map["FSOE_SAFE_POSITION"])

    # Create the rpdo map
    tpdo = TPDOMap()
    maps.fill_tpdo_map(tpdo, safe_dict)

    assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
    assert tpdo.items[0].size_bits == 8

    assert tpdo.items[1].register.identifier == "TEST_SI_U16"
    assert tpdo.items[1].size_bits == 16

    assert tpdo.items[2].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
    assert tpdo.items[2].size_bits == 16

    # Variable cut to what fills on the slot (16 bits of 32 bits, 16 remaining)
    assert tpdo.items[3].register.identifier == "FSOE_SAFE_POSITION"
    assert tpdo.items[3].size_bits == 16

    assert tpdo.items[4].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC1"
    assert tpdo.items[4].size_bits == 16

    # On this padding, the 32-bit variable will continue to be transmitted
    # (16 bits of 32 bits, 16 remaining)
    assert tpdo.items[5].register.identifier == "PADDING"
    assert tpdo.items[5].size_bits == 16

    assert tpdo.items[6].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC2"
    assert tpdo.items[6].size_bits == 16

    assert tpdo.items[7].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
    assert tpdo.items[7].size_bits == 16

    assert len(tpdo.items) == 8

    rpdo = RPDOMap()
    maps.fill_rpdo_map(rpdo, safe_dict)

    recreated_pdu_maps = ProcessImage.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
    assert (
        recreated_pdu_maps.outputs.get_text_representation()
        == maps.outputs.get_text_representation()
    )
    assert (
        recreated_pdu_maps.inputs.get_text_representation() == maps.inputs.get_text_representation()
    )


@pytest.mark.fsoe
@pytest.mark.parametrize("unify_pdo_mapping", [True, False])
def test_map_with_16_bit_vars_offset_8(
    safe_dict: "EthercatDictionary", fsoe_dict: "FSoEDictionary", unify_pdo_mapping: bool
) -> None:
    maps = ProcessImage.empty(fsoe_dict)

    # Add a first 8-bit variable that will shift the 16-bit variable
    maps.inputs.add(fsoe_dict.name_map["TEST_SI_U8"])
    # Append a 32-bit variable
    maps.inputs.add(fsoe_dict.name_map["TEST_SI_U16"])

    # Create the rpdo map
    tpdo = TPDOMap()
    maps.fill_tpdo_map(tpdo, safe_dict)

    assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
    assert tpdo.items[0].size_bits == 8

    assert tpdo.items[1].register.identifier == "TEST_SI_U8"
    assert tpdo.items[1].size_bits == 8

    # Variable cut to what fills on the slot (8 bits of 16 bits, 8 remaining)
    assert tpdo.items[2].register.identifier == "TEST_SI_U16"
    assert tpdo.items[2].size_bits == 8

    assert tpdo.items[3].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
    assert tpdo.items[3].size_bits == 16

    # On this padding, the 32-bit variable will continue to be transmitted
    # (8 bits of 16 bits, 0 remaining)
    assert tpdo.items[4].register.identifier == "PADDING"
    assert tpdo.items[4].size_bits == 8

    # Additional padding added automatically, not explicitly on the map
    assert tpdo.items[5].register.identifier == "PADDING"
    assert tpdo.items[5].size_bits == 8

    assert tpdo.items[6].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC1"
    assert tpdo.items[6].size_bits == 16

    assert tpdo.items[7].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
    assert tpdo.items[7].size_bits == 16

    assert len(tpdo.items) == 8

    # The 2 8-bit padding, virtual and non-virtual may come unified
    # It should produce the same result
    if unify_pdo_mapping:
        tpdo.items[4].size_bits = 16  # Expand previous
        del tpdo[5]  # Remove the other padding

    rpdo = RPDOMap()
    maps.fill_rpdo_map(rpdo, safe_dict)

    recreated_pdu_maps = ProcessImage.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
    assert (
        recreated_pdu_maps.outputs.get_text_representation()
        == maps.outputs.get_text_representation()
    )
    assert (
        recreated_pdu_maps.inputs.get_text_representation() == maps.inputs.get_text_representation()
    )


@pytest.mark.fsoe
@pytest.mark.parametrize(
    "pdo_length, frame_data_bytes",
    [
        (6, (1,)),
        (7, (1, 2)),
        (11, (1, 2, 5, 6)),
        (15, (1, 2, 5, 6, 9, 10)),
        (19, (1, 2, 5, 6, 9, 10, 13, 14)),
    ],
)
def test_get_safety_bytes_range_from_pdo_length(
    pdo_length: int, frame_data_bytes: tuple[int, ...]
) -> None:
    assert frame_data_bytes == ProcessImage._ProcessImage__get_safety_bytes_range_from_pdo_length(
        pdo_length
    )


@pytest.mark.fsoe
def test_insert_in_best_position(fsoe_dict: "FSoEDictionary") -> None:
    maps = ProcessImage.empty(fsoe_dict)

    si = fsoe_dict.name_map[SafeInputsFunction.SAFE_INPUTS_UID]
    sp = fsoe_dict.name_map["FSOE_SAFE_POSITION"]
    sto = fsoe_dict.name_map[STOFunction.COMMAND_UID]

    maps.insert_in_best_position(sto)
    maps.insert_in_best_position(sp)
    maps.insert_in_best_position(si)

    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "FSOE_SAFE_INPUTS_VALUE         | 0..1                 | 0..1                \n"
        "Padding                        | 0..2                 | 1..6                \n"
        "FSOE_SAFE_POSITION             | 2..0                 | 4..0                "
    )

    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                "
    )


def __move_test_files(files: list[Path], fsoe_maps_dir: Path, success: bool) -> None:
    """Move test files to success or failure subdirectories.

    Args:
        files: List of file paths to move.
        fsoe_maps_dir: Base FSoE maps directory.
        success: True for successful tests (move to 'passed'), False for failed (move to 'failed').

    Raises:
        RuntimeError: If moving the files fails.
    """
    target_dir = fsoe_maps_dir / ("passed" if success else "failed")
    target_dir.mkdir(exist_ok=True)

    for file_path in files:
        if file_path.exists():
            try:
                target_file = target_dir / file_path.name
                if target_file.exists():
                    target_file.unlink()
                file_path.rename(target_file)
            except Exception as e:
                raise RuntimeError(f"Failed to move {file_path} to {target_dir}: {e}")


def __save_maps_text_representation(maps: "ProcessImage", output_file: Path) -> None:
    """Save the text representation of FSoE maps to a file.

    Args:
        maps: The Process Image object to save
        output_file: Path where to save the text file
    """
    try:
        with output_file.open("w", encoding="utf-8") as f:
            f.write("\n\nInputs\n-------\n")
            f.write(maps.inputs.get_text_representation())
            f.write("\n\n" + "=" * 85 + "\n" + "=" * 85 + "\n\n")
            f.write("Outputs\n-------\n")
            f.write(maps.outputs.get_text_representation())
    except Exception as e:
        warnings.warn(f"Failed to save maps text representation: {e}")


@pytest.fixture
def no_error_tracker(
    mcu_error_queue_a: "ServoErrorQueue", mcu_error_queue_b: "ServoErrorQueue"
) -> Iterator[None]:
    """Fixture to ensure no new errors are added to the error queues during a test."""
    previous_mcu_a_errors = mcu_error_queue_a.get_number_total_errors()
    previous_mcu_b_errors = mcu_error_queue_b.get_number_total_errors()
    yield
    assert mcu_error_queue_a.get_number_total_errors() == previous_mcu_a_errors, (
        f"MCUA error queue changed: {previous_mcu_a_errors} -> "
        f"{mcu_error_queue_a.get_number_total_errors()}. "
        f"\nLast error: {mcu_error_queue_a.get_last_error()}"
    )
    assert mcu_error_queue_b.get_number_total_errors() == previous_mcu_b_errors, (
        f"MCUB error queue changed: {previous_mcu_b_errors} -> "
        f"{mcu_error_queue_b.get_number_total_errors()}. "
        f"\nLast error: {mcu_error_queue_b.get_last_error()}"
    )


@pytest.mark.fsoe_phase2
@pytest.mark.parametrize("iteration", range(25))  # Run 25 times
def test_map_safety_input_output_random(
    mc_with_fsoe_with_sra_and_feedback_scenario: tuple[MotionController, "FSoEMasterHandler"],
    map_generator: "FSoERandomMappingGenerator",
    fsoe_maps_dir: Path,
    timeout_for_data_sra: float,
    random_seed: int,
    random_max_items: int,
    random_paddings: bool,
    fsoe_states: list[FSoEState],
    servo: "EthercatServo",
    no_error_tracker: None,  # noqa: ARG001
    mcu_error_queue_a: "ServoErrorQueue",
    mcu_error_queue_b: "ServoErrorQueue",
    iteration: int,  # noqa: ARG001
) -> None:
    """Tests that random combinations of inputs and outputs are valid."""
    mc, handler = mc_with_fsoe_with_sra_and_feedback_scenario

    mapping_name = f"mapping_{random_max_items}_{random_paddings}_{random_seed}"
    json_file = fsoe_maps_dir / f"{mapping_name}.json"
    txt_file = fsoe_maps_dir / f"{mapping_name}.txt"

    # Generate a random mapping and validate it
    maps = map_generator.generate_and_save_random_mapping(
        dictionary=handler.dictionary,
        max_items=random_max_items,
        random_paddings=random_paddings,
        seed=random_seed,
        filename=json_file,
        override=True,
    )
    maps.validate()

    # Set the new mapping and serialize it for later analysis
    handler.process_image.inputs.clear()
    handler.process_image.outputs.clear()
    handler.set_process_image(maps)
    __save_maps_text_representation(handler.process_image, txt_file)

    test_success = False
    try:
        mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
        test_success = fsoe_states[-1] is FSoEState.DATA and (servo.slave.state is pysoem.OP_STATE)
        if not test_success:
            pytest.fail(
                f"Unexpected FSoE state {fsoe_states[-1]} or servo state {servo.slave.state}"
                f"\nMCUA last error: {mcu_error_queue_a.get_last_error()}"
                f"\nMCUB last error: {mcu_error_queue_b.get_last_error()}"
            )
    except Exception as e:
        pytest.fail(
            f"Failed to reach data state with random mapping: {e}, servo state: {servo.slave.state}"
            f"\nMCUA last error: {mcu_error_queue_a.get_last_error()}"
            f"\nMCUB last error: {mcu_error_queue_b.get_last_error()}"
        )
    finally:
        __move_test_files([json_file, txt_file], fsoe_maps_dir, test_success)


@pytest.mark.fsoe_phase2
def test_map_all_safety_functions(
    mc_with_fsoe_with_sra_and_feedback_scenario: tuple[MotionController, "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    fsoe_maps_dir: Path,
    fsoe_states: list[FSoEState],
    servo: "EthercatServo",
    no_error_tracker: None,  # noqa: ARG001
    mcu_error_queue_a: "ServoErrorQueue",
    mcu_error_queue_b: "ServoErrorQueue",
) -> None:
    """Test that data state can be reached by mapping everything."""
    mc, handler = mc_with_fsoe_with_sra_and_feedback_scenario

    handler.process_image.inputs.clear()
    handler.process_image.outputs.clear()

    # Set the new mapping
    # STO must be mapped in the first position
    sto = handler.get_function_instance(safety_functions.STOFunction)
    handler.process_image.inputs.add(sto.command)
    handler.process_image.outputs.add(sto.command)
    # Add the rest of the safety functions
    for sf in SafetyFunction.for_handler(handler):
        if isinstance(sf, safety_functions.STOFunction):
            continue  # STO is already added
        if hasattr(sf, "command"):
            # SOUT command is not allowed if SOUT disable is set to 1
            if sf.command.name == "FSOE_SOUT":
                continue
            handler.process_image.insert_in_best_position(sf.command)
        elif hasattr(sf, "command_positive"):
            handler.process_image.insert_in_best_position(sf.command_positive)
        elif hasattr(sf, "command_negative"):
            handler.process_image.insert_in_best_position(sf.command_negative)
        else:
            handler.process_image.insert_in_best_position(sf.value)

    # Check that the maps are valid
    handler.process_image.validate()
    json_file = fsoe_maps_dir / "complete_mapping.json"
    txt_file = fsoe_maps_dir / "complete_mapping.txt"
    __save_maps_text_representation(handler.process_image, txt_file)
    FSoEDictionaryMapJSONSerializer.save_mapping_to_json(
        handler.process_image, json_file, override=True
    )

    test_success = False
    try:
        mc.fsoe.configure_pdos(start_pdos=True, start_master=True)
        mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
        test_success = fsoe_states[-1] is FSoEState.DATA and (servo.slave.state is pysoem.OP_STATE)
        if not test_success:
            pytest.fail(
                f"Unexpected FSoE state {fsoe_states[-1]} or servo state {servo.slave.state}"
                f"\nMCUA last error: {mcu_error_queue_a.get_last_error()}"
                f"\nMCUB last error: {mcu_error_queue_b.get_last_error()}"
            )
    except Exception as e:
        pytest.fail(
            f"Failed to reach data state with all safety functions: {e}"
            f"\nMCUA last error: {mcu_error_queue_a.get_last_error()}"
            f"\nMCUB last error: {mcu_error_queue_b.get_last_error()}"
        )
    finally:
        __move_test_files([json_file, txt_file], fsoe_maps_dir, test_success)


@pytest.mark.fsoe_phase2
def test_is_safety_function_mapped() -> None:
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sfs = handler.safety_functions_by_type()
    maps = ProcessImage.empty(handler.dictionary)
    sto_func = sfs[STOFunction][0]
    sto_ios = list(sto_func.ios.values())
    assert maps.is_safety_function_mapped(sto_func) is False
    assert maps.is_safety_function_mapped(sto_func, strict=False) is False
    maps.inputs.add(sto_ios[0])
    assert maps.is_safety_function_mapped(sto_func) is False
    assert maps.is_safety_function_mapped(sto_func, strict=False) is True
    maps.outputs.add(sto_ios[0])
    assert maps.is_safety_function_mapped(sto_func) is True
    assert maps.is_safety_function_mapped(sto_func, strict=False) is True

    si_func = sfs[SafeInputsFunction][0]
    si_ios = list(si_func.ios.values())
    assert maps.is_safety_function_mapped(si_func) is False
    assert maps.is_safety_function_mapped(si_func, strict=False) is False
    maps.inputs.add(si_ios[0])
    assert maps.is_safety_function_mapped(si_func) is True
    assert maps.is_safety_function_mapped(si_func, strict=False) is True

    ss1_func = sfs[SS1Function][0]
    ss1_ios = list(ss1_func.ios.values())
    assert maps.is_safety_function_mapped(ss1_func) is False
    assert maps.is_safety_function_mapped(ss1_func, strict=False) is False
    maps.outputs.add(ss1_ios[0])
    assert maps.is_safety_function_mapped(ss1_func) is True
    assert maps.is_safety_function_mapped(ss1_func, strict=False) is True
    maps.inputs.add(ss1_ios[0])
    assert maps.is_safety_function_mapped(ss1_func) is True
    assert maps.is_safety_function_mapped(ss1_func, strict=False) is True


@pytest.mark.fsoe_phase2
def test_insert_safety_function() -> None:
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sto_func = handler.safety_functions_by_type()[STOFunction][0]

    maps = ProcessImage.empty(handler.dictionary)
    maps.insert_safety_function(sto_func)
    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                "
    )


@pytest.mark.fsoe_phase2
def test_insert_safety_functions_by_type() -> None:
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sfs = handler.safety_functions_by_type()
    maps = ProcessImage.empty(handler.dictionary)
    sto_func = sfs[STOFunction][0]
    sto_ios = list(sto_func.ios.values())
    maps.inputs.add(sto_ios[0])
    maps.insert_safety_functions_by_type(handler, STOFunction)
    maps.insert_safety_functions_by_type(handler, SSRFunction)
    maps.insert_safety_functions_by_type(handler, SSRFunction)
    maps.insert_safety_functions_by_type(handler, SSRFunction)
    maps.insert_safety_functions_by_type(handler, SSRFunction)
    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "FSOE_SSR_COMMAND_1             | 0..1                 | 0..1                \n"
        "FSOE_SSR_COMMAND_2             | 0..2                 | 0..1                \n"
        "FSOE_SSR_COMMAND_3             | 0..3                 | 0..1                \n"
        "FSOE_SSR_COMMAND_4             | 0..4                 | 0..1                "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "FSOE_SSR_COMMAND_1             | 0..1                 | 0..1                \n"
        "FSOE_SSR_COMMAND_2             | 0..2                 | 0..1                \n"
        "FSOE_SSR_COMMAND_3             | 0..3                 | 0..1                \n"
        "FSOE_SSR_COMMAND_4             | 0..4                 | 0..1                "
    )


@pytest.mark.fsoe_phase2
def test_remove_safety_functions_by_type_1() -> None:
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)

    maps = ProcessImage.empty(handler.dictionary)
    maps.insert_safety_functions_by_type(handler, STOFunction)
    maps.insert_safety_functions_by_type(handler, SSRFunction)
    maps.remove_safety_functions_by_type(handler, SSRFunction)
    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "Padding                        | 0..1                 | 0..1                "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "Padding                        | 0..1                 | 0..1                "
    )


@pytest.mark.fsoe_phase2
def test_remove_safety_functions_by_type_2() -> None:
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    ssr_funcs = handler.safety_functions_by_type()[SSRFunction]
    maps = ProcessImage.empty(handler.dictionary)
    maps.insert_safety_functions_by_type(handler, STOFunction)
    maps.insert_safety_function(ssr_funcs[5])
    maps.insert_safety_function(ssr_funcs[3])
    maps.remove_safety_functions_by_type(handler, SSRFunction)
    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "Padding                        | 0..1                 | 0..1                \n"
        "FSOE_SSR_COMMAND_4             | 0..2                 | 0..1                "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                       | 0..0                 | 0..1                \n"
        "Padding                        | 0..1                 | 0..1                \n"
        "FSOE_SSR_COMMAND_4             | 0..2                 | 0..1                "
    )


@pytest.mark.fsoe_phase2
def test_unmap_safety_function() -> None:
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sfs = handler.safety_functions_by_type()
    maps = ProcessImage.empty(handler.dictionary)
    maps.insert_safety_function(sfs[STOFunction][0])
    maps.insert_safety_function(sfs[SSRFunction][0])
    maps.insert_safety_function(sfs[SafeInputsFunction][0])
    maps.unmap_safety_function(sfs[STOFunction][0])
    maps.unmap_safety_function(sfs[SafeInputsFunction][0])
    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "Padding                        | 0..0                 | 0..1                \n"
        "FSOE_SSR_COMMAND_1             | 0..1                 | 0..1                \n"
        "Padding                        | 0..2                 | 0..1                "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "Padding                        | 0..0                 | 0..1                \n"
        "FSOE_SSR_COMMAND_1             | 0..1                 | 0..1                "
    )


@pytest.mark.fsoe_phase2
def test_unmap_safety_function_warring(caplog: "pytest.LogCaptureFixture") -> None:
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sfs = handler.safety_functions_by_type()
    maps = ProcessImage.empty(handler.dictionary)
    si_func = sfs[SafeInputsFunction][0]
    with caplog.at_level("WARNING"):
        maps.unmap_safety_function(si_func)
    assert any("The safety function is not mapped" in record.message for record in caplog.records)


@pytest.mark.fsoe_phase2
def test_unmap_safety_function_partial() -> None:
    handler = MockHandler(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, 0x3B00003)
    sfs = handler.safety_functions_by_type()
    maps = ProcessImage.empty(handler.dictionary)

    sto_func = sfs[STOFunction][0]
    sto_ios = list(sto_func.ios.values())
    maps.outputs.add(sto_ios[0])
    maps.unmap_safety_function(sto_func)

    assert maps.inputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    "
    )
    assert maps.outputs.get_text_representation(item_space=30) == (
        "Item                           | Position bytes..bits | Size bytes..bits    \n"
        "Padding                        | 0..0                 | 0..1                "
    )

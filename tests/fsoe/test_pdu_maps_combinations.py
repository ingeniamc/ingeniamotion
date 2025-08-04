import random
import time

import pytest
from ingenialogger import get_logger

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController

if FSOE_MASTER_INSTALLED:
    import ingeniamotion.fsoe_master.safety_functions as safety_functions
    from ingeniamotion.fsoe_master.fsoe import (
        FSoEDictionaryItem,
        FSoEDictionaryItemInput,
        FSoEDictionaryItemOutput,
        FSoEDictionaryMap,
        align_bits,
    )
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler
    from ingeniamotion.fsoe_master.safety_functions import SafetyFunction


logger = get_logger(__name__)


def _insert_item_according_to_fsoe_rules(
    dictionary_map: FSoEDictionaryMap, item: FSoEDictionaryItem
) -> bool:
    """Insert the item into the appropriate map according to FSoE rules.

    Args:
        dictionary_map: The FSoE dictionary map.
        item: The item to insert.

    Returns:
        True if item was added, False otherwise.
    """
    if not len(dictionary_map._items):
        dictionary_map.add(item)
        return True

    # According to FSoE Frame construction rules, maximum 8 data blocks are allowed in a frame
    last_item = dictionary_map._items[-1]
    current_position_bits = last_item.position_bits + last_item.bits
    # Check if adding this item would exceed the frame size
    if (current_position_bits + item.data_type.bits) > 8 * 16:
        return False

    # If the item is smaller than 16 bits, it cannot be split in different data blocks
    if item.data_type.bits < 16:
        # Check if adding this item would cause it to span across data blocks (16-bit boundaries)
        data_block_boundary = ((current_position_bits // 16) + 1) * 16
        if (current_position_bits + item.data_type.bits) > data_block_boundary:
            # Item would span across data blocks, add padding to align to next boundary
            n_bits_padding = data_block_boundary - current_position_bits
            if (current_position_bits + n_bits_padding + item.data_type.bits) <= 8 * 16:
                dictionary_map.add_padding(n_bits_padding)
            else:
                return False
        dictionary_map.add(item)
        return True

    next_alignment = align_bits(current_position_bits, 16)
    n_bits_padding = next_alignment - current_position_bits
    # Add padding if it fits in the frame, otherwise just add the item
    if (
        n_bits_padding > 0
        and (current_position_bits + item.data_type.bits + n_bits_padding) <= 8 * 16
    ):
        dictionary_map.add_padding(n_bits_padding)
    dictionary_map.add(item)
    return True


def _insert_padding_according_to_fsoe_rules(
    dictionary_map: FSoEDictionaryMap, padding_size: int
) -> None:
    """Insert padding into the dictionary map according to FSoE rules.

    Args:
        dictionary_map: The FSoE dictionary map.
        padding_size: The size of the padding to insert in bits.
    """
    if not len(dictionary_map._items):
        dictionary_map.add_padding(padding_size)
        return

    # According to FSoE Frame construction rules, maximum 8 data blocks are allowed in a frame
    last_item = dictionary_map._items[-1]
    current_position_bits = last_item.position_bits + last_item.bits
    # Check if adding this item would exceed the frame size
    if (current_position_bits + padding_size) > 8 * 16:
        return

    # If the item is smaller than 16 bits, it cannot be split in different data blocks
    if padding_size < 16:
        # Check if adding this item would cause it to span across data blocks (16-bit boundaries)
        data_block_boundary = ((current_position_bits // 16) + 1) * 16
        if (current_position_bits + padding_size) > data_block_boundary:
            n_bits_padding = data_block_boundary - current_position_bits
            # If item would span across data blocks,
            # just add padding to align to next boundary
            if n_bits_padding > 0:
                dictionary_map.add_padding(n_bits_padding)
            else:
                return
        else:
            dictionary_map.add_padding(padding_size)
        return

    next_alignment = align_bits(current_position_bits, 16)
    n_bits_padding = next_alignment - current_position_bits
    # If padding is not aligned, just add the remaining bits for the alignment
    if n_bits_padding > 0:
        dictionary_map.add_padding(n_bits_padding)
    else:
        dictionary_map.add_padding(padding_size)


def _add_random_item_to_map(
    handler: FSoEMasterHandler, item: FSoEDictionaryItem, random_paddings: bool
) -> None:
    """Add a random item to the map with optional padding.

    Args:
        handler: The FSoE master handler.
        item: The item that will be added to the map.
        random_paddings: True to add random paddings to the mapping.
    """
    add_padding = random_paddings and random.choice([True, False])

    if add_padding:
        # Random padding size between 1-16 bits
        padding_size = random.randint(1, 16)

        # Add the item + padding
        if isinstance(item, FSoEDictionaryItemInput):
            added = _insert_item_according_to_fsoe_rules(handler.maps.inputs, item)
            if added:
                _insert_padding_according_to_fsoe_rules(handler.maps.inputs, padding_size)
        elif isinstance(item, FSoEDictionaryItemOutput):
            added = _insert_item_according_to_fsoe_rules(handler.maps.outputs, item)
            if added:
                _insert_padding_according_to_fsoe_rules(handler.maps.outputs, padding_size)
        else:
            input_added = _insert_item_according_to_fsoe_rules(handler.maps.inputs, item)
            output_added = _insert_item_according_to_fsoe_rules(handler.maps.outputs, item)

            # FSoEDictionaryItemInputOutput - add padding to random map, not to both
            if random.choice([True, False]):
                if input_added:
                    _insert_padding_according_to_fsoe_rules(handler.maps.inputs, padding_size)
            elif output_added:
                _insert_padding_according_to_fsoe_rules(handler.maps.outputs, padding_size)
    else:
        # Insert the item in the best position without padding
        handler.maps.insert_in_best_position(item)


def generate_random_mapping(
    handler: FSoEMasterHandler, max_items: int, random_paddings: bool
) -> None:
    """Generate a random mapping of safety functions, adding 1 of each data type randomly.

    When a data type is finished, continue with the remaining ones.

    Args:
        handler: The FSoE master handler.
        max_items: Maximum number of items to add to the mapping.
        random_paddings: True to add random paddings to the mapping.
            Insert in best position will be used otherwise.
    """
    items_added = 0

    # Sort the safety inputs and outputs according to their data type
    safety_io = {}
    for io in handler.dictionary.name_map.values():
        if io.data_type not in safety_io:
            safety_io[io.data_type] = []
        safety_io[io.data_type].append(io)

    # According to FSoE Frame construction rules, STO must be the first item in the outputs map
    if safety_functions.STOFunction.COMMAND_UID in handler.dictionary.name_map:
        # Add the STO command to the outputs map first
        sto_command = handler.dictionary.name_map[safety_functions.STOFunction.COMMAND_UID]
        _add_random_item_to_map(handler=handler, item=sto_command, random_paddings=random_paddings)
        safety_io[sto_command.data_type].remove(sto_command)
        items_added += 1

    # Continue adding items until we reach max_items or run out of items
    available_data_types = list(safety_io.keys())
    while items_added < max_items and available_data_types:
        # Randomly select a data type
        selected_type = random.choice(available_data_types)

        # Check if this data type still has items available and
        # randomly select an item of this data type
        # If not, remove it from the available data types
        if not safety_io[selected_type]:
            available_data_types.remove(selected_type)
            continue
        selected_item = random.choice(safety_io[selected_type])

        # Add the item to the mapping
        _add_random_item_to_map(
            handler=handler, item=selected_item, random_paddings=random_paddings
        )
        safety_io[selected_type].remove(selected_item)  # Item already added
        items_added += 1


@pytest.mark.fsoe_phase_II
def test_map_safety_input_output_random(
    mc_with_fsoe_with_sra: tuple[MotionController, FSoEMasterHandler],
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    # Clear existing mappings
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()

    # Generate a random mapping
    generate_random_mapping(handler=handler, max_items=5, random_paddings=True)
    handler.maps.validate()

    mc.fsoe.configure_pdos()

    # After reconfiguring the maps and configuring the pdos,
    # The PDOs can be printed to check the mapping
    logger.info("Outputs PDO Map:")
    logger.info(handler.safety_master_pdu_map.get_text_representation())
    logger.info("Inputs PDO Map:")
    logger.info(handler.safety_slave_pdu_map.get_text_representation())

    mc.capture.pdo.start_pdos()
    logger.info("PDOs started")
    mc.fsoe.wait_for_state_data(timeout=10)
    logger.info("FSoE Master reached Data state")
    # Stay 3 seconds in Data state
    for i in range(3):
        time.sleep(1)
    logger.info("Stopping FSoE Master handler")
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe_phase_II
def test_map_all_safety_functions(
    mc_with_fsoe_with_sra: tuple[MotionController, FSoEMasterHandler],
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    inputs = handler.maps.inputs
    outputs = handler.maps.outputs

    # The handler comes with a default mapping read from the drive.
    # Clear it to create a new one
    inputs.clear()
    outputs.clear()

    for sf in SafetyFunction.for_handler(handler):
        if hasattr(sf, "command"):
            handler.maps.insert_in_best_position(sf.command)
        else:
            handler.maps.insert_in_best_position(sf.value)

    # Check that the maps are valid
    handler.maps.validate()
    mc.fsoe.configure_pdos()
    mc.capture.pdo.start_pdos()
    mc.fsoe.wait_for_state_data(timeout=10)
    # Stay 3 seconds in Data state
    for i in range(3):
        time.sleep(1)
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe_phase_II
def test_mappings_with_mc_and_fsoe_fixture(
    mc_with_fsoe_with_sra: tuple[MotionController, FSoEMasterHandler],
) -> None:
    mc, handler = mc_with_fsoe_with_sra
    # Get the safety functions instances
    sto = handler.get_function_instance(safety_functions.STOFunction)
    safe_inputs = handler.get_function_instance(safety_functions.SafeInputsFunction)
    ss1 = handler.get_function_instance(safety_functions.SS1Function)
    ss2 = handler.get_function_instance(safety_functions.SS2Function, instance=1)
    sos = handler.get_function_instance(safety_functions.SOSFunction)

    # The handler comes with a default mapping read from the drive.
    # Clear it to create a new one
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()

    # # Configure Outputs map
    outputs = handler.maps.outputs
    outputs.add(sto.command)
    outputs.add(ss1.command)
    outputs.add(sos.command)
    outputs.add(ss2.command)
    outputs.add_padding(4 + 8)

    # Configure Inputs Map
    inputs = handler.maps.inputs
    inputs.add(sto.command)
    inputs.add(ss1.command)
    inputs.add(safe_inputs.value)
    inputs.add_padding(7)

    # Print the maps to check the configuration
    logger.info("Inputs Map:")
    logger.info(inputs.get_text_representation())
    logger.info("Outputs Map:")
    logger.info(outputs.get_text_representation())

    # Check that the maps are valid
    handler.maps.validate()

    mc.fsoe.configure_pdos()

    # After reconfiguring the maps and configuring the pdos,
    # The PDOs can be printed to check the mapping
    logger.info("Outputs PDO Map:")
    logger.info(handler.safety_master_pdu_map.get_text_representation())
    logger.info("Inputs PDO Map:")
    logger.info(handler.safety_slave_pdu_map.get_text_representation())

    # Start pdo transmission
    mc.capture.pdo.start_pdos()

    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=10)

    for i in range(5):
        time.sleep(1)
        # During this time, commands can be changed
        sto.command.set(1)
        ss1.command.set(1)
        # And inputs can be read
        logger.info(f"Safe Inputs Value: {safe_inputs.value.get()}")

    logger.info("Test finished. Stopping FSoE Master handler")
    mc.fsoe.stop_master(stop_pdos=True)

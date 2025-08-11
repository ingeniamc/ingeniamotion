import random
from pathlib import Path

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

if FSOE_MASTER_INSTALLED:
    import ingeniamotion.fsoe_master.safety_functions as safety_functions
    from ingeniamotion.fsoe_master.fsoe import (
        FSoEDictionary,
        FSoEDictionaryItem,
        FSoEDictionaryItemInput,
        FSoEDictionaryItemOutput,
        FSoEDictionaryMap,
        align_bits,
    )
    from ingeniamotion.fsoe_master.maps import PDUMaps
    from tests.fsoe.map_json_serializer import FSoEDictionaryMapJSONSerializer


class FSoERandomMappingGenerator:
    """Class to generate random PDU mappings."""

    @staticmethod
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
            # Check if adding this item would cause it to span across data blocks
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

    @staticmethod
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
            # Check if adding this item would cause it to span across data blocks
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

    @staticmethod
    def _add_random_item_to_map(
        maps: PDUMaps, item: FSoEDictionaryItem, random_paddings: bool
    ) -> None:
        """Add a random item to the map with optional padding.

        Args:
            maps: The PDU maps.
            item: The item that will be added to the map.
            random_paddings: True to add random paddings to the mapping.
        """
        add_padding = random_paddings and random.choice([True, False])

        if add_padding:
            # Random padding size between 1-16 bits
            padding_size = random.randint(1, 16)

            # Add the item + padding
            if isinstance(item, FSoEDictionaryItemInput):
                added = FSoERandomMappingGenerator._insert_item_according_to_fsoe_rules(
                    maps.inputs, item
                )
                if added:
                    FSoERandomMappingGenerator._insert_padding_according_to_fsoe_rules(
                        maps.inputs, padding_size
                    )
            elif isinstance(item, FSoEDictionaryItemOutput):
                added = FSoERandomMappingGenerator._insert_item_according_to_fsoe_rules(
                    maps.outputs, item
                )
                if added:
                    FSoERandomMappingGenerator._insert_padding_according_to_fsoe_rules(
                        maps.outputs, padding_size
                    )
            else:
                input_added = FSoERandomMappingGenerator._insert_item_according_to_fsoe_rules(
                    maps.inputs, item
                )
                output_added = FSoERandomMappingGenerator._insert_item_according_to_fsoe_rules(
                    maps.outputs, item
                )

                # FSoEDictionaryItemInputOutput - add padding to random map, not to both
                if random.choice([True, False]):
                    if input_added:
                        FSoERandomMappingGenerator._insert_padding_according_to_fsoe_rules(
                            maps.inputs, padding_size
                        )
                elif output_added:
                    FSoERandomMappingGenerator._insert_padding_according_to_fsoe_rules(
                        maps.outputs, padding_size
                    )
        else:
            # Insert the item in the best position without padding
            maps.insert_in_best_position(item)

    @staticmethod
    def generate_random_mapping(
        dictionary: "FSoEDictionary",
        max_items: int,
        random_paddings: bool,
        seed: int = None,
    ) -> PDUMaps:
        """Generate a random mapping of safety functions, adding 1 of each data type randomly.

        When a data type is finished, continue with the remaining ones.

        Args:
            dictionary: The FSoE dictionary.
            max_items: Maximum number of items to add to the mapping.
            random_paddings: True to add random paddings to the mapping.
                Insert in best position will be used otherwise.
            seed: Optional random seed for reproducibility.
                If None, a fixed seed will be used.

        Returns:
            PDUMaps: The generated PDU maps with the random mapping.
        """
        if seed is not None:
            random.seed(seed)

        # Clear existing mappings
        maps = PDUMaps.empty(dictionary=dictionary)

        items_added = 0

        # Sort the safety inputs and outputs according to their data type
        safety_io = {}
        for io in dictionary.name_map.values():
            if io.data_type not in safety_io:
                safety_io[io.data_type] = []
            safety_io[io.data_type].append(io)

        # According to FSoE Frame construction rules, STO must be the first item in the outputs map
        if safety_functions.STOFunction.COMMAND_UID in dictionary.name_map:
            # Add the STO command to the outputs map first
            sto_command = dictionary.name_map[safety_functions.STOFunction.COMMAND_UID]
            FSoERandomMappingGenerator._add_random_item_to_map(
                maps=maps, item=sto_command, random_paddings=random_paddings
            )
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
            FSoERandomMappingGenerator._add_random_item_to_map(
                maps=maps, item=selected_item, random_paddings=random_paddings
            )
            safety_io[selected_type].remove(selected_item)  # Item already added
            items_added += 1

        return maps

    @staticmethod
    def generate_and_save_random_mapping(
        dictionary: "FSoEDictionary",
        max_items: int,
        random_paddings: bool,
        filename: Path,
        override: bool = False,
        seed: int = None,
    ) -> PDUMaps:
        """Generate a random mapping and save it to a JSON file for reproducible testing.

        Args:
            dictionary: The FSoE dictionary.
            max_items: Maximum number of items to add to the mapping.
            random_paddings: True to add random paddings to the mapping.
            filename: Path to the JSON file to save the mapping.
            override: If True, will overwrite existing file. Defaults to False.
            seed: Optional random seed for reproducibility. Defaults to None.
                If None, a fixed seed will be used.

        Returns:
            The generated PDU maps.
        """
        maps = FSoERandomMappingGenerator.generate_random_mapping(
            dictionary, max_items, random_paddings, seed
        )
        FSoEDictionaryMapJSONSerializer.save_mapping_to_json(maps, filename, override=override)
        return maps

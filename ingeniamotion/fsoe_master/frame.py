from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from ingenialink.canopen.register import CanopenRegister
from ingenialink.ethercat.dictionary import EthercatDictionaryV2
from ingenialink.pdo import PDOMap, PDOMapItem

from ingeniamotion.fsoe_master.safety_functions import (
    SafeInputsFunction,
    SS1Function,
    STOFunction,
)

if TYPE_CHECKING:
    from ingenialink.dictionary import Dictionary

    from ingeniamotion.fsoe_master.fsoe import (
        FSoEDictionaryItem,
        FSoEDictionaryMap,
        FSoEDictionaryMappedItem,
    )


@dataclass()
class FSoEFrameElements:
    """FSoE Frame Elements.

    Indicates uids of elements that compose the FSoE frame, excluding the safe data.
    """

    command_uid: str
    crcs_prefix: str
    connection_id_uid: str

    def get_crc_uid(self, data_slot_i: int) -> str:
        """Get the CRC element name for the given data slot index.

        Returns:
            The CRC element name for the given data slot index.
        """
        return f"{self.crcs_prefix}{data_slot_i}"


MASTER_FRAME_ELEMENTS = FSoEFrameElements(
    command_uid="FSOE_MASTER_FRAME_ELEM_CMD",
    crcs_prefix="FSOE_MASTER_FRAME_ELEM_CRC",
    connection_id_uid="FSOE_MASTER_FRAME_ELEM_CONNID",
)


SLAVE_FRAME_ELEMENTS = FSoEFrameElements(
    command_uid="FSOE_SLAVE_FRAME_ELEM_CMD",
    crcs_prefix="FSOE_SLAVE_FRAME_ELEM_CRC",
    connection_id_uid="FSOE_SLAVE_FRAME_ELEM_CONNID",
)


class FSoEFrame:
    """Class to build FSoE frames."""

    __SLOT_WIDTH = 16
    """Number of bits in a data slot of the Safety PDU."""

    @staticmethod
    def __create_pdo_item(
        servo_dictionary: "Dictionary",
        uid: str,
        item_type: type[PDOMapItem],
        size_bits: Optional[int] = None,
    ) -> PDOMapItem:
        if isinstance(servo_dictionary, EthercatDictionaryV2):
            # Dictionary V2 only supports SaCo phase 1
            # That does do not configure the pdo maps.
            # Padding items are enough to fill the map
            if uid == MASTER_FRAME_ELEMENTS.command_uid or uid == SLAVE_FRAME_ELEMENTS.command_uid:
                return item_type(size_bits=8)
            if (
                uid == MASTER_FRAME_ELEMENTS.connection_id_uid
                or uid == SLAVE_FRAME_ELEMENTS.connection_id_uid
            ):
                return item_type(size_bits=16)
            if uid.startswith((
                MASTER_FRAME_ELEMENTS.crcs_prefix,
                SLAVE_FRAME_ELEMENTS.crcs_prefix,
            )):
                return item_type(size_bits=16)
            if uid in [
                STOFunction.COMMAND_UID,
                SS1Function.COMMAND_UID.format(i=1),
                SafeInputsFunction.SAFE_INPUTS_UID,
            ]:
                return item_type(size_bits=1)

            raise NotImplementedError(f"Unknown FSoE item UID for Dictionary V2: {uid}")
        else:
            reg = servo_dictionary.get_register(uid)
            if not isinstance(reg, CanopenRegister):
                # Type could be narrowed to EthercatRegister
                # After this bugfix:
                # https://novantamotion.atlassian.net/browse/INGK-1111
                raise TypeError
            return item_type(reg, size_bits)

    @staticmethod
    def __create_pdo_safe_data_item(
        servo_dictionary: "Dictionary",
        item: "FSoEDictionaryItem",
        item_type: type[PDOMapItem],
        size_bits: Optional[int] = None,
    ) -> PDOMapItem:
        if item.item is None:
            # Padding item
            return item_type(size_bits=size_bits if size_bits is not None else item.bits)
        else:
            # I/O item
            return FSoEFrame.__create_pdo_item(
                servo_dictionary, item.item.name, item_type, size_bits=size_bits
            )

    @staticmethod
    def __get_crc_item(
        data_slot_i: int,
        frame_elements: FSoEFrameElements,
        pdo_item_type: type[PDOMapItem],
        servo_dictionary: "Dictionary",
    ) -> PDOMapItem:
        try:
            return FSoEFrame.__create_pdo_item(
                servo_dictionary, frame_elements.get_crc_uid(data_slot_i), pdo_item_type
            )
        except KeyError as e:
            raise NotImplementedError(
                f"No CRC found for data slot {data_slot_i}. Probably the PDU Map is wide"
            ) from e

    @staticmethod
    def generate_slot_structure(
        dict_map: "FSoEDictionaryMap", slot_width: int
    ) -> Iterator[tuple[int, list[tuple[Optional[int], Optional["FSoEDictionaryMappedItem"]]]]]:
        """Generate the slot structure for a dictionary map.

        Args:
            dict_map: The dictionary map to generate the slot structure for.
            slot_width: The width of each data slot in bits.

        Yields:
            Tuples of (slot_index, (bits_in_slot, item))
            If item is None, it means a virtual padding item.
            If bits_in_slot is None, it means that the item fits in the slot without padding.
        """
        data_slot_i = 0

        # The minimum bits for the initial data slot is 8 bits
        slot_bit_maximum = 8

        # List of items that will be in the current slot
        # (bits in the slot, item)
        current_slot_items: list[tuple[Optional[int], Optional[FSoEDictionaryMappedItem]]] = []

        for item in dict_map:
            if slot_bit_maximum == 8 and item.position_bits + item.bits >= slot_bit_maximum:
                # Since there's enough data to overflow the initial slot of 8 bits,
                # it will be of 16 bits instead
                slot_bit_maximum = slot_width

            if item.position_bits >= slot_bit_maximum:
                # This item must go in the next data slot
                if current_slot_items:
                    yield (data_slot_i, current_slot_items)
                    current_slot_items = []
                data_slot_i += 1
                slot_bit_maximum += slot_width

            if item.position_bits + item.bits <= slot_bit_maximum:
                # The item fits in the current slot
                current_slot_items.append((None, item))
            else:
                # The item must go in the current slot, and on the next one
                # Have a virtual padding with the remaining bits
                # As described on ETG5120 Section 5.3.3

                # Number of bits that will be used in the current slot,
                # taking into account that it may start in the middle of the slot
                item_bits_in_slot = slot_width - item.position_bits % slot_width
                current_slot_items.append((item_bits_in_slot, item))

                # Yield current slot
                yield (data_slot_i, current_slot_items)
                current_slot_items = []

                # There are remaining bits that must be mapped into virtual paddings
                remaining_bits_to_map = item.bits - item_bits_in_slot

                while remaining_bits_to_map > 0:
                    data_slot_i += 1
                    slot_bit_maximum += slot_width
                    bits_to_map_in_this_slot = min(remaining_bits_to_map, slot_width)
                    # Virtual Padding item
                    current_slot_items.append((bits_to_map_in_this_slot, None))
                    if remaining_bits_to_map > slot_width:
                        yield (data_slot_i, current_slot_items)
                        current_slot_items = []

                    remaining_bits_to_map -= bits_to_map_in_this_slot

        # Yield the last slot if it has items
        if current_slot_items:
            yield (data_slot_i, current_slot_items)

    @staticmethod
    def fill_pdo_map(
        dict_map: "FSoEDictionaryMap",
        servo_dictionary: "Dictionary",
        pdo_map: PDOMap,
        pdo_item_type: type[PDOMapItem],
        frame_elements: FSoEFrameElements,
    ) -> None:
        """Fill the PDO map with the FSoE frame elements and the safe data.

        Args:
            dict_map: The dictionary map to fill the PDO map with.
            servo_dictionary: The servo dictionary to use for the PDO items.
            pdo_map: The PDO map to fill.
            pdo_item_type: The type of the PDO items to create.
            frame_elements: The frame elements to use for the PDO map.
        """
        # Remove any existing items in the PDOMap
        pdo_map.clear()

        # Initial FSoE command
        pdo_map.add_item(
            FSoEFrame.__create_pdo_item(servo_dictionary, frame_elements.command_uid, pdo_item_type)
        )

        for data_slot_i, slot_items in FSoEFrame.generate_slot_structure(
            dict_map, FSoEFrame.__SLOT_WIDTH
        ):
            for bits_in_slot, item in slot_items:
                # Virtual padding item
                if item is None:
                    pdo_map.add_item(pdo_item_type(size_bits=bits_in_slot))
                else:
                    pdo_map.add_item(
                        FSoEFrame.__create_pdo_safe_data_item(
                            servo_dictionary, item, pdo_item_type, size_bits=bits_in_slot
                        )
                    )

            # Add CRC for this slot
            pdo_map.add_item(
                FSoEFrame.__get_crc_item(
                    data_slot_i, frame_elements, pdo_item_type, servo_dictionary
                )
            )

        pdo_map.add_item(
            FSoEFrame.__create_pdo_item(
                servo_dictionary, frame_elements.connection_id_uid, pdo_item_type
            )
        )

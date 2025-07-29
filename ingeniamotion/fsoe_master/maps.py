from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from ingenialink.canopen.register import CanopenRegister
from ingenialink.ethercat.dictionary import EthercatDictionaryV2
from ingenialink.pdo import PDOMap, PDOMapItem, RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem

from ingeniamotion.fsoe_master.fsoe import (
    FSoEDictionary,
    FSoEDictionaryItem,
    FSoEDictionaryItemInput,
    FSoEDictionaryItemInputOutput,
    FSoEDictionaryItemOutput,
    FSoEDictionaryMap,
)
from ingeniamotion.fsoe_master.safety_functions import (
    SafeInputsFunction,
    SafetyFunction,
    SS1Function,
    STOFunction,
)

if TYPE_CHECKING:
    from ingenialink.dictionary import Dictionary

__all__ = ["PDUMaps"]


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


class PDUMaps:
    """Helper class to configure the Safety PDU PDOMaps."""

    __SLOT_WIDHT = 16
    """Number of bits in a data slot of the Safety PDU."""

    def __init__(
        self,
        outputs: "FSoEDictionaryMap",
        inputs: "FSoEDictionaryMap",
    ) -> None:
        self.outputs = outputs
        self.inputs = inputs

    @classmethod
    def empty(cls, dictionary: "FSoEDictionary") -> "PDUMaps":
        """Create an empty PDUMaps instance with the given dictionary.

        Returns:
            PDUMaps instance with empty outputs and inputs maps.
        """
        return cls(
            outputs=FSoEDictionaryMap(
                dictionary,
                item_types_accepted={FSoEDictionaryItemOutput, FSoEDictionaryItemInputOutput},
            ),
            inputs=FSoEDictionaryMap(
                dictionary,
                item_types_accepted={FSoEDictionaryItemInput, FSoEDictionaryItemInputOutput},
            ),
        )

    @classmethod
    def default(cls, dictionary: "FSoEDictionary") -> "PDUMaps":
        """Create a default PDUMaps instance with the default dictionary.

        Returns:
            PDUMaps instance with the minimum required items for the PDU maps.
        """
        maps = cls.empty(dictionary)
        maps.outputs.add(dictionary.name_map[STOFunction.COMMAND_UID])
        return maps

    def copy(self) -> "PDUMaps":
        """Create a copy of the PDUMaps instance.

        Returns:
            A new PDUMaps instance with copies of the outputs and inputs maps.
        """
        return PDUMaps(
            outputs=self.outputs.copy(),
            inputs=self.inputs.copy(),
        )

    @property
    def editable(self) -> bool:
        """Indicates if the PDU maps can be edited."""
        return not (self.outputs.locked or self.inputs.locked)

    def insert_in_best_position(self, element: "FSoEDictionaryItem") -> None:
        """Insert I/O in any best position of the maps.

        Finds unused space in the map and insert them there.
        If not unused space is found, it appends the item to the end of the map.

        Args:
            element: element to add

        Raises:
            TypeError: if the element is not of a valid type.
        """
        align_to = 1
        if element.data_type.bits > 8:
            align_to = 8
        if isinstance(element, FSoEDictionaryItemOutput):
            self.outputs.insert_in_best_position(element, align_to)
        elif isinstance(element, FSoEDictionaryItemInput):
            self.inputs.insert_in_best_position(element, align_to)
        elif isinstance(element, FSoEDictionaryItemInputOutput):
            self.inputs.insert_in_best_position(element, align_to)
            self.outputs.insert_in_best_position(element, align_to)
        else:
            raise TypeError(f"Unknown IO Element type: {type(element)}")

    def insert_safety_function(self, safety_function: "SafetyFunction") -> None:
        """Insert all elements of the safety function on the maps.

        Args:
            safety_function: Safety function
        """
        for io in safety_function.io:
            self.insert_in_best_position(io)

    @classmethod
    def from_rpdo_tpdo(
        cls, rpdo: RPDOMap, tpdo: TPDOMap, dictionary: "FSoEDictionary"
    ) -> "PDUMaps":
        """Create a PDUMaps instance from the given RPDO and TPDO maps.

        Returns:
            PDUMaps instance with the RPDO and TPDO maps filled.
        """
        pdu_maps = cls.empty(dictionary)
        cls.__fill_dictionary_map_from_pdo(rpdo, pdu_maps.outputs)
        cls.__fill_dictionary_map_from_pdo(tpdo, pdu_maps.inputs)
        return pdu_maps

    def fill_rpdo_map(self, rpdo_map: RPDOMap, servo_dictionary: "Dictionary") -> None:
        """Fill the RPDOMap used for the Safety Master PDU."""
        self.outputs.complete_with_padding()
        self.__fill_pdo_map(
            self.outputs,
            servo_dictionary=servo_dictionary,
            pdo_map=rpdo_map,
            pdo_item_type=RPDOMapItem,
            frame_elements=MASTER_FRAME_ELEMENTS,
        )

    def fill_tpdo_map(self, tpdo_map: TPDOMap, servo_dictionary: "Dictionary") -> None:
        """Fill the TPDOMap used for the Safety Slave PDU."""
        self.inputs.complete_with_padding()
        self.__fill_pdo_map(
            self.inputs,
            servo_dictionary=servo_dictionary,
            pdo_map=tpdo_map,
            pdo_item_type=TPDOMapItem,
            frame_elements=SLAVE_FRAME_ELEMENTS,
        )

    @staticmethod
    def __get_safety_bytes_range_from_pdo_length(pdo_byte_length: int) -> tuple[int, ...]:
        """Get the bytes that belong to the safe data in a PDO map according to its length.

        Args:
            pdo_byte_length: byte length of the PDO map

        Raises:
            ValueError: if pdo_byte_lenght is less than 6

        Returns:
            Tuple containing all byte indexes of the PDO map that belong to safe data
        """
        if pdo_byte_length < 6:
            raise ValueError("pdo_lenght must be at least 6")
        elif pdo_byte_length == 6:
            # Shortest PDOMap is 6 bytes, containing only one data byte
            return (1,)
        else:
            # The total bytes of data is the Pdo map length
            # minus 1 byte for the command and 2 bytes for the connection ID
            # divided by 4, since each data slot has 2 bytes of data and 2 bytes of CRC
            total_data_slots = (pdo_byte_length - 3) // 4
            return tuple(
                byt
                for slot_i in range(total_data_slots)
                for byt in (1 + slot_i * 4, 2 + slot_i * 4)
            )

    @classmethod
    def __fill_dictionary_map_from_pdo(
        cls, pdo_map: PDOMap, dictionary_map: "FSoEDictionaryMap"
    ) -> None:
        """Fill the dictionary map with items from the given PDOMap."""
        valid_bits = tuple(
            valid_bit
            for valid_byte in cls.__get_safety_bytes_range_from_pdo_length(
                pdo_map.data_length_bytes
            )
            for valid_bit in range(valid_byte * 8, (valid_byte + 1) * 8)
        )
        dictionary: FSoEDictionary = dictionary_map.dictionary
        position_bits = 0

        # Number of bits of variables that are in multiple data slots
        # That will be on future virtual padding
        pending_virtual_padding_bits = 0

        for pdo_item in pdo_map.items:
            if position_bits in valid_bits:
                # The item is a safe data item
                if pdo_item.register.idx == 0:
                    # Padding item

                    if pending_virtual_padding_bits == 0:
                        # Regular padding item
                        dictionary_map.add_padding(pdo_item.size_bits)
                    else:
                        # Virtual padding bits must not be added on the mapping,
                        # since they are already accounted on the fsoe map variable
                        if pending_virtual_padding_bits >= pdo_item.size_bits:
                            # There are not enough bits on this padding
                            # to fit all the remaining virtual ones
                            # Or is exactly the same size
                            pending_virtual_padding_bits -= pdo_item.size_bits
                        else:
                            # The padding is larger than the pending virtual bits
                            # All the virtual padding are already accounted,
                            # and some more must be added
                            dictionary_map.add_padding(
                                pdo_item.size_bits - pending_virtual_padding_bits
                            )
                            pending_virtual_padding_bits = 0

                else:
                    # Register item
                    register = pdo_item.register
                    fsoe_item = dictionary.name_map[register.identifier]
                    pending_virtual_padding_bits = fsoe_item.data_type.bits - pdo_item.size_bits
                    dictionary_map.add(fsoe_item)

            position_bits += pdo_item.size_bits

        dictionary_map.merge_adjacent_paddings()

    def __create_pdo_item(
        self,
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

    def __create_pdo_safe_data_item(
        self,
        servo_dictionary: "Dictionary",
        item: "FSoEDictionaryItem",
        item_type: type[PDOMapItem],
        size_bits: Optional[int] = None,
    ) -> PDOMapItem:
        if item.item is None:
            # Padding item
            return item_type(size_bits=item.bits)
        else:
            # I/O item
            return self.__create_pdo_item(
                servo_dictionary, item.item.name, item_type, size_bits=size_bits
            )

    def __get_crc_item(
        self,
        data_slot_i: int,
        frame_elements: FSoEFrameElements,
        pdo_item_type: type[PDOMapItem],
        servo_dictionary: "Dictionary",
    ) -> PDOMapItem:
        try:
            return self.__create_pdo_item(
                servo_dictionary, frame_elements.get_crc_uid(data_slot_i), pdo_item_type
            )
        except KeyError as e:
            raise NotImplementedError(
                f"No CRC found for data slot {data_slot_i}. Probably the PDU Map is wide"
            ) from e

    def __fill_pdo_map(
        self,
        dict_map: "FSoEDictionaryMap",
        servo_dictionary: "Dictionary",
        pdo_map: PDOMap,
        pdo_item_type: type[PDOMapItem],
        frame_elements: FSoEFrameElements,
    ) -> None:
        # Remove any existing items in the PDOMap
        pdo_map.items.clear()

        # Initial FSoE command
        pdo_map.add_item(
            self.__create_pdo_item(servo_dictionary, frame_elements.command_uid, pdo_item_type)
        )

        data_slot_i = 0

        # The minimum bits for the initial data slot is 8 bits
        slot_bit_maximum = 8

        for item in dict_map:
            if slot_bit_maximum == 8 and item.position_bits + item.bits >= slot_bit_maximum:
                # Since there's enough data to overflow the initial slot of 8 bits,
                # it will be of 16 bits instead
                slot_bit_maximum = self.__SLOT_WIDHT

            if item.position_bits >= slot_bit_maximum:
                # This item must go in the next data slot
                # Add a CRC item, and update to the next data slot
                pdo_map.add_item(
                    self.__get_crc_item(
                        data_slot_i, frame_elements, pdo_item_type, servo_dictionary
                    )
                )
                data_slot_i += 1
                slot_bit_maximum += self.__SLOT_WIDHT

            if item.position_bits + item.bits <= slot_bit_maximum:
                # The item fits in the current slot, add it
                pdo_map.add_item(
                    self.__create_pdo_safe_data_item(servo_dictionary, item, pdo_item_type)
                )
            else:
                # The item must go in the current slot, and on the next one
                # Have a virtual padding with the remaining bits
                # As described on ETG5120 Section 5.3.3

                # Number of bits that will be used in the current slot,
                # taking into account that it may start in the middle of the slot
                item_bits_in_slot = self.__SLOT_WIDHT - item.position_bits % self.__SLOT_WIDHT

                # Add I/O item, cut to the bits that fit in the current slot
                pdo_map.add_item(
                    self.__create_pdo_safe_data_item(
                        servo_dictionary, item, pdo_item_type, size_bits=item_bits_in_slot
                    )
                )

                # There are remaining bits that must be mapped into virtual paddings
                remaining_bits_to_map = item.bits - item_bits_in_slot

                while remaining_bits_to_map > 0:
                    # Add CRC item
                    pdo_map.add_item(
                        self.__get_crc_item(
                            data_slot_i, frame_elements, pdo_item_type, servo_dictionary
                        )
                    )
                    data_slot_i += 1
                    slot_bit_maximum += self.__SLOT_WIDHT
                    bits_to_map_in_this_slot = min(remaining_bits_to_map, self.__SLOT_WIDHT)
                    # Virtual Padding item
                    pdo_map.add_item(pdo_item_type(size_bits=bits_to_map_in_this_slot))
                    remaining_bits_to_map -= bits_to_map_in_this_slot

        # Last CRC
        pdo_map.add_item(
            self.__get_crc_item(data_slot_i, frame_elements, pdo_item_type, servo_dictionary),
        )

        # Connection ID
        pdo_map.add_item(
            self.__create_pdo_item(
                servo_dictionary,
                frame_elements.connection_id_uid,
                pdo_item_type,
            )
        )

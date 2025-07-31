from typing import TYPE_CHECKING, Optional

from ingenialink.pdo import PDOMap, RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem

from ingeniamotion.fsoe_master.frame import (
    MASTER_FRAME_ELEMENTS,
    SLAVE_FRAME_ELEMENTS,
    FSoEFrame,
)
from ingeniamotion.fsoe_master.fsoe import (
    FSoEDictionary,
    FSoEDictionaryItem,
    FSoEDictionaryItemInput,
    FSoEDictionaryItemInputOutput,
    FSoEDictionaryItemOutput,
    FSoEDictionaryMap,
)
from ingeniamotion.fsoe_master.maps_validator import (
    FSoEDictionaryMapValidator,
    FSoEFrameRules,
    FSoEFrameRuleValidatorOutput,
)
from ingeniamotion.fsoe_master.safety_functions import (
    SafetyFunction,
)

if TYPE_CHECKING:
    from ingenialink.dictionary import Dictionary

__all__ = ["PDUMaps"]


class PDUMaps:
    """Helper class to configure the Safety PDU PDOMaps."""

    __SLOT_WIDTH = 16
    """Number of bits in a data slot of the Safety PDU."""

    def __init__(
        self,
        outputs: "FSoEDictionaryMap",
        inputs: "FSoEDictionaryMap",
    ) -> None:
        self.outputs = outputs
        self.inputs = inputs
        self.__validator: FSoEDictionaryMapValidator = FSoEDictionaryMapValidator()

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

    def copy(self) -> "PDUMaps":
        """Create a copy of the PDUMaps instance.

        Returns:
            A new PDUMaps instance with copies of the outputs and inputs maps.
        """
        return PDUMaps(
            outputs=self.outputs.copy(),
            inputs=self.inputs.copy(),
        )

    def __validate_dictionary_map(
        self,
        dictionary_map: "FSoEDictionaryMap",
        rules: Optional[list[FSoEFrameRules]],
        raise_exceptions: bool,
    ) -> FSoEFrameRuleValidatorOutput:
        """Validate the given dictionary map against the specified rules.

        Args:
            dictionary_map: The dictionary map to validate.
            rules: Optional list of specific rules to validate. If None, all rules are validated.
            raise_exceptions: If True, raises an exception if any rule is invalid.
                If False, returns the validation output with exceptions. Defaults to False.

        Returns:
            The output of the validation containing the rules and exceptions.
        """
        return self.__validator.validate_dictionary_map_fsoe_frame_rules(
            dictionary_map, rules, raise_exceptions
        )

    def are_inputs_valid(
        self, rules: Optional[list[FSoEFrameRules]] = None, raise_exceptions: bool = False
    ) -> FSoEFrameRuleValidatorOutput:
        """Check if the inputs map is valid.

        Args:
            rules: list of specific rules to validate. If None, all rules are validated.
            raise_exceptions: If True, raises an exception if any rule is invalid.
                If False, returns the validation output with exceptions. Defaults to False.

        Returns:
            The output of the validation containing the rules and exceptions.
        """
        return self.__validate_dictionary_map(self.inputs, rules, raise_exceptions)

    def are_outputs_valid(
        self, rules: Optional[list[FSoEFrameRules]] = None, raise_exceptions: bool = False
    ) -> FSoEFrameRuleValidatorOutput:
        """Check if the outputs map is valid.

        Args:
            rules: list of specific rules to validate. If None, all rules are validated.
            raise_exceptions: If True, raises an exception if any rule is invalid.
                If False, returns the validation output with exceptions. Defaults to False.

        Returns:
            The output of the validation containing the rules and exceptions.
        """
        return self.__validate_dictionary_map(self.outputs, rules, raise_exceptions)

    def is_map_valid(
        self, rules: Optional[list[FSoEFrameRules]] = None, raise_exceptions: bool = False
    ) -> dict[str, FSoEFrameRuleValidatorOutput]:
        """Check if the map is valid.

        Args:
            rules: list of specific rules to validate. If None, all rules are validated.
            raise_exceptions: If True, raises an exception if any rule is invalid.
                If False, returns the validation output with exceptions. Defaults to False.

        Returns:
            Dictiionary with the validation output for inputs and outputs maps.
            The keys are "inputs" and "outputs".
        """
        return {
            "inputs": self.are_inputs_valid(rules, raise_exceptions),
            "outputs": self.are_outputs_valid(rules, raise_exceptions),
        }

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
        FSoEFrame.fill_pdo_map(
            self.outputs,
            servo_dictionary=servo_dictionary,
            pdo_map=rpdo_map,
            pdo_item_type=RPDOMapItem,
            frame_elements=MASTER_FRAME_ELEMENTS,
        )

    def fill_tpdo_map(self, tpdo_map: TPDOMap, servo_dictionary: "Dictionary") -> None:
        """Fill the TPDOMap used for the Safety Slave PDU."""
        self.inputs.complete_with_padding()
        FSoEFrame.fill_pdo_map(
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

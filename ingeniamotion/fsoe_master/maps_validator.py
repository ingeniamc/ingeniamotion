from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from ingenialogger import get_logger
from typing_extensions import override

from ingeniamotion.fsoe_master.fsoe import (
    FSoEDictionaryItemInput,
    FSoEDictionaryItemInputOutput,
    FSoEDictionaryItemOutput,
    FSoEDictionaryMap,
)

logger = get_logger(__name__)


class FSoEFrameRules(Enum):
    """FSoE frame rules."""

    SAFE_DATA_BLOCKS_VALID = (
        "Frame must contain 1-8 blocks of safe data, each 16-bit (except single block may be 8-bit)"
    )
    OBJECTS_IN_FRAME = "A frame can contain up to 45 objects in total"


@dataclass
class InvalidFSoEFrameRule:
    """Information about an invalid FSoE frame rule."""

    rule: FSoEFrameRules  # The rule that was violated
    exception: str  # Description of the error
    position: Optional[int] = None  # Position information where the rule is invalid


class FSoEFrameConstructionError(Exception):
    """FSoE frame construction exceptions."""

    _ERROR_MESSAGE: str = "PDO map validation failed with errors"

    def __init__(self, validation_errors: dict[FSoEFrameRules, list[InvalidFSoEFrameRule]]):
        """Initialize with validation errors.

        Args:
            validation_errors: List of validation errors to include in the message
        """
        error_details = []
        for idx, (rule, errors) in enumerate(validation_errors.items(), 1):
            error_detail = f"  {idx}. Rule: {rule}\n"
            for error in errors:
                error_detail += f"     Error: {error.exception}\n"
            error_details.append(error_detail)

        full_message = f"{self._ERROR_MESSAGE}:\n" + "\n".join(error_details)
        super().__init__(full_message)


class FSoEFrameRuleValidator(ABC):
    """Base class for FSoE frame rule validators.

    Provides a common interface for validating FSoE frame rules.
    """

    def __init__(self) -> None:
        self._exceptions: list[InvalidFSoEFrameRule] = []
        self.__validated: bool = False

    @property
    def is_valid(self) -> bool:
        """Check if the validation has been performed and if there are no exceptions.

        Returns:
            True if validation has been performed and no exceptions were raised, False otherwise.
        """
        if not self.__validated:
            logger.warning("Validation not performed yet, cannot determine validity.")
            return False
        return not self._exceptions

    @abstractmethod
    def _validate(self, dictionary_map: FSoEDictionaryMap) -> None:
        raise NotImplementedError

    def validate(self, dictionary_map: FSoEDictionaryMap) -> list[InvalidFSoEFrameRule]:
        """Validate the FSoE frame rules.

        Args:
            dictionary_map: The dictionary map to validate.

        Returns:
            List of validation errors.
        """
        if self.__validated:
            logger.warning("Validation already performed, returning cached exceptions.")
            return self._exceptions
        self._validate(dictionary_map)
        self.__validated = True
        return self._exceptions

    def reset(self) -> None:
        """Reset the validator state."""
        self._exceptions = []
        self.__validated = False


class SafeDataBlocksValidator(FSoEFrameRuleValidator):
    """Validator for safe data blocks rule: 1-8 blocks, each 16-bit.

    If the frame contains only one block, it may be either 8 bits or 16 bits.

    Each safe data block is followed by a CRC_N, where N is the block index starting from 0.
    """

    __SLOT_WIDHT: int = 16
    __MAX_FRAME_OBJECTS: int = 45

    def _safe_data_blocks_from_dictionary_map(
        self, dictionary_map: FSoEDictionaryMap
    ) -> list[
        list[
            tuple[
                int,
                Union[
                    FSoEDictionaryItemOutput, FSoEDictionaryItemInput, FSoEDictionaryItemInputOutput
                ],
            ]
        ]
    ]:
        """Get safe data blocks from the dictionary map.

        Args:
            dictionary_map: The dictionary map to get safe data blocks from.

        Returns:
            A list of safe data blocks, where each block is a list of tuples containing the
            bit length and the corresponding dictionary item.
        """
        data_slots: list[
            list[
                tuple[
                    int,
                    Union[
                        FSoEDictionaryItemOutput,
                        FSoEDictionaryItemInput,
                        FSoEDictionaryItemInputOutput,
                    ],
                ]
            ]
        ] = []
        current_slot_items: list[
            tuple[
                int,
                Union[
                    FSoEDictionaryItemOutput, FSoEDictionaryItemInput, FSoEDictionaryItemInputOutput
                ],
            ]
        ] = []
        slot_bit_maximum = 8

        # Same logic as in PDUMaps.__fill_pdo_map
        for item in dictionary_map:
            if slot_bit_maximum == 8 and item.position_bits + item.bits >= slot_bit_maximum:
                slot_bit_maximum = self.__SLOT_WIDHT

            if item.position_bits >= slot_bit_maximum:
                if current_slot_items:
                    data_slots.append(current_slot_items)
                    current_slot_items = []
                slot_bit_maximum += self.__SLOT_WIDHT

            if item.position_bits + item.bits <= slot_bit_maximum:
                current_slot_items.append((item.bits, item))
            else:
                item_bits_in_slot = self.__SLOT_WIDHT - item.position_bits % self.__SLOT_WIDHT
                current_slot_items.append((item_bits_in_slot, item))
                data_slots.append(current_slot_items)
                current_slot_items = []

                remaining_bits_to_map = item.bits - item_bits_in_slot
                while remaining_bits_to_map > 0:
                    slot_bit_maximum += self.__SLOT_WIDHT
                    bits_to_map_in_this_slot = min(remaining_bits_to_map, self.__SLOT_WIDHT)
                    current_slot_items.append((bits_to_map_in_this_slot, item))
                    data_slots.append(current_slot_items)
                    current_slot_items = []
                    remaining_bits_to_map -= bits_to_map_in_this_slot

        if current_slot_items:
            data_slots.append(current_slot_items)

        return data_slots

    def _validate_safe_data_blocks_size(
        self,
        safe_data_blocks: list[
            list[
                tuple[
                    int,
                    Union[
                        FSoEDictionaryItemOutput,
                        FSoEDictionaryItemInput,
                        FSoEDictionaryItemInputOutput,
                    ],
                ]
            ]
        ],
    ) -> None:
        """Validate the size of safe data blocks in the dictionary map.

        Args:
            dictionary_map: The dictionary map to validate.
            safe_data_blocks: The list of safe data blocks to validate.
        """
        n_safe_data_blocks = len(safe_data_blocks)

        if n_safe_data_blocks == 0:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                    exception="No safe data blocks found in PDO map",
                )
            )
            return

        # Frames may contain 1 to 8 blocks of safe data (payload)
        if n_safe_data_blocks < 1 or n_safe_data_blocks > 8:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                    exception=f"Expected 1-8 safe data blocks, found {n_safe_data_blocks}",
                )
            )
            return

        # Validate each safe data block
        for block_idx, block_items in enumerate(safe_data_blocks):
            block_size_bits = sum(block_bits for block_bits, _ in block_items)
            # If the frame contains only one block, it may be either 8 bits or 16 bits
            if n_safe_data_blocks == 1:
                if block_size_bits not in (8, 16):
                    self._exceptions.append(
                        InvalidFSoEFrameRule(
                            rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                            exception="Single safe data block must be 8 or 16 bits, "
                            f"found {block_size_bits}",
                            position=block_idx,
                        )
                    )
                    return
            # Each safe data block must be 16 bits
            else:
                if block_size_bits != 16:
                    self._exceptions.append(
                        InvalidFSoEFrameRule(
                            rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                            exception=f"Safe data block {block_idx} must be 16 bits, "
                            f"found {block_size_bits}",
                            position=block_idx,
                        )
                    )
                    return

    def _validate_objects_in_frame(
        self,
        dictionary_map: FSoEDictionaryMap,
        safe_data_blocks: list[
            list[
                tuple[
                    int,
                    Union[
                        FSoEDictionaryItemOutput,
                        FSoEDictionaryItemInput,
                        FSoEDictionaryItemInputOutput,
                    ],
                ]
            ]
        ],
    ) -> None:
        """Validate the number of objects in the frame.

        1 object used for CMD
        1 object used for CONN_ID
        1 objects used per register mapped
        1 object used for each safe data block CRC

        Args:
            dictionary_map: The dictionary map to validate.
            safe_data_blocks: The list of safe data blocks to validate.
        """
        n_crcs = len(safe_data_blocks)  # One CRC per safe data block
        n_registers = len(dictionary_map._items)

        total_objects = 1 + n_registers + n_crcs + 1  # CMD, registers, CRCs, CONN_ID
        if total_objects > self.__MAX_FRAME_OBJECTS:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.OBJECTS_IN_FRAME,
                    exception=f"Total objects in frame exceeds limit: {total_objects} > {self.__MAX_FRAME_OBJECTS}",
                )
            )

    @override
    def _validate(self, dictionary_map: FSoEDictionaryMap) -> None:
        safe_data_blocks = self._safe_data_blocks_from_dictionary_map(dictionary_map)
        self._validate_safe_data_blocks_size(safe_data_blocks)
        self._validate_objects_in_frame(dictionary_map, safe_data_blocks)


class FSoEDictionaryMapValidator:
    """Validator for FSoE Dictionary Maps.

    Validates that the dictionary map follows the rules for FSoE frame construction.
    """

    def __init__(self) -> None:
        """Initialize the FSoEDictionaryMapValidator."""
        self._rule_to_validators: dict[FSoEFrameRules, FSoEFrameRuleValidator] = {
            FSoEFrameRules.SAFE_DATA_BLOCKS_VALID: SafeDataBlocksValidator(),
        }
        self._exceptions: dict[FSoEFrameRules, list[InvalidFSoEFrameRule]] = {}
        self.__validated: bool = False

    @property
    def exceptions(self) -> dict[FSoEFrameRules, list[InvalidFSoEFrameRule]]:
        """Validation exceptions.

        Returns:
            Dictionary of validation exceptions raised during the validation process.
        """
        return self._exceptions

    def reset(self) -> None:
        """Reset the validator state."""
        for validator in self._rule_to_validators.values():
            validator.reset()
        self._exceptions = {}
        self.__validated = False

    def validate_dictionary_map_fsoe_frame_rules(
        self, dictionary_map: FSoEDictionaryMap
    ) -> dict[FSoEFrameRules, list[InvalidFSoEFrameRule]]:
        """Validate that the FSoE dictionary map follows FSoE frame construction rules.

        Args:
            dictionary_map: The dictionary map to validate.

        Returns:
            Dictionary of validation errors for the FSoE frame.
        """
        if self.__validated:
            logger.warning("Validation already performed, returning cached exceptions.")
            return self.exceptions
        for rule, validator in self._rule_to_validators.items():
            rule_exceptions = validator.validate(dictionary_map)
            if len(rule_exceptions):
                self._exceptions[rule] = rule_exceptions
        self.__validated = True
        return self.exceptions

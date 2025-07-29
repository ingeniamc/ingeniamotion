from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ingenialogger import get_logger
from typing_extensions import override

from ingeniamotion.fsoe_master.fsoe import FSoEDictionaryItem, FSoEDictionaryMap
from ingeniamotion.fsoe_master.maps import PDUMaps

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

    def __init__(self, rules: list[FSoEFrameRules]) -> None:
        self._exceptions: dict[FSoEFrameRules, Optional[InvalidFSoEFrameRule]] = dict.fromkeys(
            rules, None
        )
        self.__validated: bool = False
        self.rules: list[FSoEFrameRules] = rules

    @property
    def is_valid(self) -> bool:
        """Check if the validation has been performed and if there are no exceptions.

        Returns:
            True if validation has been performed and no exceptions were raised, False otherwise.
        """
        if not self.__validated:
            logger.warning("Validation not performed yet, cannot determine validity.")
            return False
        has_exceptions = any(exception is not None for exception in self._exceptions.values())
        return not has_exceptions

    @abstractmethod
    def _validate(self, dictionary_map: FSoEDictionaryMap) -> None:
        raise NotImplementedError

    def validate(
        self, dictionary_map: FSoEDictionaryMap
    ) -> dict[FSoEFrameRules, InvalidFSoEFrameRule]:
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
        self._exceptions = {}
        self.__validated = False


class SafeDataBlocksValidator(FSoEFrameRuleValidator):
    """Validator for safe data blocks rule: 1-8 blocks, each 16-bit.

    If the frame contains only one block, it may be either 8 bits or 16 bits.

    Each safe data block is followed by a CRC_N, where N is the block index starting from 0.
    """

    __MAX_FRAME_OBJECTS: int = 45

    def __init__(self):
        super().__init__(
            rules=[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID, FSoEFrameRules.OBJECTS_IN_FRAME]
        )

    @staticmethod
    def __get_bits_in_data_block(
        items: list[tuple[Optional[int], Optional["FSoEDictionaryItem"]]],
    ) -> int:
        slot_size_bits = 0
        for bits_in_slot, item in items:
            if bits_in_slot is not None:
                slot_size_bits += bits_in_slot
            else:
                slot_size_bits += item.bits if item else 0
        return slot_size_bits

    def _validate_safe_data_blocks_size(
        self,
        safe_data_blocks: list[
            tuple[int, list[tuple[Optional[int], Optional["FSoEDictionaryItem"]]]]
        ],
    ) -> None:
        """Validate the size of safe data blocks in the dictionary map.

        Note:
            The only way in which the safe data blocks can have invalid size is if there is a bug in
            the PDUMaps._generate_slot_structure method, which should always return safe data blocks
            with the correct size.

        Args:
            dictionary_map: The dictionary map to validate.
            safe_data_blocks: The list of safe data blocks to validate.
        """
        n_safe_data_blocks = len(safe_data_blocks)

        if n_safe_data_blocks == 0:
            self._exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID] = InvalidFSoEFrameRule(
                rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                exception="No safe data blocks found in PDO map",
            )
            return

        # Frames may contain 1 to 8 blocks of safe data (payload)
        if n_safe_data_blocks < 1 or n_safe_data_blocks > 8:
            self._exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID] = InvalidFSoEFrameRule(
                rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                exception=f"Expected 1-8 safe data blocks, found {n_safe_data_blocks}",
            )
            return

        # Validate each safe data block
        for data_slot_i, slot_items in safe_data_blocks:
            slot_size_bits = SafeDataBlocksValidator.__get_bits_in_data_block(slot_items)
            # If the frame contains only one block, it may be either 8 bits or 16 bits
            if n_safe_data_blocks == 1:
                # It can be smaller -> it will be padded to 16 bits when creating the PDO frame
                if slot_size_bits > 16:
                    self._exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID] = InvalidFSoEFrameRule(
                        rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                        exception="Single safe data block must be 16 bits or less "
                        f"(completed with padding), found {slot_size_bits}",
                        position=data_slot_i,
                    )
                    return
            # Each safe data block must be 16 bits
            elif data_slot_i != n_safe_data_blocks - 1:
                if slot_size_bits != 16:
                    self._exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID] = InvalidFSoEFrameRule(
                        rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                        exception=f"Safe data block {data_slot_i} must be 16 bits, "
                        f"found {slot_size_bits}",
                        position=data_slot_i,
                    )
                    return
            # It can be smaller, because it will be padded to 16 bits when creating the PDO frame
            elif slot_size_bits > 16:
                self._exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID] = InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                    exception=f"Safe data block {data_slot_i} must be 16 bits, "
                    f"found {slot_size_bits}",
                    position=data_slot_i,
                )
                return
            # It can be smaller, because it will be padded to 16 bits when creating the PDO frame
            elif slot_size_bits > 16:
                self._exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID] = InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                    exception=f"Last safe data block {data_slot_i} must be 16 bits or less "
                    f"(completed with padding), found {slot_size_bits}",
                    position=data_slot_i,
                )
                return

    def _validate_objects_in_frame(
        self,
        dictionary_map: FSoEDictionaryMap,
        safe_data_blocks: list[
            tuple[int, list[tuple[Optional[int], Optional["FSoEDictionaryItem"]]]]
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

        n_objects = 1 + n_registers + n_crcs + 1  # CMD, registers, CRCs, CONN_ID
        if n_objects > self.__MAX_FRAME_OBJECTS:
            self._exceptions[FSoEFrameRules.OBJECTS_IN_FRAME] = InvalidFSoEFrameRule(
                rule=FSoEFrameRules.OBJECTS_IN_FRAME,
                exception=(
                    "Total objects in frame exceeds limit: "
                    f"{n_objects} > {self.__MAX_FRAME_OBJECTS}"
                ),
                position=None,
            )

    @override
    def _validate(self, dictionary_map: FSoEDictionaryMap) -> None:
        safe_data_blocks = list(
            PDUMaps._generate_slot_structure(dictionary_map, PDUMaps._PDUMaps__SLOT_WIDTH)
        )
        self._validate_safe_data_blocks_size(safe_data_blocks)
        self._validate_objects_in_frame(dictionary_map, safe_data_blocks)


class FSoEDictionaryMapValidator:
    """Validator for FSoE Dictionary Maps.

    Validates that the dictionary map follows the rules for FSoE frame construction.
    """

    def __init__(self) -> None:
        """Initialize the FSoEDictionaryMapValidator."""
        self._validators: list[FSoEFrameRuleValidator] = [SafeDataBlocksValidator()]
        self._exceptions: dict[FSoEFrameRules, InvalidFSoEFrameRule] = {}
        self._validated_rules: list[FSoEFrameRules] = []

    @property
    def exceptions(self) -> dict[FSoEFrameRules, InvalidFSoEFrameRule]:
        """Validation exceptions.

        Returns:
            Dictionary of validation exceptions raised during the validation process.
        """
        return self._exceptions

    def reset(self) -> None:
        """Reset the validator state."""
        for validator in self._validators:
            validator.reset()
        self._exceptions = {}
        self._validated_rules = []

    def validate_dictionary_map_fsoe_frame_rules(
        self, dictionary_map: FSoEDictionaryMap
    ) -> dict[FSoEFrameRules, InvalidFSoEFrameRule]:
        """Validate that the FSoE dictionary map follows FSoE frame construction rules.

        Args:
            dictionary_map: The dictionary map to validate.

        Returns:
            Dictionary of validation errors for the FSoE frame.
        """
        if self._validated_rules:
            logger.warning("Validation already performed, returning cached exceptions.")
            return self.exceptions
        for validator in self._validators:
            exceptions = validator.validate(dictionary_map)
            self._validated_rules.extend(validator.rules)
            for rule in validator.rules:
                if exceptions[rule] is not None:
                    self._exceptions[rule] = exceptions[rule]
        return self.exceptions

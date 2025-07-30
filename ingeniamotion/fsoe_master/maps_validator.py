from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ingenialogger import get_logger
from typing_extensions import override

from ingeniamotion.fsoe_master.fsoe import (
    FSoEDictionaryItem,
    FSoEDictionaryItemOutput,
    FSoEDictionaryMap,
)
from ingeniamotion.fsoe_master.maps import PDUMaps
from ingeniamotion.fsoe_master.safety_functions import STOFunction

logger = get_logger(__name__)


class FSoEFrameRules(Enum):
    """FSoE frame rules."""

    SAFE_DATA_BLOCKS_VALID = (
        "Frame must contain 1-8 blocks of safe data, each 16-bit (except single block may be 8-bit)"
    )
    OBJECTS_IN_FRAME = "A frame can contain up to 45 objects in total"
    PADDING_BLOCKS_VALID = "Padding blocks may range from 1 to 16 bits"
    OBJECTS_ALIGNED = "16-bit and larger objects must be word-aligned within the payload"
    STO_COMMAND_FIRST = (
        "The STO command must always be mapped to the first position in the Safe Outputs payload"
    )


@dataclass
class InvalidFSoEFrameRule:
    """Information about an invalid FSoE frame rule."""

    rule: FSoEFrameRules  # The rule that was violated
    exception: str  # Description of the error
    position: Optional[list[int]] = (
        None  # Dictionary item position in bits where the rule is invalid
    )


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
        self.__validated: bool = False
        self.rules: list[FSoEFrameRules] = rules
        self._exceptions: dict[FSoEFrameRules, Optional[InvalidFSoEFrameRule]] = dict.fromkeys(
            self.rules, None
        )

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
    ) -> dict[FSoEFrameRules, Optional[InvalidFSoEFrameRule]]:
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
        self.__validated = False
        self._exceptions = dict.fromkeys(self.rules, None)


class SafeDataBlocksValidator(FSoEFrameRuleValidator):
    """Validator for safe data blocks rule: 1-8 blocks, each 16-bit.

    If the frame contains only one block, it may be either 8 bits or 16 bits.

    Each safe data block is followed by a CRC_N, where N is the block index starting from 0.
    """

    __MAX_FRAME_OBJECTS: int = 45

    def __init__(self) -> None:
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

    @staticmethod
    def __get_items_position_in_data_block(
        items: list[tuple[Optional[int], Optional["FSoEDictionaryItem"]]],
    ) -> Optional[list[int]]:
        positions = [item.position_bits for _, item in items if item is not None]
        if not positions:
            return None
        return positions

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
                        position=SafeDataBlocksValidator.__get_items_position_in_data_block(
                            slot_items
                        ),
                    )
                    return
            # Each safe data block must be 16 bits
            elif data_slot_i != n_safe_data_blocks - 1:
                if slot_size_bits != 16:
                    self._exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID] = InvalidFSoEFrameRule(
                        rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                        exception=f"Safe data block {data_slot_i} must be 16 bits, "
                        f"found {slot_size_bits}",
                        position=SafeDataBlocksValidator.__get_items_position_in_data_block(
                            slot_items
                        ),
                    )
                    return
            # It can be smaller, because it will be padded to 16 bits when creating the PDO frame
            elif slot_size_bits > 16:
                self._exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID] = InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                    exception=f"Safe data block {data_slot_i} must be 16 bits, "
                    f"found {slot_size_bits}",
                    position=SafeDataBlocksValidator.__get_items_position_in_data_block(slot_items),
                )
                return
            # It can be smaller, because it will be padded to 16 bits when creating the PDO frame
            elif slot_size_bits > 16:
                self._exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID] = InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                    exception=f"Last safe data block {data_slot_i} must be 16 bits or less "
                    f"(completed with padding), found {slot_size_bits}",
                    position=SafeDataBlocksValidator.__get_items_position_in_data_block(slot_items),
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

        Note:
            This rule will never fail if _validate_safe_data_blocks_size is called first
            If the safe data blocks are valid, then the number of objects in the frame
            will always be valid as well.
            If not, then there will be an overflow error when trying to write the PDU.

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
            PDUMaps._generate_slot_structure(dictionary_map, PDUMaps._PDUMaps__SLOT_WIDTH)  # type: ignore[attr-defined]
        )
        self._validate_safe_data_blocks_size(safe_data_blocks)
        self._validate_objects_in_frame(dictionary_map, safe_data_blocks)


class PaddingBlockValidator(FSoEFrameRuleValidator):
    """Validator for padding blocks in FSoE frames.

    Validates that the size of padding blocks range from 1 to 16 bits.
    """

    def __init__(self) -> None:
        super().__init__(rules=[FSoEFrameRules.PADDING_BLOCKS_VALID])

    @override
    def _validate(self, dictionary_map: FSoEDictionaryMap) -> None:
        for item in dictionary_map:
            # Not a padding block
            if item.item is not None:
                continue
            if item.bits < 1 or item.bits > 16:
                self._exceptions[FSoEFrameRules.PADDING_BLOCKS_VALID] = InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.PADDING_BLOCKS_VALID,
                    exception=f"Padding block size must range from 1 to 16 bits, found {item.bits}",
                    position=[item.position_bits],
                )
                return


class ObjectsAlignedValidator(FSoEFrameRuleValidator):
    """Validator for object alignment in FSoE frames.

    Validates that 16-bit and larger objects are word-aligned within the payload.
    """

    def __init__(self) -> None:
        super().__init__(rules=[FSoEFrameRules.OBJECTS_ALIGNED])

    @override
    def _validate(self, dictionary_map: FSoEDictionaryMap) -> None:
        for item in dictionary_map:
            if item.bits >= 16 and item.position_bits % 16 != 0:
                self._exceptions[FSoEFrameRules.OBJECTS_ALIGNED] = InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.OBJECTS_ALIGNED,
                    exception=(
                        f"Object must be word-aligned, found at bit position {item.position_bits}"
                    ),
                    position=[item.position_bits],
                )
                return


class STOCommandFirstValidator(FSoEFrameRuleValidator):
    """Validator for the STO command position in FSoE frames.

    Validates that the STO command is always mapped to the first position in Safe Outputs.
    """

    def __init__(self) -> None:
        super().__init__(rules=[FSoEFrameRules.STO_COMMAND_FIRST])

    @override
    def _validate(self, dictionary_map: FSoEDictionaryMap) -> None:
        if FSoEDictionaryItemOutput not in dictionary_map.item_types_accepted:
            return

        first_item = dictionary_map._items[0]
        if first_item.item is None or first_item.item.name != STOFunction.COMMAND_UID:
            self._exceptions[FSoEFrameRules.STO_COMMAND_FIRST] = InvalidFSoEFrameRule(
                rule=FSoEFrameRules.STO_COMMAND_FIRST,
                exception="STO command must be mapped to the first position in Safe Outputs",
                position=[first_item.position_bits],
            )


class FSoEDictionaryMapValidator:
    """Validator for FSoE Dictionary Maps.

    Validates that the dictionary map follows the rules for FSoE frame construction.
    """

    def __init__(self) -> None:
        """Initialize the FSoEDictionaryMapValidator."""
        self.__validators: list[FSoEFrameRuleValidator] = [
            SafeDataBlocksValidator(),
            PaddingBlockValidator(),
            ObjectsAlignedValidator(),
            STOCommandFirstValidator(),
        ]
        self._validated_rules: dict[FSoEFrameRules, bool] = {}
        self._exceptions: dict[FSoEFrameRules, InvalidFSoEFrameRule] = {}

    @property
    def exceptions(self) -> dict[FSoEFrameRules, InvalidFSoEFrameRule]:
        """Validation exceptions.

        Returns:
            Dictionary of validation exceptions raised during the validation process.
        """
        return self._exceptions

    def reset(self) -> None:
        """Reset the validator state."""
        for validator in self.__validators:
            validator.reset()
        self._exceptions = {}
        self._validated_rules = {}

    def is_rule_valid(self, rule: FSoEFrameRules) -> bool:
        """Check if a specific rule has been validated and is valid.

        Args:
            rule: The FSoE frame rule to check.

        Returns:
            True if the rule is valid, False otherwise.
        """
        if rule not in self._validated_rules:
            logger.warning(f"Rule {rule} has not been validated yet.")
            return False
        return self._validated_rules[rule]

    def validate_dictionary_map_fsoe_frame_rules(
        self, dictionary_map: FSoEDictionaryMap, rules: Optional[list[FSoEFrameRules]] = None
    ) -> dict[FSoEFrameRules, InvalidFSoEFrameRule]:
        """Validate that the FSoE dictionary map follows FSoE frame construction rules.

        Args:
            dictionary_map: The dictionary map to validate.
            rules: Optional list of specific rules to validate. If None, all rules are validated.

        Returns:
            Dictionary of validation errors for the FSoE frame.
        """
        rules_to_validate = set(rules) if rules is not None else list(FSoEFrameRules)
        for rule in rules_to_validate:
            if rule in self._validated_rules:
                logger.warning("Validation already performed, returning cached exceptions.")
                continue
            for validator in self.__validators:
                if rule not in validator.rules:
                    continue
                exceptions = validator.validate(dictionary_map)
                for evaluated_rule in validator.rules:
                    self._validated_rules[evaluated_rule] = validator.is_valid
                    if exceptions[evaluated_rule] is not None:
                        self._exceptions[evaluated_rule] = exceptions[evaluated_rule]  # type: ignore[assignment]
                # Only one validator can contain the rule
                break
        return self.exceptions

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from ingenialogger import get_logger
from typing_extensions import override

from ingeniamotion.fsoe_master.frame import FSoEFrame
from ingeniamotion.fsoe_master.fsoe import (
    FSoEDictionaryMap,
    FSoEDictionaryMappedItem,
    align_bits,
)
from ingeniamotion.fsoe_master.safety_functions import STOFunction

logger = get_logger(__name__)


class FSoEFrameRules(Enum):
    """FSoE frame rules."""

    OBJECTS_ALIGNED = auto()
    OBJECTS_IN_FRAME = auto()
    STO_COMMAND_FIRST = auto()
    SAFE_DATA_BLOCKS_VALID = auto()
    OBJECTS_SPLIT_RESTRICTED = auto()


@dataclass(frozen=True)
class InvalidFSoEFrameRule:
    """Information about an invalid FSoE frame rule."""

    rule: FSoEFrameRules  # The rule that was violated
    exception: str  # Description of the error
    items: list[FSoEDictionaryMappedItem]  # Dictionary item that caused the rule to be invalid


@dataclass(frozen=True)
class FSoEFrameRuleValidatorOutput:
    """Output of FSoE frame rule validation.

    Contains the validation result and any exceptions raised during validation.
    """

    rules: list[FSoEFrameRules]
    """List of FSoE frame rules that were validated."""
    exceptions: dict[FSoEFrameRules, InvalidFSoEFrameRule]
    """Exceptions raised during validation.

    If no exception was raised for a rule, it won't be present in the dictionary.
    """

    def is_rule_valid(self, rule: FSoEFrameRules) -> bool:
        """Check if a specific rule is valid.

        Args:
            rule: The FSoE frame rule to check.

        Returns:
            True if the rule is valid, False otherwise.

        Raises:
            ValueError: If the rule is not in the validated rules list.
        """
        if rule not in self.rules:
            raise ValueError(f"Rule {rule} is not in the validated rules list.")
        return rule not in self.exceptions


class FSoEFrameConstructionError(Exception):
    """FSoE frame construction exceptions."""

    _ERROR_MESSAGE: str = "Map validation failed with errors"

    def __init__(self, validation_errors: FSoEFrameRuleValidatorOutput) -> None:
        """Initialize with validation errors.

        Args:
            validation_errors: The validation output containing the rules and exceptions.
        """
        error_details = []
        for idx, (rule, exception) in enumerate(validation_errors.exceptions.items(), 1):
            error_detail = f"  {idx}. Rule: {rule}\n"
            error_detail += f"     Error: {exception.exception}\n"
            error_details.append(error_detail)
        full_message = f"{self._ERROR_MESSAGE}:\n" + "\n".join(error_details)
        super().__init__(full_message)


class FSoEFrameRuleValidator(ABC):
    """Base class for FSoE frame rule validators.

    Provides a common interface for validating FSoE frame rules.
    """

    def __init__(self, rules: list[FSoEFrameRules]) -> None:
        self.rules: list[FSoEFrameRules] = rules

    @abstractmethod
    def _validate(
        self, dictionary_map: FSoEDictionaryMap, rules: list[FSoEFrameRules]
    ) -> FSoEFrameRuleValidatorOutput:
        raise NotImplementedError

    def validate(
        self, dictionary_map: FSoEDictionaryMap, rules: Optional[list[FSoEFrameRules]] = None
    ) -> FSoEFrameRuleValidatorOutput:
        """Validate the FSoE frame rules.

        Args:
            dictionary_map: The dictionary map to validate.
            rules: Optional list of specific rules to validate. If None, all rules are validated.

        Returns:
            The output of the validation containing the rules and exceptions.

        Raises:
            ValueError: If no valid rules are provided for evaluation.
        """
        eval_rules: list[FSoEFrameRules] = (
            self.rules if rules is None else [rule for rule in rules if rule in self.rules]
        )
        if not len(eval_rules):
            raise ValueError("No valid rules to evaluate. Please provide a valid list of rules.")
        return self._validate(dictionary_map, eval_rules)


class SafeDataBlocksValidator(FSoEFrameRuleValidator):
    """Validator for safe data blocks rule: 1-8 blocks, each 16-bit.

    If the frame contains only one block, it may be either 8 bits or 16 bits.

    Each safe data block is followed by a CRC_N, where N is the block index starting from 0.
    """

    __MAX_FRAME_OBJECTS: int = 45

    def __init__(self) -> None:
        super().__init__(
            rules=[
                FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                FSoEFrameRules.OBJECTS_IN_FRAME,
                FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED,
            ]
        )

    @staticmethod
    def __get_bits_in_data_block(
        items: list[tuple[Optional[int], Optional["FSoEDictionaryMappedItem"]]],
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
            tuple[int, list[tuple[Optional[int], Optional["FSoEDictionaryMappedItem"]]]]
        ],
    ) -> dict[FSoEFrameRules, InvalidFSoEFrameRule]:
        """Validate the size of safe data blocks in the dictionary map.

        Note:
            The only way in which the safe data blocks can have invalid size is if there is a bug in
            the FSoEFrame.generate_slot_structure method, which should always return safe data
            blocks with the correct size.

        Args:
            dictionary_map: The dictionary map to validate.
            safe_data_blocks: The list of safe data blocks to validate.

        Returns:
            Dictionary containing any validation errors found.
        """
        n_safe_data_blocks = len(safe_data_blocks)

        # PDO map will be valid if the map is empty (check `test_empty_map_8_bits` test)
        if n_safe_data_blocks == 0:
            return {}

        # Frames may contain 1 to 8 blocks of safe data (payload)
        if n_safe_data_blocks > 8:
            return {
                FSoEFrameRules.SAFE_DATA_BLOCKS_VALID: InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                    exception=f"Expected 1-8 safe data blocks, found {n_safe_data_blocks}",
                    items=[
                        item
                        for _, slot_items in safe_data_blocks
                        for _, item in slot_items
                        if item is not None
                    ],
                )
            }
        # Validate each safe data block
        for data_slot_i, slot_items in safe_data_blocks:
            slot_size_bits = SafeDataBlocksValidator.__get_bits_in_data_block(slot_items)
            # If the frame contains only one block, it may be either 8 bits or 16 bits
            if n_safe_data_blocks == 1:
                # It can be smaller -> it will be padded to 16 bits when creating the PDO frame
                if slot_size_bits > 16:
                    return {
                        FSoEFrameRules.SAFE_DATA_BLOCKS_VALID: InvalidFSoEFrameRule(
                            rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                            exception="Single safe data block must be 16 bits or less "
                            f"with padding. Found {slot_size_bits}",
                            items=[item for _, item in slot_items if item is not None],
                        )
                    }
            # Each safe data block must be 16 bits
            elif data_slot_i != n_safe_data_blocks - 1:
                if slot_size_bits != 16:
                    return {
                        FSoEFrameRules.SAFE_DATA_BLOCKS_VALID: InvalidFSoEFrameRule(
                            rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                            exception=f"Safe data block {data_slot_i} must be 16 bits. "
                            f"Found {slot_size_bits}",
                            items=[item for _, item in slot_items if item is not None],
                        )
                    }
            # It can be smaller, because it will be padded to 16 bits when creating the PDO frame
            elif slot_size_bits > 16:
                return {
                    FSoEFrameRules.SAFE_DATA_BLOCKS_VALID: InvalidFSoEFrameRule(
                        rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                        exception=f"Last safe data block {data_slot_i} must be 16 bits or less "
                        f"with padding. Found {slot_size_bits}",
                        items=[item for _, item in slot_items if item is not None],
                    )
                }
        return {}

    def _validate_objects_in_frame(
        self,
        dictionary_map: FSoEDictionaryMap,
        safe_data_blocks: list[
            tuple[int, list[tuple[Optional[int], Optional["FSoEDictionaryMappedItem"]]]]
        ],
    ) -> dict[FSoEFrameRules, InvalidFSoEFrameRule]:
        """Validate the number of objects in the frame.

        1 object used for CMD
        1 object used for CONN_ID
        1 objects used per register mapped
        1 object used for each safe data block CRC

        Args:
            dictionary_map: The dictionary map to validate.
            safe_data_blocks: The list of safe data blocks to validate.

        Returns:
            Dictionary containing any validation errors found.
        """
        n_crcs = len(safe_data_blocks)  # One CRC per safe data block
        n_registers = len(dictionary_map)

        n_objects = 1 + n_registers + n_crcs + 1  # CMD, registers, CRCs, CONN_ID
        if n_objects > self.__MAX_FRAME_OBJECTS:
            return {
                FSoEFrameRules.OBJECTS_IN_FRAME: InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.OBJECTS_IN_FRAME,
                    exception=(
                        "Total objects in frame exceeds limit: "
                        f"{n_objects} > {self.__MAX_FRAME_OBJECTS}"
                    ),
                    items=[item for item in dictionary_map if item is not None],
                )
            }
        return {}

    def _validate_size_of_split_objects(
        self,
        safe_data_blocks: list[
            tuple[int, list[tuple[Optional[int], Optional["FSoEDictionaryMappedItem"]]]]
        ],
    ) -> dict[FSoEFrameRules, InvalidFSoEFrameRule]:
        """Validate that only 32-bit objects may be split across multiple safe data blocks.

        Args:
            dictionary_map: The dictionary map to validate.
            safe_data_blocks: The list of safe data blocks to validate.

        Returns:
            Dictionary containing any validation errors found.
        """
        for data_slot_i, slot_items in safe_data_blocks:
            for bits_in_slot, item in slot_items:
                # bits_in_slot == None and bits_in_slot == item.bits:
                #      the item is fully contained in the current safe data block
                # item == None: the item is a virtual padding block,
                # which fits in the current safe data block
                # item.item == None: the item is a padding block, it can be split
                if (
                    bits_in_slot is None
                    or item is None
                    or bits_in_slot == item.bits
                    or item.item is None
                ):
                    continue
                # If the item != 32 bits, it cannot be split across multiple safe data blocks
                # 16 bit is checked by ObjectsAlignedValidator
                if item.bits < 16:
                    return {
                        FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED: InvalidFSoEFrameRule(
                            rule=FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED,
                            exception=(
                                f"Make sure that 8 bit objects belong to the same data block. "
                                f"Data slot {data_slot_i} contains split object {item.item.name}."
                            ),
                            items=[item],
                        )
                    }
        return {}

    @override
    def _validate(
        self, dictionary_map: FSoEDictionaryMap, rules: list[FSoEFrameRules]
    ) -> FSoEFrameRuleValidatorOutput:
        safe_data_blocks = list(
            FSoEFrame.generate_slot_structure(dictionary_map, FSoEFrame._FSoEFrame__SLOT_WIDTH)  # type: ignore[attr-defined]
        )

        exceptions: dict[FSoEFrameRules, InvalidFSoEFrameRule] = {}
        if FSoEFrameRules.SAFE_DATA_BLOCKS_VALID in rules:
            exceptions.update(self._validate_safe_data_blocks_size(safe_data_blocks))
        if FSoEFrameRules.OBJECTS_IN_FRAME in rules:
            exceptions.update(self._validate_objects_in_frame(dictionary_map, safe_data_blocks))
        if FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED in rules:
            exceptions.update(self._validate_size_of_split_objects(safe_data_blocks))
        return FSoEFrameRuleValidatorOutput(rules=rules, exceptions=exceptions)


class ObjectsAlignedValidator(FSoEFrameRuleValidator):
    """Validator for object alignment in FSoE frames.

    Validates that 16-bit and larger objects are word-aligned within the payload.
    """

    def __init__(self) -> None:
        super().__init__(rules=[FSoEFrameRules.OBJECTS_ALIGNED])

    @override
    def _validate(
        self, dictionary_map: FSoEDictionaryMap, rules: list[FSoEFrameRules]
    ) -> FSoEFrameRuleValidatorOutput:
        exceptions: dict[FSoEFrameRules, InvalidFSoEFrameRule] = {}
        for item in dictionary_map:
            # Ignore paddings for alignment check
            if item.item is None:
                continue
            if item.bits >= 16 and item.position_bits % 16 != 0:
                next_alignment = align_bits(item.position_bits, 16)
                exceptions[FSoEFrameRules.OBJECTS_ALIGNED] = InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.OBJECTS_ALIGNED,
                    exception=(
                        "Objects larger than 16-bit must be word-aligned. "
                        f"Object '{item.item.name}' found at position {item.position_bits}, "
                        f"next alignment is at {next_alignment}."
                    ),
                    items=[item],
                )
        return FSoEFrameRuleValidatorOutput(rules=rules, exceptions=exceptions)


class STOCommandFirstValidator(FSoEFrameRuleValidator):
    """Validator for the STO command position in FSoE frames.

    Validates that the STO command is always mapped to the first position.
    """

    def __init__(self) -> None:
        super().__init__(rules=[FSoEFrameRules.STO_COMMAND_FIRST])

    @override
    def _validate(
        self, dictionary_map: FSoEDictionaryMap, rules: list[FSoEFrameRules]
    ) -> FSoEFrameRuleValidatorOutput:
        exceptions: dict[FSoEFrameRules, InvalidFSoEFrameRule] = {}
        if not len(dictionary_map):
            exceptions[FSoEFrameRules.STO_COMMAND_FIRST] = InvalidFSoEFrameRule(
                rule=FSoEFrameRules.STO_COMMAND_FIRST,
                exception="Map is empty, STO command must be mapped to the first position",
                items=[],
            )
        else:
            first_item = dictionary_map._items[0]
            if first_item.item is None or first_item.item.name != STOFunction.COMMAND_UID:
                exceptions[FSoEFrameRules.STO_COMMAND_FIRST] = InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.STO_COMMAND_FIRST,
                    exception="STO command must be mapped to the first position",
                    items=[first_item] if first_item is not None else [],
                )
        return FSoEFrameRuleValidatorOutput(rules=rules, exceptions=exceptions)


class FSoEDictionaryMapValidator:
    """Validator for FSoE Dictionary Maps.

    Validates that the dictionary map follows the rules for FSoE frame construction.
    """

    def __init__(self) -> None:
        """Initialize the FSoEDictionaryMapValidator."""
        self.__validators: list[FSoEFrameRuleValidator] = [
            SafeDataBlocksValidator(),
            ObjectsAlignedValidator(),
            STOCommandFirstValidator(),
        ]

    def validate_dictionary_map_fsoe_frame_rules(
        self,
        dictionary_map: FSoEDictionaryMap,
        rules: Optional[list[FSoEFrameRules]] = None,
        raise_exceptions: bool = False,
    ) -> FSoEFrameRuleValidatorOutput:
        """Validate that the FSoE dictionary map follows FSoE frame construction rules.

        Args:
            dictionary_map: The dictionary map to validate.
            rules: List of specific rules to validate. If None, all rules are validated.
            raise_exceptions: If True, raises an exception if any rule is invalid.
                If False, returns the validation output with exceptions. Defaults to False.

        Returns:
            The output of the validation containing the rules and exceptions.

        Raises:
            FSoEFrameConstructionError: if raise_exceptions is True and any rule is invalid.
        """
        rules_to_validate = list(set(rules)) if rules is not None else list(FSoEFrameRules)
        exceptions: dict[FSoEFrameRules, InvalidFSoEFrameRule] = {}
        for validator in self.__validators:
            if all(rule not in validator.rules for rule in rules_to_validate):
                continue
            output = validator.validate(dictionary_map, rules_to_validate)
            exceptions.update(output.exceptions)

        result = FSoEFrameRuleValidatorOutput(rules=rules_to_validate, exceptions=exceptions)
        if raise_exceptions and result.exceptions:
            raise FSoEFrameConstructionError(validation_errors=result)
        return result

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ingenialink.pdo import PDOMap, PDOMapItem
from ingenialogger import get_logger
from typing_extensions import override

from ingeniamotion.fsoe_master.frame_elements import FSoEFrameElements

logger = get_logger(__name__)


class FSoEFrameRules(Enum):
    """FSoE frame rules."""

    CMD_FIELD_FIRST = "CMD field must be the first item in the PDO map"
    CONN_ID_FIELD_LAST = "ConnID field must be the last item in the PDO map"
    SAFE_DATA_BLOCKS_VALID = (
        "Frame must contain 1-8 blocks of safe data, each 16-bit (except single block may be 8-bit)"
    )


@dataclass
class InvalidFSoEFrameRule:
    """Information about an invalid FSoE frame rule."""

    rule: FSoEFrameRules  # The rule that was violated
    exception: str  # Description of the error
    suggestion: Optional[str] = None  # Suggestion for fixing the error
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
                if error.suggestion:
                    error_detail += f"     Suggestion: {error.suggestion}\n"
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
    def _validate(self, pdo_map: PDOMap, frame_elements: FSoEFrameElements) -> None:
        raise NotImplementedError("Subclasses must implement this method.")

    def validate(
        self, pdo_map: PDOMap, frame_elements: FSoEFrameElements
    ) -> list[InvalidFSoEFrameRule]:
        """Validate the FSoE frame rules.

        Args:
            pdo_map: The PDO map to validate.
            frame_elements: Frame elements for the specific frame type

        Returns:
            List of validation errors.
        """
        if self.__validated:
            logger.warning("Validation already performed, returning cached exceptions.")
            return self._exceptions
        self._validate(pdo_map, frame_elements)
        self.__validated = True
        return self._exceptions

    def reset(self) -> None:
        """Reset the validator state."""
        self._exceptions = []
        self.__validated = False


class CmdFieldFirstValidator(FSoEFrameRuleValidator):
    """Validator for the rule: Each FSoE frame must begin with a CMD field."""

    @override
    def _validate(self, pdo_map: PDOMap, frame_elements: FSoEFrameElements) -> None:
        if not pdo_map.items:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.CMD_FIELD_FIRST,
                    exception="PDO map is empty - no CMD field found",
                )
            )
            return

        first_item = pdo_map.items[0]

        # Check if first item is the CMD field
        if first_item.register.identifier != frame_elements.command_uid:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.CMD_FIELD_FIRST,
                    exception=f"First PDO item must be CMD field '{frame_elements.command_uid}', "
                    f"but found '{first_item.register.identifier}'",
                    suggestion="Ensure the first item in the PDO map is the CMD field.",
                )
            )


class ConnIDFieldLastValidator(FSoEFrameRuleValidator):
    """Validator for the rule: Each FSoE frame must end with a ConnID field."""

    @override
    def _validate(self, pdo_map: PDOMap, frame_elements: FSoEFrameElements) -> None:
        if not pdo_map.items:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.CONN_ID_FIELD_LAST,
                    exception="PDO map is empty - no CONN_ID field found",
                )
            )
            return

        last_item = pdo_map.items[-1]

        # Check if last item is the CONN_ID field
        if last_item.register.identifier != frame_elements.connection_id_uid:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.CONN_ID_FIELD_LAST,
                    exception="Last PDO item must be CONN_ID field "
                    f"'{frame_elements.connection_id_uid}'"
                    f", but found '{last_item.register.identifier}'",
                    suggestion="Ensure the last item in the PDO map is the CONN_ID field.",
                )
            )


class SafeDataBlocksValidator(FSoEFrameRuleValidator):
    """Validator for safe data blocks rule: 1-8 blocks, each 16-bit.

    If the frame contains only one block, it may be either 8 bits or 16 bits.

    Each safe data block is followed by a CRC_N, where N is the block index starting from 0.
    """

    def _get_safe_data_blocks(
        self, pdo_map: PDOMap, frame_elements: FSoEFrameElements
    ) -> tuple[bool, list[tuple[int, list[PDOMapItem], Optional[PDOMapItem]]]]:
        """Get safe data blocks from the PDO map.

        A frame element consists of:

            [CMD][Safe Data 0][CRC0][Safe Data 1][CRC1][...][Data Slot N][CRCN][Connection ID]

        Therefore, safe data blocks are all items that are not the CMD, CONN_ID, or CRCs.

        Each safety data is a 16-bit block separated by CRCs.

        Returns:
            tuple of exceptions flag and a list of tuples containing the index and PDOMapItems
            that are safe data blocks.
        """
        safe_data_blocks: list[tuple[int, list[PDOMapItem], Optional[PDOMapItem]]] = []
        current_block: list[PDOMapItem] = []
        block_idx = 0

        for item in pdo_map.items:
            if item.register.identifier is None:
                self._exceptions.append(
                    InvalidFSoEFrameRule(
                        rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                        exception="PDO item has no register identifier",
                        suggestion="Ensure all PDO items have valid register identifiers.",
                    )
                )
                return True, []

            # Skip CMD (it's at the beginning)
            # Skip Connection ID (it's at the end)
            if item.register.identifier in (
                frame_elements.command_uid,
                frame_elements.connection_id_uid,
            ):
                continue

            # If the item is a CRC, it indicates the end of a safe data block
            if item.register.identifier.startswith(frame_elements.crcs_prefix):
                if not len(current_block):
                    self._exceptions.append(
                        InvalidFSoEFrameRule(
                            rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                            exception=f"Unexpected CRC item '{item.register.identifier}' "
                            "without preceding safe data block",
                            suggestion="Ensure each CRC is preceded by a safe data block.",
                            position=block_idx,
                        )
                    )
                    return True, []
                if frame_elements.get_crc_uid(block_idx) != item.register.identifier:
                    crc_item = None
                else:
                    crc_item = item
                safe_data_blocks.append((block_idx, current_block, crc_item))
                block_idx += 1
                current_block = []
            else:
                current_block.append(item)

        if len(current_block) > 0:
            safe_data_blocks.append((block_idx, current_block, None))

        return False, safe_data_blocks

    @override
    def _validate(self, pdo_map: PDOMap, frame_elements: FSoEFrameElements) -> None:
        if not pdo_map.items:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                    exception="PDO map is empty - no safe data blocks found",
                )
            )
            return

        exception_retrieving_blocks, safe_data_blocks = self._get_safe_data_blocks(
            pdo_map, frame_elements
        )
        if exception_retrieving_blocks:
            return
        if not safe_data_blocks:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                    exception="No safe data blocks found in PDO map",
                    suggestion="Add safe data items to the frame.",
                )
            )
            return

        # Frames may contain 1 to 8 blocks of safe data (payload)
        n_safe_data_blocks = len(safe_data_blocks)
        if n_safe_data_blocks < 1 or n_safe_data_blocks > 8:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                    exception=f"Expected 1-8 safe data blocks, found {n_safe_data_blocks}",
                    suggestion="Ensure the PDO map contains between 1 and 8 safe data blocks.",
                )
            )
            return

        # Validate each safe data block
        for block_idx, block_items, crc_item in safe_data_blocks:
            # Each safe data block is followed by a CRC_N,
            # where N is the block index starting from 0
            if crc_item is None:
                self._exceptions.append(
                    InvalidFSoEFrameRule(
                        rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                        exception=f"Missing CRC for safe data block {block_idx}",
                        suggestion="Ensure each safe data block is followed by a CRC item.",
                        position=block_idx,
                    )
                )
                return

            block_size_bits = sum(item.size_bits for item in block_items)
            # If the frame contains only one block, it may be either 8 bits or 16 bits
            if n_safe_data_blocks == 1:
                if block_size_bits not in (8, 16):
                    self._exceptions.append(
                        InvalidFSoEFrameRule(
                            rule=FSoEFrameRules.SAFE_DATA_BLOCKS_VALID,
                            exception="Single safe data block must be 8 or 16 bits, "
                            f"found {block_size_bits}",
                            suggestion="Ensure the single safe data block is either 8 or 16 bits.",
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
                            suggestion="Ensure all safe data blocks are 16 bits.",
                            position=block_idx,
                        )
                    )
                    return


class PDOMapValidator:
    """Validator for FSoE PDO Maps.

    Validates that the PDO map follows the rules for FSoE frame construction.
    """

    def __init__(self) -> None:
        """Initialize the PDOMapValidator."""
        self._rule_to_validators: dict[FSoEFrameRules, FSoEFrameRuleValidator] = {
            FSoEFrameRules.CMD_FIELD_FIRST: CmdFieldFirstValidator(),
            FSoEFrameRules.CONN_ID_FIELD_LAST: ConnIDFieldLastValidator(),
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

    def validate_fsoe_frame_rules(
        self, pdo_map: PDOMap, frame_elements: FSoEFrameElements
    ) -> dict[FSoEFrameRules, list[InvalidFSoEFrameRule]]:
        """Validate that the PDO map follows FSoE frame construction rules.

        Args:
            pdo_map: The PDO map to validate.
            frame_elements: Frame elements for the specific frame type

        Returns:
            Dictionary of validation errors for the FSoE frame.
        """
        if self.__validated:
            logger.warning("Validation already performed, returning cached exceptions.")
            return self.exceptions
        for rule, validator in self._rule_to_validators.items():
            rule_exceptions = validator.validate(pdo_map, frame_elements)
            if len(rule_exceptions):
                self._exceptions[rule] = rule_exceptions
        self.__validated = True
        return self.exceptions

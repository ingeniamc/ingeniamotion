from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ingenialink.pdo import PDOMap
from ingenialogger import get_logger
from typing_extensions import override

from ingeniamotion.fsoe_master.frame_elements import FSoEFrameElements

logger = get_logger(__name__)


class FSoEFrameRule(Enum):
    """Enumeration of FSoE frame rules."""

    CMD_FIELD_FIRST = "CMD field must be the first item in the PDO map"


@dataclass
class InvalidFSoEFrameRule:
    """Data class to hold information about an invalid FSoE frame rule."""

    rule: FSoEFrameRule  # The rule that was violated
    error: str  # Description of the error
    suggestion: Optional[str] = None  # Suggestion for fixing the error


class FSoEFrameConstructionError(Exception):
    """FSoE frame construction exceptions."""

    _ERROR_MESSAGE: str = "PDO map validation failed with errors"

    def __init__(self, validation_errors: list[InvalidFSoEFrameRule]):
        """Initialize with validation errors.

        Args:
            validation_errors: List of validation errors to include in the message
        """
        if not validation_errors:
            super().__init__(self._ERROR_MESSAGE)
            return

        # Format each validation error
        error_details = []
        for i, validation_error in enumerate(validation_errors, 1):
            error_detail = (
                f"  {i}. Rule: {validation_error.rule.value}\n     Error: {validation_error.error}"
            )
            if validation_error.suggestion:
                error_detail += f"\n     Suggestion: {validation_error.suggestion}"
            error_details.append(error_detail)

        # Combine base message with formatted errors
        full_message = f"{self._ERROR_MESSAGE}:\n" + "\n".join(error_details)
        super().__init__(full_message)

        # Store the validation errors for programmatic access
        self.validation_errors = validation_errors


class FSoEFrameRuleValidator(ABC):
    """Base class for FSoE frame rule validators.

    Provides a common interface for validating FSoE frame rules.
    """

    def __init__(self):
        self._exceptions: list[InvalidFSoEFrameRule] = []
        self.__validated: bool = False

    @property
    def exceptions(self) -> list[InvalidFSoEFrameRule]:
        """List of validation exceptions.

        Returns:
            List of validation exceptions raised during the validation process.
        """
        if not self.__validated:
            logger.warning("Validation not performed yet, no exceptions available.")
        return self._exceptions

    @property
    def is_valid(self) -> bool:
        """Check if the validation has been performed and if there are no exceptions.

        Returns:
            True if validation has been performed and no exceptions were raised, False otherwise.
        """
        if not self.__validated:
            logger.warning("Validation not performed yet, cannot determine validity.")
            return False
        return not self.exceptions

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
            return self.exceptions
        self._validate(pdo_map, frame_elements)
        self.__validated = True
        return self.exceptions

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
                    rule=FSoEFrameRule.CMD_FIELD_FIRST,
                    error="PDO map is empty - no CMD field found",
                )
            )
            return

        first_item = pdo_map.items[0]

        # Check if first item is the CMD field
        if first_item.register.identifier != frame_elements.command_uid:
            self._exceptions.append(
                InvalidFSoEFrameRule(
                    rule=FSoEFrameRule.CMD_FIELD_FIRST,
                    error=f"First PDO item must be CMD field '{frame_elements.command_uid}', "
                    f"but found '{first_item.register.identifier}'",
                    suggestion="Ensure the first item in the PDO map is the CMD field.",
                )
            )


class PDOMapValidator:
    """Validator for FSoE PDO Maps.

    Validates that the PDO map follows the rules for FSoE frame construction.
    """

    def __init__(self):
        self._rule_validators: list[FSoEFrameRuleValidator] = [CmdFieldFirstValidator()]
        self._exceptions: list[InvalidFSoEFrameRule] = []
        self.__validated: bool = False

    @property
    def exceptions(self) -> list[InvalidFSoEFrameRule]:
        """List of validation exceptions.

        Returns:
            List of validation exceptions raised during the validation process.
        """
        return self._exceptions

    def reset(self) -> None:
        """Reset the validator state."""
        for validator in self._rule_validators:
            validator.reset()
        self._exceptions = []
        self.__validated = False

    def validate_fsoe_frame_rules(
        self, pdo_map: PDOMap, frame_elements: FSoEFrameElements
    ) -> list[InvalidFSoEFrameRule]:
        """Validate that the PDO map follows FSoE frame construction rules.

        Args:
            pdo_map: The PDO map to validate.
            frame_elements: Frame elements for the specific frame type

        Returns:
            List of validation errors for the FSoE frame.
        """
        if self.__validated:
            logger.warning("Validation already performed, returning cached exceptions.")
            return self.exceptions
        for validator in self._rule_validators:
            self._exceptions.extend(validator.validate(pdo_map, frame_elements))
        self.__validated = True
        return self.exceptions

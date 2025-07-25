from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ingenialink.pdo import PDOMap
from ingenialogger import get_logger
from typing_extensions import override

from ingeniamotion.fsoe_master.frame_elements import FSoEFrameElements

logger = get_logger(__name__)


class FSoEFrameRules(Enum):
    """Enumeration of FSoE frame rules."""

    CMD_FIELD_FIRST = "CMD field must be the first item in the PDO map"
    CONN_ID_FIELD_LAST = "ConnID field must be the last item in the PDO map"


@dataclass
class InvalidFSoEFrameRule:
    """Data class to hold information about an invalid FSoE frame rule."""

    rule: FSoEFrameRules  # The rule that was violated
    exception: str  # Description of the error
    suggestion: Optional[str] = None  # Suggestion for fixing the error


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


class PDOMapValidator:
    """Validator for FSoE PDO Maps.

    Validates that the PDO map follows the rules for FSoE frame construction.
    """

    def __init__(self) -> None:
        """Initialize the PDOMapValidator."""
        self._rule_to_validators: dict[FSoEFrameRules, FSoEFrameRuleValidator] = {
            FSoEFrameRules.CMD_FIELD_FIRST: CmdFieldFirstValidator(),
            FSoEFrameRules.CONN_ID_FIELD_LAST: ConnIDFieldLastValidator(),
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

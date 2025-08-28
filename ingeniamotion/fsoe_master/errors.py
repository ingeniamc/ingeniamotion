from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, cast

from ingenialink.dictionary import Dictionary, DictionaryError

if TYPE_CHECKING:
    from ingenialink import Servo


class Error:
    """Class to represent an error from the servo."""

    def __init__(self, error_id: int, dictionary_error: Optional[DictionaryError] = None):
        """Constructor.

        Args:
            error_id: Error ID.
            dictionary_error: DictionaryError instance from the dictionary, if available.
        """
        self.__error_id = error_id
        self.__dictionary_error = dictionary_error

    @property
    def error_id(self) -> int:
        """Get the error ID."""
        return self.__error_id

    @property
    def error_description(self) -> str:
        """Get the error description."""
        if self.__dictionary_error is not None and self.__dictionary_error.description is not None:
            return self.__dictionary_error.description
        return f"Unknown error {self.error_id} / 0x{self.error_id:X}"

    @classmethod
    def from_id(cls, error_id: int, dictionary: Optional[Dictionary] = None) -> Optional["Error"]:
        """Get an Error instance from an error ID.

        Args:
            error_id: Error ID.
            dictionary: Dictionary to get the error description from.

        Returns:
            Error: Error instance, or None if error_id is 0.
        """
        if error_id == 0:
            return None

        dictionary_error = None

        if dictionary:
            dictionary_error = dictionary.errors.get(error_id, None)

        return cls(error_id, dictionary_error)


@dataclass()
class ErrorQueueDescriptor:
    """Descriptor for an error queue in a servo."""

    last_error_reg_uid: str
    total_error_reg_uid: str
    error_request_index_reg_uid: str
    error_request_code_reg_uid: str


MCUA_ERROR_QUEUE = ErrorQueueDescriptor(
    last_error_reg_uid="FSOE_LAST_ERROR_MCUA",
    total_error_reg_uid="FSOE_TOTAL_ERROR_MCUA",
    error_request_index_reg_uid="FSOE_ERROR_REQUEST_INDEX_MCUA",
    error_request_code_reg_uid="FSOE_ERROR_REQUEST_CODE_MCUA",
)

MCUB_ERROR_QUEUE = ErrorQueueDescriptor(
    last_error_reg_uid="FSOE_LAST_ERROR_MCUB",
    total_error_reg_uid="FSOE_TOTAL_ERROR_MCUB",
    error_request_index_reg_uid="FSOE_ERROR_REQUEST_INDEX_MCUB",
    error_request_code_reg_uid="FSOE_ERROR_REQUEST_CODE_MCUB",
)


class ServoErrorQueue:
    """Class to manage a error queue of a servo."""

    def __init__(
        self,
        descriptor: ErrorQueueDescriptor,
        servo: Servo,
    ):
        self.descriptor = descriptor
        self.__servo = servo
        self.__dictionary = servo.dictionary

    def __get_int_reg(self, reg_uid: str) -> int:
        return cast(int, self.__servo.read(reg_uid))

    def get_last_error(self) -> Optional[Error]:
        """Get the last error from the servo's error queue.

        Returns:
            Optional[Error]: The last error, or None if there is no error.
        """
        return Error.from_id(
            self.__get_int_reg(self.descriptor.last_error_reg_uid), self.__dictionary
        )

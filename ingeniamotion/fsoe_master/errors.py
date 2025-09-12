from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, cast

from ingenialink.dictionary import Dictionary, DictionaryError

from ingeniamotion._utils import weak_lru

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

    def __repr__(self) -> str:
        """Get a string representation of the Error instance.

        Returns:
            str: String representation of the Error instance.
        """
        return (
            f"<Error object at {hex(id(self))} "
            f"error_id={self.error_id} "
            f"error_description='{self.error_description}'>"
        )


@dataclass()
class ErrorQueueDescriptor:
    """Descriptor for an error queue in a servo."""

    last_error_reg_uid: str
    total_error_reg_uid: str
    error_request_index_reg_uid: str
    error_request_code_reg_uid: str
    max_index_request: int


MCUA_ERROR_QUEUE = ErrorQueueDescriptor(
    last_error_reg_uid="FSOE_LAST_ERROR_MCUA",
    total_error_reg_uid="FSOE_TOTAL_ERROR_MCUA",
    error_request_index_reg_uid="FSOE_ERROR_REQUEST_INDEX_MCUA",
    error_request_code_reg_uid="FSOE_ERROR_REQUEST_CODE_MCUA",
    max_index_request=31,
)

MCUB_ERROR_QUEUE = ErrorQueueDescriptor(
    last_error_reg_uid="FSOE_LAST_ERROR_MCUB",
    total_error_reg_uid="FSOE_TOTAL_ERROR_MCUB",
    error_request_index_reg_uid="FSOE_ERROR_REQUEST_INDEX_MCUB",
    error_request_code_reg_uid="FSOE_ERROR_REQUEST_CODE_MCUB",
    max_index_request=31,
)


class ServoErrorQueue:
    """Class to manage a error queue of a servo."""

    def __init__(
        self,
        descriptor: ErrorQueueDescriptor,
        servo: "Servo",
    ):
        self.descriptor = descriptor
        self.__servo = servo
        self.__dictionary = servo.dictionary

        # Total number of errors that were last read to obtain pending errors
        self.__last_read_total_errors_pending = 0

    def __read_int_reg(self, reg_uid: str) -> int:
        return cast("int", self.__servo.read(reg_uid))

    def get_last_error(self) -> Optional[Error]:
        """Get the last error from the servo's error queue.

        Returns:
            Optional[Error]: The last error, or None if there is no error.
        """
        return Error.from_id(
            self.__read_int_reg(self.descriptor.last_error_reg_uid), self.__dictionary
        )

    def get_number_total_errors(self) -> int:
        """Get the total number of errors from the servo's error queue.

        Returns:
            int: Total number of errors.
        """
        return self.__read_int_reg(self.descriptor.total_error_reg_uid)

    @property
    @weak_lru()
    def max_number_of_errors_in_buffer(self) -> int:
        """Get the maximum number of errors in the buffer from the servo's error queue.

        If more errors occur. oldest ones are discarded.
        """
        return self.descriptor.max_index_request + 1

    def get_error_by_index(self, index: int) -> Optional[Error]:
        """Get the error from the servo's error queue.

        Args:
            index: Index of the error from the servo's error queue.

        Returns:
            The error at the given index, or None if there is no error.
        """
        self.__servo.write(self.descriptor.error_request_index_reg_uid, index)
        return Error.from_id(
            self.__read_int_reg(self.descriptor.error_request_code_reg_uid),
        )

    def __get_pending_error_indexes(
        self, current_total_errors: int
    ) -> tuple[tuple[int, ...], bool]:
        """Get the indexes of the pending errors from the servo's error queue.

        Indicates the indexes of the error queue that are pending to be read since the last
        time it the queue was read, according to the total number of errors reported by the servo.

        It takes into account overflow and wrap around of the error queue.

        Also indicates if any errors were lost and will not be read.
        Happens when the n pending errors to read is higher than the queue length

        Returns:
            tuple with:
                tuple of indexes of the errors pending to be read
                boolean indicating if errors were lost
        """
        n_pending_errors = current_total_errors - self.__last_read_total_errors_pending
        errors_lost = n_pending_errors > self.max_number_of_errors_in_buffer

        first_n_error_to_read = self.__last_read_total_errors_pending
        if errors_lost:
            # Previous errors have been lost and can't be read
            first_n_error_to_read = current_total_errors - self.max_number_of_errors_in_buffer

        return tuple(
            idx % self.max_number_of_errors_in_buffer
            for idx in range(first_n_error_to_read, current_total_errors)
        ), errors_lost

    def get_pending_errors(self) -> tuple[list[Error], bool]:
        """Get the pending errors from the servo's error queue.

        Indicates the errors that have occurred since the last time this method was called.

        Returns:
            A tuple containing: List of pending errors, and a boolean indicating
                if any errors were lost due to buffer overflow.
        """
        total_errors = self.get_number_total_errors()
        pending_indexes, errors_lost = self.__get_pending_error_indexes(total_errors)
        errors = [
            error for idx in pending_indexes if (error := self.get_error_by_index(idx)) is not None
        ]

        self.__last_read_total_errors_pending = total_errors

        return errors, errors_lost

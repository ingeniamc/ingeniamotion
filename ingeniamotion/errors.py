from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, ClassVar, Optional

from ingenialink.dictionary import Dictionary, DictionaryError
from ingenialogger import get_logger

from ingeniamotion._utils import weak_lru

if TYPE_CHECKING:
    from ingenialink import Servo

    from ingeniamotion.motion_controller import MotionController

from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO

logger = get_logger(__name__)


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


class ServoErrorQueue:
    """Class to manage a error queue of a servo."""

    def __init__(
        self,
        descriptor: ErrorQueueDescriptor,
        servo: "Servo",
        axis: Optional[int] = None,
    ):
        self.descriptor = descriptor
        self.__servo = servo
        self.__dictionary = servo.dictionary
        self.__axis = axis

        # Total number of errors that were last read to obtain pending errors
        self.__last_read_total_errors_pending = 0

    def __read_int_reg(self, reg_uid: str) -> int:
        """Read an integer register value with type validation.

        Args:
            reg_uid: Register UID to read.

        Returns:
            The register value as an integer.

        Raises:
            TypeError: If the register value is not an integer.
        """
        if self.__axis is not None:
            value = self.__servo.read(reg_uid, subnode=self.__axis)
        else:
            value = self.__servo.read(reg_uid)
        if not isinstance(value, int):
            raise TypeError(
                f"Register {reg_uid} value must be an integer, got {type(value).__name__}"
            )
        return value

    def get_last_error(self) -> Optional[Error]:
        """Get the last error from the servo's error queue.

        Returns:
            Optional[Error]: The last error, or None if there is no error.
        """
        error = Error.from_id(
            self.__read_int_reg(self.descriptor.last_error_reg_uid), self.__dictionary
        )
        return error

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
        if self.__axis is not None:
            self.__servo.write(
                self.descriptor.error_request_index_reg_uid, index, subnode=self.__axis
            )
        else:
            self.__servo.write(self.descriptor.error_request_index_reg_uid, index)
        error = Error.from_id(
            self.__read_int_reg(self.descriptor.error_request_code_reg_uid), self.__dictionary
        )
        return error

    def __get_number_of_pending_error(self, current_total_errors: int) -> tuple[int, bool]:
        """Get the number of pending errors from the servo's error queue.

        Args:
            current_total_errors: Current total number of errors in the servo's error queue.

        Returns:
            A tuple containing: Number of pending errors to read, and a boolean indicating
                if any errors were lost due to buffer overflow.

        """
        n_pending_errors = current_total_errors - self.__last_read_total_errors_pending
        errors_lost = n_pending_errors > self.max_number_of_errors_in_buffer

        if errors_lost:
            # Previous errors have been lost and can't be read
            total_errors_to_read = self.max_number_of_errors_in_buffer
        else:
            total_errors_to_read = n_pending_errors

        return total_errors_to_read, errors_lost

    def get_pending_errors(self) -> tuple[list[Error], bool]:
        """Get the pending errors from the servo's error queue.

        Indicates the errors that have occurred since the last time this method was called.

        Returns:
            A tuple containing: List of pending errors, and a boolean indicating
                if any errors were lost due to buffer overflow.
        """
        total_errors = self.get_number_total_errors()
        number_of_pending_errors, errors_lost = self.__get_number_of_pending_error(total_errors)
        errors = []
        pending_error_count = number_of_pending_errors
        while pending_error_count > 0:
            # Read errors from oldest to newest
            pending_error_index = pending_error_count - 1
            total_errors_before_read = self.get_number_total_errors()
            error = self.get_error_by_index(pending_error_index)
            total_errors_after_read = self.get_number_total_errors()
            # Check if new errors appeared during processing
            if total_errors_before_read == total_errors_after_read:
                # No new errors
                if error is not None:
                    errors.append(error)
                pending_error_count -= 1
            else:
                # New errors appeared, need to recalculate pending errors
                current_total_errors = total_errors_after_read
                new_errors = current_total_errors - total_errors
                total_errors = current_total_errors
                pending_error_count += new_errors

        self.__last_read_total_errors_pending = total_errors
        # Reverse the list to have the newest errors first
        return errors[::-1], errors_lost


# Standard error queue descriptors
MOCO_ERROR_QUEUE = ErrorQueueDescriptor(
    last_error_reg_uid="DRV_DIAG_ERROR_LAST",
    total_error_reg_uid="DRV_DIAG_ERROR_TOTAL",
    error_request_index_reg_uid="DRV_DIAG_ERROR_LIST_IDX",
    error_request_code_reg_uid="DRV_DIAG_ERROR_LIST_CODE",
    max_index_request=31,
)

COCO_ERROR_QUEUE = ErrorQueueDescriptor(
    last_error_reg_uid="DRV_DIAG_ERROR_LAST_COM",
    total_error_reg_uid="DRV_DIAG_ERROR_TOTAL_COM",
    error_request_index_reg_uid="DRV_DIAG_ERROR_LIST_IDX_COM",
    error_request_code_reg_uid="DRV_DIAG_ERROR_LIST_CODE_COM",
    max_index_request=31,
)

SYSTEM_ERROR_QUEUE = ErrorQueueDescriptor(
    last_error_reg_uid="DRV_DIAG_SYS_ERROR_LAST",
    total_error_reg_uid="DRV_DIAG_SYS_ERROR_TOTAL_COM",
    error_request_index_reg_uid="DRV_DIAG_SYS_ERROR_LIST_IDX_COM",
    error_request_code_reg_uid="DRV_DIAG_SYS_ERROR_LIST_CODE_COM",
    max_index_request=31,
)


class Errors:
    """Errors."""

    class ErrorLocation(IntEnum):
        """Location of a generated error."""

        COCO = 0
        MOCO = 1
        SYSTEM = 2

    LAST_ERROR_COCO_REGISTER = "DRV_DIAG_ERROR_LAST_COM"
    LAST_ERROR_MOCO_REGISTER = "DRV_DIAG_ERROR_LAST"
    LAST_ERROR_SYSTEM_REGISTER = "DRV_DIAG_SYS_ERROR_LAST"
    LAST_ERROR_REGISTER: ClassVar[dict[ErrorLocation, str]] = {
        ErrorLocation.COCO: LAST_ERROR_COCO_REGISTER,
        ErrorLocation.MOCO: LAST_ERROR_MOCO_REGISTER,
        ErrorLocation.SYSTEM: LAST_ERROR_SYSTEM_REGISTER,
    }
    ERROR_TOTAL_NUMBER_COCO_REGISTER = "DRV_DIAG_ERROR_TOTAL_COM"
    ERROR_TOTAL_NUMBER_MOCO_REGISTER = "DRV_DIAG_ERROR_TOTAL"
    ERROR_TOTAL_NUMBER_SYSTEM_REGISTER = "DRV_DIAG_SYS_ERROR_TOTAL_COM"
    ERROR_TOTAL_NUMBER_REGISTER: ClassVar[dict[ErrorLocation, str]] = {
        ErrorLocation.COCO: ERROR_TOTAL_NUMBER_COCO_REGISTER,
        ErrorLocation.MOCO: ERROR_TOTAL_NUMBER_MOCO_REGISTER,
        ErrorLocation.SYSTEM: ERROR_TOTAL_NUMBER_SYSTEM_REGISTER,
    }
    ERROR_LIST_INDEX_REQUEST_COCO_REGISTER = "DRV_DIAG_ERROR_LIST_IDX_COM"
    ERROR_LIST_INDEX_REQUEST_MOCO_REGISTER = "DRV_DIAG_ERROR_LIST_IDX"
    ERROR_LIST_INDEX_REQUEST_SYSTEM_REGISTER = "DRV_DIAG_SYS_ERROR_LIST_IDX_COM"
    ERROR_LIST_INDEX_REQUEST_REGISTER: ClassVar[dict[ErrorLocation, str]] = {
        ErrorLocation.COCO: ERROR_LIST_INDEX_REQUEST_COCO_REGISTER,
        ErrorLocation.MOCO: ERROR_LIST_INDEX_REQUEST_MOCO_REGISTER,
        ErrorLocation.SYSTEM: ERROR_LIST_INDEX_REQUEST_SYSTEM_REGISTER,
    }
    ERROR_LIST_REQUESTED_COCO_CODE = "DRV_DIAG_ERROR_LIST_CODE_COM"
    ERROR_LIST_REQUESTED_MOCO_CODE = "DRV_DIAG_ERROR_LIST_CODE"
    ERROR_LIST_REQUESTED_SYSTEM_CODE = "DRV_DIAG_SYS_ERROR_LIST_CODE_COM"
    ERROR_LIST_REQUESTED_CODE: ClassVar[dict[ErrorLocation, str]] = {
        ErrorLocation.COCO: ERROR_LIST_REQUESTED_COCO_CODE,
        ErrorLocation.MOCO: ERROR_LIST_REQUESTED_MOCO_CODE,
        ErrorLocation.SYSTEM: ERROR_LIST_REQUESTED_SYSTEM_CODE,
    }

    MAXIMUM_ERROR_INDEX = 32

    STATUS_WORD_FAULT_BIT = 0x08
    STATUS_WORD_WARNING_BIT = 0x80

    ERROR_CODE_BITS = 0xFFFF
    ERROR_SUBNODE_BITS = 0xF00000
    ERROR_SUBNODE_SHIFT = 20
    ERROR_WARNING_BIT = 0x10000000
    ERROR_WARNING_SHIFT = 28

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller

    def __get_error_queue(
        self, servo: str = DEFAULT_SERVO, axis: Optional[int] = None
    ) -> ServoErrorQueue:
        """Get the appropriate ServoErrorQueue for the given servo and axis.

        Args:
            servo: servo alias to reference it.
            axis: axis to get error queue for.

        Returns:
            ServoErrorQueue instance for the specified servo/axis.
        """
        error_version = self.__get_error_location(servo)
        axis, error_location = self.__get_error_subnode(error_version, axis)

        # Select the appropriate descriptor based on error location
        if error_location == self.ErrorLocation.SYSTEM:
            descriptor = SYSTEM_ERROR_QUEUE
        elif error_location == self.ErrorLocation.COCO:
            descriptor = COCO_ERROR_QUEUE
        else:  # MOCO
            descriptor = MOCO_ERROR_QUEUE

        # Always get fresh drive reference to avoid stale servo objects
        drive = self.mc._get_drive(servo)

        # Pass axis to ServoErrorQueue to match old behavior via get_register()
        return ServoErrorQueue(descriptor, drive, axis=axis)

    def __parse_error_to_tuple(
        self, error: int, location: ErrorLocation, subnode: Optional[int] = None
    ) -> tuple[int, Optional[int], Optional[bool]]:
        error_code = error & self.ERROR_CODE_BITS
        if error_code == 0:
            return error_code, None, None
        if subnode is None:
            if location == self.ErrorLocation.MOCO:
                subnode = DEFAULT_AXIS
            else:
                subnode = (error & self.ERROR_SUBNODE_BITS) >> self.ERROR_SUBNODE_SHIFT
        is_warning = (error & self.ERROR_WARNING_BIT) >> self.ERROR_WARNING_SHIFT
        return error_code, subnode, bool(is_warning)

    def __get_error_location(self, servo: str = DEFAULT_SERVO) -> ErrorLocation:
        """Determine the error location based on available registers.

        Args:
            servo: servo alias to reference it.

        Returns:
            ErrorLocation: The error location (SYSTEM, COCO, or MOCO).
        """
        if self.mc.info.register_exists(self.LAST_ERROR_SYSTEM_REGISTER, axis=0, servo=servo):
            # Check System last error, if it does not exist check CoCo
            return self.ErrorLocation.SYSTEM
        if self.mc.info.register_exists(self.LAST_ERROR_COCO_REGISTER, axis=0, servo=servo):
            # Check CoCo last error, if it does not exist use MoCo
            return self.ErrorLocation.COCO
        # Default to MoCo
        return self.ErrorLocation.MOCO

    def __get_error_subnode(
        self, location: ErrorLocation, subnode: Optional[int]
    ) -> tuple[int, ErrorLocation]:
        """Get the appropriate subnode and error location.

        Args:
            location: The error location.
            subnode: The subnode (axis).

        Returns:
            A tuple containing the subnode and the adjusted error location.
        """
        if location == self.ErrorLocation.SYSTEM:
            if subnode is None:
                return 0, location
            if subnode == 0:
                location = self.ErrorLocation.COCO
            elif subnode > 0:
                location = self.ErrorLocation.MOCO
            return subnode, location
        if location == self.ErrorLocation.MOCO:
            return subnode or DEFAULT_AXIS, self.ErrorLocation.MOCO
        # COCO
        return 0, self.ErrorLocation.COCO

    def get_last_error(
        self, servo: str = DEFAULT_SERVO, axis: Optional[int] = None
    ) -> tuple[int, Optional[int], Optional[bool]]:
        """Return last servo error.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis force read errors in target axis. ``None`` by default.

        Returns:
            Returns error data.

            code (int):
                Code error.
            axis (int):
                Error axis.
            is_warning (bool):
                ``True`` if warning, else ``False``.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        error_version = self.__get_error_location(servo)
        queue = self.__get_error_queue(servo, axis)
        error_obj = queue.get_last_error()

        if error_obj is None:
            return 0, None, None

        return self.__parse_error_to_tuple(error_obj.error_id, error_version, axis)

    def get_last_buffer_error(
        self, servo: str = DEFAULT_SERVO, axis: Optional[int] = None
    ) -> tuple[int, Optional[int], Optional[bool]]:
        """Get error code from error buffer last position.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis force read errors in target axis. ``None`` by default.

        Returns:
            Returns error data.

            code (int):
                Code error.
            axis (int):
                Error axis.
            is_warning (bool):
                ``True`` if warning, else ``False``.

        Raises:
            ValueError: Index must be less than 32
        """
        logger.info("Errors.get_last_buffer_error: Called with servo=%s, axis=%s", servo, axis)
        result = self.get_buffer_error_by_index(0, servo=servo, axis=axis)
        logger.info("Errors.get_last_buffer_error: Returning %s", result)
        return result

    def get_buffer_error_by_index(
        self, index: int, servo: str = DEFAULT_SERVO, axis: Optional[int] = None
    ) -> tuple[int, Optional[int], Optional[bool]]:
        """Get error code from buffer error target index.

        Args:
            index : buffer error index. It must be less than ``32``.
            servo : servo alias to reference it. ``default`` by default.
            axis : axis force read errors in target axis. ``None`` by default.

        Returns:
            Returns error data.

            code (int):
                Code error.
            axis (int):
                Error axis.
            is_warning (bool):
                ``True`` if warning, else ``False``.

        Raises:
            ValueError: Index must be less than 32
            TypeError: If some read value has a wrong type.
        """
        if index >= self.MAXIMUM_ERROR_INDEX:
            raise ValueError("index must be less than 32")

        error_version = self.__get_error_location(servo)
        queue = self.__get_error_queue(servo, axis)
        error_obj = queue.get_error_by_index(index)

        if error_obj is None:
            return 0, None, None

        return self.__parse_error_to_tuple(error_obj.error_id, error_version, axis)

    def get_number_total_errors(
        self, servo: str = DEFAULT_SERVO, axis: Optional[int] = None
    ) -> int:
        """Return total number of drive errors.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis force read errors in target axis. ``None`` by default.

        Returns:
            Total number of errors.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        queue = self.__get_error_queue(servo, axis)
        return queue.get_number_total_errors()

    def get_all_errors(
        self, servo: str = DEFAULT_SERVO, axis: Optional[int] = None
    ) -> list[tuple[int, Optional[int], Optional[bool]]]:
        """Return List with all error codes.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis force read errors in target axis. ``None`` by default.

        Returns:
            List of all errors.

        """
        err_list = []
        err_num = self.get_number_total_errors(servo, axis)
        err_num = min(err_num, self.MAXIMUM_ERROR_INDEX)
        for i in range(err_num):
            error = self.get_buffer_error_by_index(i, servo=servo, axis=axis)
            err_list.append(error)
        return err_list

    def is_fault_active(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> bool:
        """Return if fault is active.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            ``True`` if fault is active, else ``False``.
        """
        status_word = self.mc.configuration.get_status_word(servo=servo, axis=axis)
        return bool(status_word & self.STATUS_WORD_FAULT_BIT)

    def is_warning_active(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> bool:
        """Return if warning is active.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            ``True`` if warning is active, else ``False``.
        """
        status_word = self.mc.configuration.get_status_word(servo=servo, axis=axis)
        return bool(status_word & self.STATUS_WORD_WARNING_BIT)

    def get_error_data(
        self, error_code: int, servo: str = DEFAULT_SERVO
    ) -> tuple[str, str, str, str]:
        """Return error info from target error_code.

        Args:
            error_code : target error code.
            servo : servo alias to reference it. ``default`` by default.

        Returns:
           Returns error info.

            id (str):
                Error Id
            affected_module (str):
                Error affected module
            error_type (str):
                Error type
            error_message (str):
                Error message
        Raises:
            KeyError: The error codes does not exist in the error's dictionary.

        """
        drive = self.mc._get_drive(servo)
        dictionary_errors = drive.errors[error_code & self.ERROR_CODE_BITS]
        return tuple(dictionary_errors)  # type: ignore[return-value]

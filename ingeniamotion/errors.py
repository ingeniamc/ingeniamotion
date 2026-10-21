from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from ingenialink import Register
from ingenialink.dictionary import Dictionary, DictionaryError

from ingeniamotion._utils import weak_lru
from ingeniamotion.exceptions import (
    IMError,
    IMErrorQueueNotExistsError,
)

if TYPE_CHECKING:
    from ingenialink import Servo

    from ingeniamotion.axis import Axis
    from ingeniamotion.motion_controller import MotionController
    from ingeniamotion.motion_node import MotionNode

from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO


class Error:
    """Class to represent an error from the servo."""

    def __init__(self, error_id: int, dictionary_error: Optional[DictionaryError] = None):
        """Constructor.

        Args:
            error_id: Error ID.
            dictionary_error: DictionaryError instance from the dictionary, if available.
        """
        self._error_id = error_id
        self.__dictionary_error = dictionary_error

    @property
    def error_id(self) -> int:
        """The error ID."""
        return self._error_id

    @property
    def error_code(self) -> int:
        """The error code.

        Same as ID in most cases, but can be masked by additional bits
        in some error types (e.g. OperationError).
        """
        return self._error_id

    @property
    def dictionary_error(self) -> Optional[DictionaryError]:
        """The DictionaryError instance from the dictionary, if available."""
        return self.__dictionary_error

    @property
    def error_type(self) -> Optional[str]:
        """The error type, if available."""
        if self.__dictionary_error is not None and self.__dictionary_error.error_type is not None:
            return self.__dictionary_error.error_type
        return None

    @property
    def error_description(self) -> str:
        """The error description."""
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


class OperationError(Error):
    """Class to represent an operation error from the servo."""

    __ERROR_CODE_BITS = 0xFFFF
    __ERROR_WARNING_BIT = 0x10000000
    __ERROR_WARNING_SHIFT = 28

    @property
    def error_code(self) -> int:
        """The error code."""
        return self._error_id & self.__ERROR_CODE_BITS

    @property
    def is_warning(self) -> bool:
        """Check if the error is a warning."""
        return bool((self._error_id & self.__ERROR_WARNING_BIT) >> self.__ERROR_WARNING_SHIFT)

    @classmethod
    def from_id(cls, error_id: int, dictionary: Optional[Dictionary] = None) -> Optional["Error"]:
        """Get an OperationError instance from an error ID.

        The dictionary lookup uses the masked error code (lower 16 bits) instead of
        the full error_id, which may contain additional flag bits (e.g. warning bit).

        Args:
            error_id: Error ID.
            dictionary: Dictionary to get the error description from.

        Returns:
            OperationError: Error instance, or None if error_id is 0.
        """
        if error_id == 0:
            return None

        dictionary_error = None

        if dictionary:
            error_code = error_id & cls.__ERROR_CODE_BITS
            dictionary_error = dictionary.errors.get(error_code, None)

        return cls(error_id, dictionary_error)


class SystemQueueError(OperationError):
    """Class to represent a system error from the servo."""

    __ERROR_SUBNODE_BITS = 0xF00000
    __ERROR_SUBNODE_SHIFT = 20

    @property
    def axis(self) -> int:
        """The error axis. If 0, it is a COCO error."""
        return (self._error_id & self.__ERROR_SUBNODE_BITS) >> self.__ERROR_SUBNODE_SHIFT


@dataclass(frozen=True)
class ErrorQueueDescriptor:
    """Descriptor for an error queue in a servo."""

    last_error_reg_uid: str
    total_error_reg_uid: str
    error_request_index_reg_uid: str
    error_request_code_reg_uid: str
    max_index_request: int
    error_type: type[Error]
    name: str


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

        # Begin collecting registers, if any of them is missing,
        # an IMErrorQueueNotExistsError will be raised at the end of the block
        # with the missing registers as underlying exceptions
        with IMErrorQueueNotExistsError.group(
            message="One or more registers for error queue not found in servo dictionary."
        ) as exception_group:
            with exception_group.catch(KeyError, ValueError):
                self.__last_error_reg = servo.dictionary.get_register(
                    self.descriptor.last_error_reg_uid, axis=axis
                )

            with exception_group.catch(KeyError, ValueError):
                self.__total_error_reg = servo.dictionary.get_register(
                    self.descriptor.total_error_reg_uid, axis=axis
                )

            with exception_group.catch(KeyError, ValueError):
                self.__error_request_index_reg = servo.dictionary.get_register(
                    self.descriptor.error_request_index_reg_uid, axis=axis
                )

            with exception_group.catch(KeyError, ValueError):
                self.__error_request_code_reg = servo.dictionary.get_register(
                    self.descriptor.error_request_code_reg_uid, axis=axis
                )

    def __read_int_reg(self, register: Register) -> int:
        """Read an integer register value with type validation.

        Args:
            register: Register object to read.

        Returns:
            The register value as an integer.

        Raises:
            TypeError: If the register value is not an integer.
        """
        value = self.__servo.read(register)
        if not isinstance(value, int):
            raise TypeError(
                f"Register {register.identifier} value must be an integer, "
                f"got {type(value).__name__}"
            )
        return value

    @property
    def axis(self) -> Optional[int]:
        """The axis number associated with this error queue, if any."""
        return self.__axis

    @property
    def name(self) -> str:
        """The name of the error queue."""
        if self.axis is not None:
            return f"{self.descriptor.name} Axis {self.axis} Error Queue"
        return f"{self.descriptor.name} Error Queue"

    def get_last_error(self) -> Optional[Error]:
        """Get the last error from the servo's error queue.

        Returns:
            Optional[Error]: The last error, or None if there is no error.
        """
        error = self.descriptor.error_type.from_id(
            self.__read_int_reg(self.__last_error_reg), self.__dictionary
        )
        return error

    def get_number_total_errors(self) -> int:
        """Get the total number of errors from the servo's error queue.

        Returns:
            int: Total number of errors.
        """
        return self.__read_int_reg(self.__total_error_reg)

    @property
    @weak_lru()
    def max_number_of_errors_in_buffer(self) -> int:
        """The maximum number of errors in the buffer from the servo's error queue.

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
        self.__servo.write(self.__error_request_index_reg, index)
        error = self.descriptor.error_type.from_id(
            self.__read_int_reg(self.__error_request_code_reg), self.__dictionary
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
    name="MoCo",
    last_error_reg_uid="DRV_DIAG_ERROR_LAST",
    total_error_reg_uid="DRV_DIAG_ERROR_TOTAL",
    error_request_index_reg_uid="DRV_DIAG_ERROR_LIST_IDX",
    error_request_code_reg_uid="DRV_DIAG_ERROR_LIST_CODE",
    max_index_request=31,
    error_type=OperationError,
)

COCO_ERROR_QUEUE = ErrorQueueDescriptor(
    name="CoCo",
    last_error_reg_uid="DRV_DIAG_ERROR_LAST_COM",
    total_error_reg_uid="DRV_DIAG_ERROR_TOTAL_COM",
    error_request_index_reg_uid="DRV_DIAG_ERROR_LIST_IDX_COM",
    error_request_code_reg_uid="DRV_DIAG_ERROR_LIST_CODE_COM",
    max_index_request=31,
    error_type=OperationError,
)

SYSTEM_ERROR_QUEUE = ErrorQueueDescriptor(
    name="System",
    last_error_reg_uid="DRV_DIAG_SYS_ERROR_LAST",
    total_error_reg_uid="DRV_DIAG_SYS_ERROR_TOTAL_COM",
    error_request_index_reg_uid="DRV_DIAG_SYS_ERROR_LIST_IDX_COM",
    error_request_code_reg_uid="DRV_DIAG_SYS_ERROR_LIST_CODE_COM",
    max_index_request=31,
    error_type=SystemQueueError,
)

FSOE_MCUA_ERROR_QUEUE = ErrorQueueDescriptor(
    name="Safety A",
    last_error_reg_uid="FSOE_LAST_ERROR_MCUA",
    total_error_reg_uid="FSOE_TOTAL_ERROR_MCUA",
    error_request_index_reg_uid="FSOE_ERROR_REQUEST_INDEX_MCUA",
    error_request_code_reg_uid="FSOE_ERROR_REQUEST_CODE_MCUA",
    max_index_request=31,
    error_type=Error,
)

FSOE_MCUB_ERROR_QUEUE = ErrorQueueDescriptor(
    name="Safety B",
    last_error_reg_uid="FSOE_LAST_ERROR_MCUB",
    total_error_reg_uid="FSOE_TOTAL_ERROR_MCUB",
    error_request_index_reg_uid="FSOE_ERROR_REQUEST_INDEX_MCUB",
    error_request_code_reg_uid="FSOE_ERROR_REQUEST_CODE_MCUB",
    max_index_request=31,
    error_type=Error,
)


class NodeErrors:
    """Class to manage errors of a motion node."""

    def __init__(self, motion_node: "MotionNode") -> None:
        self.__motion_node = motion_node

    @weak_lru(maxsize=None)
    def get_queue(self, descriptor: ErrorQueueDescriptor) -> Optional[ServoErrorQueue]:
        """Get the error queue of the motion node for the given descriptor.

        Returns:
            ServoErrorQueue: The error queue instance, or ``None`` if the registers
                described by the descriptor are not present in the servo dictionary.
        """
        try:
            return ServoErrorQueue(descriptor, self.__motion_node.servo)
        except IMErrorQueueNotExistsError:
            return None

    @property
    def system(self) -> Optional[ServoErrorQueue]:
        """The system error queue of the motion node.

        Returns:
            ServoErrorQueue: The system error queue, or ``None`` if not available in
                the servo dictionary.
        """
        return self.get_queue(SYSTEM_ERROR_QUEUE)

    @property
    def coco(self) -> Optional[ServoErrorQueue]:
        """The COCO error queue of the motion node.

        Returns:
            ServoErrorQueue: The COCO error queue, or ``None`` if not available in
                the servo dictionary.
        """
        return self.get_queue(COCO_ERROR_QUEUE)

    def get_all_queues(
        self, exclude: Optional[list[ErrorQueueDescriptor]] = None
    ) -> Iterator[ServoErrorQueue]:
        """Get all error queues of the motion node.

        Yields:
            ServoErrorQueue: An error queue of the motion node.
        """
        for descriptor in [SYSTEM_ERROR_QUEUE, COCO_ERROR_QUEUE]:
            if exclude and descriptor in exclude:
                continue
            queue = self.get_queue(descriptor)
            if queue is not None:
                yield queue

        for axis in self.__motion_node.axes:
            yield from axis.errors.get_all_queues(exclude=exclude)


class AxisErrors:
    """Class to manage errors of an axis."""

    def __init__(self, axis: "Axis") -> None:
        """Initialize axis errors.

        Args:
            axis: The axis associated with the errors.
        """
        self.__axis = axis

    @weak_lru(maxsize=None)
    def get_queue(self, descriptor: ErrorQueueDescriptor) -> Optional[ServoErrorQueue]:
        """Get the error queue for the given descriptor.

        Returns:
            ServoErrorQueue: The error queue instance, or ``None`` if the registers
                described by the descriptor are not present in the servo dictionary.
        """
        try:
            return ServoErrorQueue(
                descriptor, self.__axis.motion_node.servo, axis=self.__axis.axis_number
            )
        except IMErrorQueueNotExistsError:
            return None

    @property
    def moco(self) -> Optional[ServoErrorQueue]:
        """The MOCO error queue of the axis.

        Returns:
            ServoErrorQueue: The MOCO error queue, or ``None`` if not available in
                the servo dictionary.
        """
        return self.get_queue(MOCO_ERROR_QUEUE)

    @property
    def safety_a(self) -> Optional[ServoErrorQueue]:
        """The error queue of the MCU A of safety.

        Returns:
            ServoErrorQueue: The MCU-A safety error queue, or ``None`` if not available
                in the servo dictionary.
        """
        return self.get_queue(FSOE_MCUA_ERROR_QUEUE)

    @property
    def safety_b(self) -> Optional[ServoErrorQueue]:
        """The error queue of the MCU B of safety.

        Returns:
            ServoErrorQueue: The MCU-B safety error queue, or ``None`` if not available
                in the servo dictionary.
        """
        return self.get_queue(FSOE_MCUB_ERROR_QUEUE)

    def get_all_queues(
        self, exclude: Optional[list[ErrorQueueDescriptor]] = None
    ) -> Iterator[ServoErrorQueue]:
        """Get all error queues of the axis.

        Yields:
            ServoErrorQueue: An error queue of the axis.
        """
        for descriptor in [MOCO_ERROR_QUEUE, FSOE_MCUA_ERROR_QUEUE, FSOE_MCUB_ERROR_QUEUE]:
            if exclude and descriptor in exclude:
                continue
            queue = self.get_queue(descriptor)
            if queue is not None:
                yield queue


class Errors:
    """Errors."""

    MAXIMUM_ERROR_INDEX = 32

    STATUS_WORD_FAULT_BIT = 0x08
    STATUS_WORD_WARNING_BIT = 0x80

    __ERROR_CODE_BITS = 0xFFFF

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

        Raises:
            IMErrorQueueNotExistsError: If no suitable error queue registers are found.
        """
        m = self.mc._get_motion_node(servo)

        system_queue = m.errors.system
        if system_queue is not None:
            # Drive has SYSTEM registers
            if axis is None:
                return system_queue
            if axis == 0:
                coco_queue = m.errors.coco
                if coco_queue is not None:
                    return coco_queue
            else:
                # axis > 0: axis-specific MOCO queue
                try:
                    return m.get_axis(axis).error_queue
                except KeyError:
                    msg = (
                        f"Axis {axis} not found in servo {servo}, "
                        "cannot access axis-specific error queue"
                    )
                    raise IMErrorQueueNotExistsError(msg, [IMError(msg)])

        coco_queue = m.errors.coco
        if coco_queue is not None:
            # Drive has no System queue, use COCO queue regardless of axis
            return coco_queue

        # Drive has MOCO-only error queues, get the one for the specified axis
        resolved_axis = axis if axis is not None else DEFAULT_AXIS
        try:
            axis_obj = m.get_axis(resolved_axis)
        except KeyError:
            msg = f"Axis {resolved_axis} not found in servo {servo}, cannot access MOCO error queue"
            raise IMErrorQueueNotExistsError(msg, [IMError(msg)])
        return axis_obj.error_queue

    def __parse_error_to_tuple(
        self, error: Error, subnode: Optional[int] = None
    ) -> tuple[int, Optional[int], Optional[bool]]:
        if not isinstance(error, OperationError):
            return error.error_id, None, None
        if isinstance(error, SystemQueueError):
            return error.error_code, error.axis, error.is_warning
        return error.error_code, subnode, error.is_warning

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
        queue = self.__get_error_queue(servo, axis)
        error_obj = queue.get_last_error()

        if error_obj is None:
            return 0, None, None

        return self.__parse_error_to_tuple(error_obj, axis)

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
        result = self.get_buffer_error_by_index(0, servo=servo, axis=axis)
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

        queue = self.__get_error_queue(servo, axis)
        error_obj = queue.get_error_by_index(index)

        if error_obj is None:
            return 0, None, None

        return self.__parse_error_to_tuple(error_obj, axis)

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
        dictionary_errors = drive.errors[error_code & self.__ERROR_CODE_BITS]
        return tuple(dictionary_errors)  # type: ignore[return-value]

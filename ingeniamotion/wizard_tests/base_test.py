import time
from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Generic,
    Optional,
    TypeVar,
)

import ingenialogger
from ingenialink.drive_context_manager import DriveContextManager, DriveRegistersValue
from ingenialink.exceptions import ILError
from ingenialink.register import Register
from ingenialink.utils._utils import REG_VALUE

from ingeniamotion._utils import weak_lru
from ingeniamotion.metaclass import DEFAULT_SERVO
from ingeniamotion.wizard_tests.stoppable import StopExceptionError, Stoppable

if TYPE_CHECKING:
    from ingenialink.servo import Servo

    from ingeniamotion import MotionController
    from ingeniamotion.axis import Axis
    from ingeniamotion.feedbacks import AxisFeedbacks
    from ingeniamotion.motion_node import MotionNode

from ingeniamotion.enums import SeverityLevel


class TestError(Exception):
    """Test error exception."""


class TestConfigurationError(TestError):
    """Test configuration exception."""


RegisterChangeProposal = dict[Register, REG_VALUE]


@dataclass(eq=False)
class ReportBase:
    """Base class for result reports."""

    result_severity: SeverityLevel
    """Severity level."""
    result_message: str
    """Message explaining the result."""
    suggested_registers: RegisterChangeProposal
    """Register values suggested by the test."""

    def __getitem__(self, key: str) -> Any:
        """Read a report field using the legacy dictionary syntax.

        Args:
            key: Report field name.

        Returns:
            The value associated with the report field.

        Raises:
            KeyError: If the field name is not recognized.
        """
        if key == "result_severity":
            return self.result_severity
        if key == "result_message":
            return self.result_message
        if key == "suggested_registers":
            return self.suggested_registers
        raise KeyError(key)


T = TypeVar("T", bound=ReportBase)


class BaseTest(ABC, Stoppable, Generic[T]):
    """Abstract base Test class."""

    ACCEPTED_CHANGED_REGISTERS: ClassVar[tuple[str, ...]] = ()
    """Registers that the test is expected to leave changed after it runs."""

    def __init__(self) -> None:
        super().__init__()
        self.suggested_registers: RegisterChangeProposal = {}
        self.mc: MotionController
        self.servo: str = DEFAULT_SERVO
        self.axis: int = 0
        self.report: Optional[T] = None
        self.logger = ingenialogger.get_logger(__name__)

    def suggest_register(self, register: Register, value: REG_VALUE) -> None:
        """Suggest a value for a drive register.

        Args:
            register: Drive register.
            value: Value recommended by the test.
        """
        self.suggested_registers[register] = value

    @weak_lru()
    def _get_servo(self) -> "Servo":
        """Get the servo object from the motion controller.

        Returns:
            The servo object.

        """
        return self.mc._get_drive(self.servo)

    @cached_property
    def _motion_node(self) -> "MotionNode":
        """Motion node targeted by the test.

        Returns:
            The motion node selected by ``self.servo``.
        """
        return self.mc._get_motion_node(self.servo)

    @cached_property
    def _axis(self) -> "Axis":
        """Axis targeted by the test.

        Returns:
            The axis selected by ``self.axis``.
        """
        return self._motion_node.get_axis(self.axis)

    @cached_property
    def _axis_feedbacks(self) -> "AxisFeedbacks":
        """Feedback container for the test axis.

        Returns:
            The feedback container selected by ``self._axis``.
        """
        return self._axis.feedbacks

    @Stoppable.stoppable
    def show_error_message(self) -> None:
        """Raise an exception containing the last generated error.

        Raises:
            TestError: If there is an error in the buffer,
                it raises a TestError with the error message.
        """
        error_code, _axis, _warning = self.mc.errors.get_last_buffer_error(
            servo=self.servo, axis=self.axis
        )
        *_, error_msg = self.mc.errors.get_error_data(error_code, servo=self.servo)
        raise TestError(error_msg)

    @abstractmethod
    def setup(self) -> None:
        """Actions to perform before the test is run."""

    @abstractmethod
    def loop(self) -> Any:
        """Actions to perform during the test."""

    @abstractmethod
    def teardown(self) -> None:
        """Actions to perform after the test is run."""

    def run(self, registers_baseline: Optional[DriveRegistersValue] = None) -> Optional[T]:
        """Run the test.

        Returns:
            The test report, which contains the result severity,
                suggested registers, and result message.

        Raises:
            ILError: If the underlying drive communication fails during the test run.
        """
        with (
            context := DriveContextManager(
                servo=self.mc._get_drive(self.servo),
                baseline=registers_baseline,
                do_not_restore_registers=list(self.ACCEPTED_CHANGED_REGISTERS),
                track_objects=False,
            )
        ):
            self.reset_stop()
            try:
                self.setup()
                self.check_stop()
                output = self.loop()
                self.check_stop()
                self.report = self.generate_report(output)
                self.check_stop()
            except ILError as err:
                raise err
            except StopExceptionError:
                self.logger.warning("Test has been stopped")
            finally:
                try:
                    self.teardown()
                finally:
                    self._restore_configuration(context)

        return self.report

    def _restore_configuration(self, context: DriveContextManager) -> None:
        """Restore configuration that requires an ordered transition."""

    def generate_report(self, output: Any) -> T:
        """Generate the test report.

        Args:
            output: The test output.

        Returns:
            The test report.

        """
        return ReportBase(
            result_severity=self.get_result_severity(output),
            suggested_registers=self.suggested_registers,
            result_message=self.get_result_msg(output),
        )  # type: ignore [return-value]

    @abstractmethod
    def get_result_msg(self, output: Any) -> str:
        """Get the test result message.

        Args:
            output: The test output.

        Returns:
            The test result message.

        """

    @abstractmethod
    def get_result_severity(self, output: Any) -> SeverityLevel:
        """Get the test result severity.

        Args:
            output: The test output.

        Returns:
            The test result severity level.

        """

    def _timeout_loop(
        self,
        timeout_sec: float,
        sleep_sec: float = 0.0,
        timeout: Optional[Callable[[], Exception]] = lambda: TimeoutError("Test timed out"),
    ) -> Iterator[int]:
        """Iterate until a timeout expires or the test is stopped.

        The first iteration is yielded immediately unless the timeout has already
        expired. Between iterations, ``stoppable_sleep`` is used so that the loop
        can be interrupted while waiting.

        Args:
            timeout_sec: Maximum duration of the loop, in seconds.
            sleep_sec: Delay between iterations, in seconds.
            timeout: Callable that returns an exception to be raised if the timeout
                expires. If omitted, the iteration stops and continues flow

        Yields:
            Iteration number, starting at 1.

        Raises:
            ValueError: If ``timeout_sec`` or ``sleep_sec`` is negative.


        Examples:

            .. code-block:: python

                for iteration in self.timeout_loop(
                    timeout_sec=0.5,
                    sleep_sec=0.1,
                    timeout= lambda: TimeoutError("Test timed out")
                ):
                    print(f"Iteration {iteration}")
        """
        if timeout_sec < 0:
            raise ValueError("timeout_sec cannot be negative")

        if sleep_sec < 0:
            raise ValueError("sleep_sec cannot be negative")

        iteration = 1
        deadline = time.monotonic() + timeout_sec

        while True:
            self.check_stop()

            remaining_time = deadline - time.monotonic()

            if remaining_time <= 0:
                if timeout is not None:
                    raise timeout()
                return

            yield iteration
            iteration += 1

            next_sleep = min(sleep_sec, remaining_time)
            if next_sleep > 0:
                self.stoppable_sleep(next_sleep)

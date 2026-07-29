from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Generic, Optional, TypeVar, Union

import ingenialogger
from ingenialink.drive_context_manager import DriveContextManager, DriveRegistersValue
from ingenialink.exceptions import ILError

from ingeniamotion._utils import weak_lru
from ingeniamotion.metaclass import DEFAULT_SERVO
from ingeniamotion.wizard_tests.stoppable import StopExceptionError, Stoppable

if TYPE_CHECKING:
    from ingenialink.servo import Servo

    from ingeniamotion import MotionController

from ingeniamotion.enums import SeverityLevel


class TestError(Exception):
    """Test error exception."""


class TestConfigurationError(TestError):
    """Test configuration exception."""


LegacyDictReportType = dict[str, Union[SeverityLevel, dict[str, Union[int, float, str]], str]]


@dataclass
class ReportBase:
    """Base class for result reports."""

    result_severity: SeverityLevel
    """Severity level."""
    result_message: str
    """Message explaining the result."""


T = TypeVar("T", bound=Union[LegacyDictReportType, ReportBase])


class BaseTest(ABC, Stoppable, Generic[T]):
    """Abstract base Test class."""

    ACCEPTED_CHANGED_REGISTERS: Final[tuple[str, ...]] = ()
    """Registers that the test is expected to leave changed after it runs."""

    def __init__(self) -> None:
        self.suggested_registers: dict[str, Union[int, float, str]] = {}
        self.mc: MotionController
        self.servo: str = DEFAULT_SERVO
        self.axis: int = 0
        self.report: Optional[T] = None
        self.logger = ingenialogger.get_logger(__name__)

    @weak_lru()
    def _get_servo(self) -> "Servo":
        """Get the servo object from the motion controller.

        Returns:
            The servo object.

        """
        return self.mc._get_drive(self.servo)

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
        with DriveContextManager(
            servo=self.mc._get_drive(self.servo),
            baseline=registers_baseline,
            do_not_restore_registers=list(self.ACCEPTED_CHANGED_REGISTERS),
            track_objects=False,
        ):
            self.reset_stop()
            try:
                self.setup()
                output = self.loop()
                self.report = self.generate_report(output)
            except ILError as err:
                raise err
            except StopExceptionError:
                self.logger.warning("Test has been stopped")
            finally:
                self.teardown()

        return self.report

    def generate_report(self, output: Any) -> T:
        """Generate the test report.

        Args:
            output: The test output.

        Returns:
            The test report.

        """
        return {
            "result_severity": self.get_result_severity(output),
            "suggested_registers": self.suggested_registers,
            "result_message": self.get_result_msg(output),
        }  # type: ignore [return-value]

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

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Optional, TypeVar, Union

import ingenialogger
from ingenialink.exceptions import ILError

from ingeniamotion.exceptions import IMRegisterNotExistError, IMRegisterWrongAccessError
from ingeniamotion.metaclass import DEFAULT_SERVO
from ingeniamotion.wizard_tests.stoppable import StopExceptionError, Stoppable

if TYPE_CHECKING:
    from ingeniamotion import MotionController

from ingeniamotion.enums import SeverityLevel


class TestError(Exception):
    """Test error exception."""


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

    WARNING_BIT_MASK = 0x0FFFFFFF

    def __init__(self) -> None:
        self.backup_registers_names: list[str] = []
        self.optional_backup_registers_names: list[str] = []
        self.backup_registers: dict[int, dict[str, Union[int, float, str]]] = {}
        self.suggested_registers: dict[str, Union[int, float, str]] = {}
        self.mc: MotionController
        self.servo: str = DEFAULT_SERVO
        self.axis: int = 0
        self.report: Optional[T] = None
        self.logger = ingenialogger.get_logger(__name__)

    def save_backup_registers(self) -> None:
        """Store the value of the backup registers before the test execution."""
        self.backup_registers[self.axis] = {}
        for uid in self.backup_registers_names:
            try:
                value = self.mc.communication.get_register(uid, servo=self.servo, axis=self.axis)
                self.backup_registers[self.axis][uid] = value
            except IMRegisterNotExistError as e:  # noqa: PERF203
                self.logger.warning(e, axis=self.axis)

        for uid in self.optional_backup_registers_names:
            if self.mc.info.register_exists(uid, self.axis, self.servo):
                value = self.mc.communication.get_register(uid, servo=self.servo, axis=self.axis)
                self.backup_registers[self.axis][uid] = value

    def restore_backup_registers(self) -> None:
        """Restores the value of the registers after the test execution.

        Notes:
        This should only be called by the Wizard.
        """
        for subnode in self.backup_registers:  # noqa: PERF203
            for key, value in self.backup_registers[subnode].items():
                try:
                    self.mc.communication.set_register(key, value, servo=self.servo, axis=self.axis)
                    # From FW>=2.7.3, to set the operation mode a motor enable is needed
                    if key == self.mc.motion.OPERATION_MODE_REGISTER:
                        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
                        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
                except IMRegisterNotExistError as e:  # noqa: PERF203
                    self.logger.warning(e, axis=subnode)
                except IMRegisterWrongAccessError as e:
                    self.logger.warning(e, axis=subnode)

    @Stoppable.stoppable
    def show_error_message(self) -> None:
        """Raise an exception containing the last generated error."""
        error_code, axis, warning = self.mc.errors.get_last_buffer_error(
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

    def run(
        self,
    ) -> Optional[T]:
        """Run the test."""
        self.reset_stop()
        self.save_backup_registers()
        try:
            self.setup()
            output = self.loop()
            self.report = self.generate_report(output)
        except ILError as err:
            raise err
        except StopExceptionError:
            self.logger.warning("Test has been stopped")
        finally:
            try:
                self.teardown()
            finally:
                self.restore_backup_registers()
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

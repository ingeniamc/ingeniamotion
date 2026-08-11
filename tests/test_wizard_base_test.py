from collections import OrderedDict
from typing import Any
from unittest.mock import MagicMock

from ingenialink.drive_context_manager import DriveRegistersValue
from ingenialink.register import Register

from ingeniamotion.enums import SeverityLevel
from ingeniamotion.wizard_tests.base_test import BaseTest, ReportBase


class MinimalWizardTest(BaseTest[dict[str, Any]]):
    """Minimal wizard test implementation for BaseTest lifecycle checks."""

    def setup(self) -> None:
        """Prepare the test."""

    def loop(self) -> None:
        """Run the test body."""

    def teardown(self) -> None:
        """Clean up the test."""

    def get_result_msg(self, output: Any) -> str:
        """Return the test result message."""
        _ = output
        return "success"

    def get_result_severity(self, output: Any) -> SeverityLevel:
        """Return the test result severity."""
        _ = output
        return SeverityLevel.SUCCESS


def test_run_uses_supplied_baseline_without_reading_hardware(mocker) -> None:
    """A supplied baseline is forwarded and avoids an entry-time hardware read."""
    drive = MagicMock()
    motion_controller = MagicMock()
    motion_controller._get_drive.return_value = drive
    baseline = DriveRegistersValue(OrderedDict())
    wizard_test = MinimalWizardTest()
    wizard_test.mc = motion_controller

    from_hardware = mocker.patch.object(
        DriveRegistersValue,
        "from_hardware",
        wraps=DriveRegistersValue.from_hardware,
    )

    wizard_test.run(registers_baseline=baseline)

    from_hardware.assert_not_called()


def test_suggest_register_returns_register_instance_with_value() -> None:
    """A suggestion maps the drive register object to its recommended value."""
    register = MagicMock(spec=Register)
    wizard_test = MinimalWizardTest()

    wizard_test.suggest_register(register, 42)

    assert wizard_test.suggested_registers == {register: 42}
    report = ReportBase(SeverityLevel.SUCCESS, "success", wizard_test.suggested_registers)
    assert report["suggested_registers"] == {register: 42}

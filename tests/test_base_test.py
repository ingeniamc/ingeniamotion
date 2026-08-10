from types import TracebackType
from typing import TYPE_CHECKING, Optional

import pytest
from ingenialink.drive_context_manager import DriveContextManager

import ingeniamotion.wizard_tests.base_test as base_test_module
from ingeniamotion.enums import SeverityLevel
from ingeniamotion.wizard_tests.base_test import BaseTest, LegacyDictReportType

if TYPE_CHECKING:
    from ingeniamotion import MotionController
    from ingeniamotion.axis import Axis


class FakeDriveContextManager:
    """Minimal context manager used to exercise BaseTest cleanup."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def __enter__(self) -> "FakeDriveContextManager":
        return self

    def __exit__(
        self,
        _exc_type: Optional[type[BaseException]],
        _exc_value: Optional[BaseException],
        _traceback: Optional[TracebackType],
    ) -> None:
        pass


class FakeMotionController:
    """Minimal motion controller used to provide a drive to BaseTest."""

    def _get_drive(self, _servo: str) -> object:
        return object()


class TeardownFailureTest(BaseTest[LegacyDictReportType]):
    """Concrete BaseTest whose teardown fails after the test body succeeds."""

    def __init__(self, mc: FakeMotionController) -> None:
        super().__init__()
        self.mc = mc
        self.restored = False

    def setup(self) -> None:
        pass

    def loop(self) -> None:
        pass

    def teardown(self) -> None:
        raise RuntimeError("teardown failed")

    def _restore_configuration(self, _context: DriveContextManager) -> None:
        self.restored = True

    def get_result_msg(self, _output: object) -> str:
        return ""

    def get_result_severity(self, _output: object) -> SeverityLevel:
        return SeverityLevel.SUCCESS


def test_base_test_restores_configuration_when_teardown_fails(monkeypatch) -> None:
    """Configuration restoration must run even when teardown raises."""
    monkeypatch.setattr(base_test_module, "DriveContextManager", FakeDriveContextManager)
    test = TeardownFailureTest(FakeMotionController())

    with pytest.raises(RuntimeError, match="teardown failed"):
        test.run()

    assert test.restored


@pytest.mark.virtual
def test_base_test_caches_target_motion_node_axis_and_feedbacks(
    mc: "MotionController", alias: str, axis: "Axis"
) -> None:
    """BaseTest resolves the selected axis feedback container once."""
    test = TeardownFailureTest(mc)
    test.servo = alias
    test.axis = axis.axis_number

    assert test._motion_node is test._motion_node
    assert test._axis is test._axis
    assert test._axis_feedbacks is test._axis.feedbacks

from typing import TYPE_CHECKING

import pytest
from ingenialink.drive_context_manager import DriveContextManager

from ingeniamotion.enums import SeverityLevel
from ingeniamotion.wizard_tests.base_test import BaseTest, ReportBase

if TYPE_CHECKING:
    from ingeniamotion import MotionController
    from ingeniamotion.axis import Axis


class TeardownFailureTest(BaseTest[ReportBase]):
    """Concrete BaseTest whose teardown fails after the test body succeeds."""

    def __init__(self, mc: "MotionController") -> None:
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


@pytest.mark.virtual
def test_base_test_restores_configuration_when_teardown_fails(
    mc: "MotionController", alias: str, axis: "Axis"
) -> None:
    """Configuration restoration must run even when teardown raises."""
    test = TeardownFailureTest(mc)
    test.servo = alias
    test.axis = axis.axis_number

    with pytest.raises(RuntimeError) as exc_info:
        test.run()

    assert str(exc_info.value) == "teardown failed"
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

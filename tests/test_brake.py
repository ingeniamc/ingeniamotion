from typing import TYPE_CHECKING

import pytest
from typing_extensions import override

from ingeniamotion.enums import SeverityLevel
from ingeniamotion.wizard_tests.brake import Brake
from ingeniamotion.wizard_tests.stoppable import StopExceptionError

if TYPE_CHECKING:
    from ingeniamotion import MotionController


class BrakeThatFailsToSetUp(Brake):
    """Brake test whose setup requests a stop before it can configure the drive."""

    @override
    def setup(self) -> None:
        self.stop()
        self.check_stop()


@pytest.mark.virtual
def test_brake_test_configures_drive_immediately(mc: "MotionController", alias: str) -> None:
    """``DriveTests.brake_test`` must configure the drive on the call itself.

    ``with`` is optional sugar, not a requirement: a caller may keep the
    returned ``Brake`` around and only wrap it in ``with`` later to restore
    the drive, without that being a second, independent configuration.
    """
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)

    brake = mc.tests.brake_test(servo=alias)

    assert mc.configuration.get_motor_pair_poles(servo=alias) == 1

    with brake:
        pass

    assert mc.configuration.get_motor_pair_poles(servo=alias) == pair_poles


@pytest.mark.virtual
def test_brake_test_context_configures_and_restores_drive(
    mc: "MotionController", alias: str
) -> None:
    """Entering the brake test configures the drive; exiting restores it."""
    pair_poles = 2
    mc.configuration.set_motor_pair_poles(pair_poles, servo=alias)

    with mc.tests.brake_test(servo=alias):
        assert mc.configuration.get_motor_pair_poles(servo=alias) == 1

    assert mc.configuration.get_motor_pair_poles(servo=alias) == pair_poles


@pytest.mark.virtual
def test_brake_test_reports_success_after_a_clean_run(mc: "MotionController", alias: str) -> None:
    """A brake test that completes without error must report SUCCESS, not None/Fail.

    The report is derived from ``loop()``'s return value via
    ``generate_report()``, so ``loop()`` must return a severity for the
    report to be meaningful.
    """
    with mc.tests.brake_test(servo=alias) as brake:
        pass

    assert brake.report is not None
    assert brake.report.result_severity == SeverityLevel.SUCCESS
    assert brake.report.result_message == "Success"


@pytest.mark.virtual
def test_brake_test_restores_drive_when_body_raises(mc: "MotionController", alias: str) -> None:
    """An exception raised inside the ``with`` block must propagate and still restore.

    Raises:
        ValueError: Always, from the ``with`` block body.
    """
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)

    with pytest.raises(ValueError, match="body failed"), mc.tests.brake_test(servo=alias):
        assert mc.configuration.get_motor_pair_poles(servo=alias) == 1
        raise ValueError("body failed")

    assert mc.configuration.get_motor_pair_poles(servo=alias) == pair_poles


@pytest.mark.virtual
def test_brake_test_enter_failure_still_restores_drive(mc: "MotionController", alias: str) -> None:
    """A failure during setup must restore the drive even though the ``with`` body never runs.

    Raises:
        StopExceptionError: Always, from ``setup()``.
    """
    pair_poles = mc.configuration.get_motor_pair_poles(servo=alias)

    with pytest.raises(StopExceptionError), BrakeThatFailsToSetUp(mc, servo=alias):
        pass

    assert mc.configuration.get_motor_pair_poles(servo=alias) == pair_poles

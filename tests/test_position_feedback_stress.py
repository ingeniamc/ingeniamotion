"""Stress tests for intermittent EtherCAT and BiSS-C position-feedback failures.

The tests compare position-feedback behavior with the motor disabled, with the
motor enabled while holding position, and during repeated position movements.
A separate diagnostic test characterizes the effect of reduced SDO timeouts.
"""

import time
from collections.abc import Generator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Optional

import pytest
from ingenialink.exceptions import ILRegisterAccessError
from ingenialogger import get_logger

from ingeniamotion.enums import OperationMode

if TYPE_CHECKING:
    from ingenialink.ethercat.network import EthercatNetwork

    from ingeniamotion.motion_controller import MotionController


logger = get_logger(__name__)

DriveError = tuple[int, Optional[int], Optional[bool]]
SdoFailure = dict[str, Any]

MOTION_REGISTERS = (
    "DRV_STATE_CONTROL",
    "DRV_STATE_STATUS",
    "DRV_OP_CMD",
    "DRV_OP_VALUE",
    "CL_POS_SET_POINT_VALUE",
    "CL_POS_FBK_VALUE",
    "CL_VEL_FBK_VALUE",
)
STATUS_WORD_FAULT_BIT = 0x0008
STATUS_WORD_TARGET_REACHED_BIT = 0x0800
MAX_ERROR_BUFFER_SIZE = 32
STATIONARY_TEST_DURATION_S = 120.0
MOVEMENT_ITERATIONS = 1_000


@dataclass(frozen=True)
class StressSettings:
    """Timing and tolerance settings shared by the feedback stress tests.

    Attributes:
        position_tolerance: Maximum accepted distance from a target position.
        movement_timeout: Maximum time allowed for one position movement.
        stall_timeout: Maximum time that position may remain unchanged while
            the target has not been reached.
        polling_interval: Delay between consecutive position reads.
        diagnostic_interval: Delay between status and error-buffer checks.
        settling_time: Delay after commanding the motor to hold its position.
    """

    position_tolerance: int = 20
    movement_timeout: float = 10.0
    stall_timeout: float = 1.0
    polling_interval: float = 0.01
    diagnostic_interval: float = 0.1
    settling_time: float = 1.0


class EncoderDebugger:
    """Provide reusable setup, polling, diagnostics, and cleanup operations."""

    def __init__(
        self,
        mc: "MotionController",
        alias: str,
        settings: StressSettings,
    ) -> None:
        """Initialize a debugger for one connected servo.

        Args:
            mc: Motion controller used by the test.
            alias: Alias of the servo under test.
            settings: Timing and position tolerances for the stress tests.
        """
        self.mc = mc
        self.alias = alias
        self.settings = settings
        self.motor_enabled = False

    def enable_motor_holding_current_position(self) -> int:
        """Enable profile-position mode and hold the current position.

        Returns:
            Position measured after the position loop has settled.
        """
        position = self.read_position()
        self.mc.motion.set_operation_mode(
            OperationMode.PROFILE_POSITION,
            servo=self.alias,
        )
        self.mc.motion.motor_enable(servo=self.alias)
        self.motor_enabled = True
        self.mc.motion.move_to_position(
            position,
            servo=self.alias,
            blocking=True,
            timeout=self.settings.movement_timeout,
        )
        time.sleep(self.settings.settling_time)
        return self.read_position()

    def disable_motor(self) -> None:
        """Disable a motor enabled by this debugger without masking failures."""
        if not self.motor_enabled:
            return
        try:
            self.mc.motion.motor_disable(servo=self.alias)
        except Exception as exception:
            logger.warning(
                "Could not disable motor during cleanup: %s: %s",
                type(exception).__name__,
                exception,
            )
        finally:
            self.motor_enabled = False

    def read_position(self) -> int:
        """Read the actual position of the servo.

        Returns:
            Current position-feedback value.
        """
        return self.mc.motion.get_actual_position(servo=self.alias)

    def read_register(self, register: str) -> Any:
        """Read one register from the servo.

        Args:
            register: Register identifier from the connected dictionary.

        Returns:
            Value returned for the requested register.
        """
        return self.mc.communication.get_register(register, servo=self.alias)

    def get_error_buffer(self) -> list[DriveError]:
        """Read the drive error buffer, newest entry first.

        Returns:
            Raw error tuples containing code, axis, and warning state.
        """
        total_errors = self.mc.errors.get_number_total_errors(
            servo=self.alias,
            axis=1,
        )
        return [
            self.mc.errors.get_buffer_error_by_index(
                index,
                servo=self.alias,
                axis=1,
            )
            for index in range(min(total_errors, MAX_ERROR_BUFFER_SIZE))
        ]

    def capture_error_baseline(self) -> list[DriveError]:
        """Capture errors that existed before the current test started.

        Historical errors are retained by the drive across tests. They are
        logged as context but are not attributed to the current test.

        Returns:
            Snapshot of the error buffer at test start.
        """
        errors = self.get_error_buffer()
        if errors:
            logger.warning(
                "Drive error buffer is not empty before the test. Only changes "
                "during this test will be considered. Initial errors: %s",
                errors,
            )
        return errors

    def log_error(self, label: str, error: Optional[DriveError]) -> None:
        """Resolve and log one raw drive error.

        Args:
            label: Description used in the log entry.
            error: Raw error tuple, or ``None`` when no error is available.
        """
        if error is None:
            logger.error("%s: no error", label)
            return

        error_code, error_axis, is_warning = error
        try:
            error_id, module, error_type, message = self.mc.errors.get_error_data(
                error_code,
                servo=self.alias,
            )
        except Exception as exception:
            logger.error(
                "%s: code=%s (0x%04X), axis=%s, warning=%s; description unavailable: %s: %s",
                label,
                error_code,
                error_code,
                error_axis,
                is_warning,
                type(exception).__name__,
                exception,
            )
            return

        logger.error(
            "%s: code=%s (0x%04X), axis=%s, warning=%s, id=%s, module=%s, type=%s, message=%s",
            label,
            error_code,
            error_code,
            error_axis,
            is_warning,
            error_id,
            module,
            error_type,
            message,
        )

    def log_errors(self) -> None:
        """Log the current error and every available buffered error."""
        getters: tuple[tuple[str, Callable[[], Optional[DriveError]]], ...] = (
            (
                "Last drive error",
                lambda: self.mc.errors.get_last_error(servo=self.alias, axis=1),
            ),
            (
                "Last buffered error",
                lambda: self.mc.errors.get_last_buffer_error(
                    servo=self.alias,
                    axis=1,
                ),
            ),
        )
        for label, getter in getters:
            try:
                self.log_error(label, getter())
            except Exception as exception:  # noqa: PERF203
                logger.error(
                    "Could not read %s: %s: %s",
                    label.lower(),
                    type(exception).__name__,
                    exception,
                )

        try:
            errors = self.get_error_buffer()
        except Exception as exception:
            logger.error(
                "Could not read buffered errors: %s: %s",
                type(exception).__name__,
                exception,
            )
            return

        logger.error("Total buffered errors: %s", len(errors))
        for index, error in enumerate(errors):
            self.log_error(f"Buffered error {index}", error)

    def log_motion_state(
        self,
        *,
        iteration: int,
        target: int,
        last_position: Optional[int],
    ) -> None:
        """Log motion-related register values after a failure.

        Args:
            iteration: Movement iteration active when the failure occurred.
            target: Requested position.
            last_position: Last position read successfully, if available.
        """
        logger.error(
            "Motion failure diagnostics: iteration=%s, target=%s, last_position=%s",
            iteration,
            target,
            last_position,
        )
        for register in MOTION_REGISTERS:
            try:
                value = self.read_register(register)
            except Exception as exception:
                logger.error(
                    "%s could not be read: %s: %s",
                    register,
                    type(exception).__name__,
                    exception,
                )
                continue

            if register in {"DRV_STATE_CONTROL", "DRV_STATE_STATUS"}:
                hexadecimal = hex(value) if isinstance(value, int) else "not integer"
                logger.error("%s=%s (%s)", register, value, hexadecimal)
            else:
                logger.error("%s=%s", register, value)

            if register == "DRV_STATE_STATUS" and isinstance(value, int):
                logger.error(
                    "Status flags: fault=%s, target_reached=%s",
                    bool(value & STATUS_WORD_FAULT_BIT),
                    bool(value & STATUS_WORD_TARGET_REACHED_BIT),
                )

    def log_failure(
        self,
        *,
        iteration: int,
        target: int,
        last_position: Optional[int],
    ) -> None:
        """Log motion registers and the drive error buffer after a failure.

        Args:
            iteration: Movement iteration active during the failure.
            target: Requested position.
            last_position: Last position read successfully, if available.
        """
        self.log_motion_state(
            iteration=iteration,
            target=target,
            last_position=last_position,
        )
        self.log_errors()

    def fail_sdo(
        self,
        exception: ILRegisterAccessError,
        *,
        context: str,
        iteration: int,
        target: int,
        last_position: Optional[int],
        successful_reads: int,
        elapsed: float,
    ) -> None:
        """Log an SDO failure and fail the active test.

        Args:
            exception: Register-access exception raised by IngeniaLink.
            context: Operation being performed when the failure occurred.
            iteration: Current movement iteration.
            target: Requested or held position.
            last_position: Last position read successfully, if available.
            successful_reads: Number of successful reads before failure.
            elapsed: Seconds elapsed in the current operation.
        """
        base_exception = exception.base_exception
        logger.error(
            "SDO failure: context=%s, iteration=%s, target=%s, "
            "last_position=%s, successful_reads=%s, elapsed=%s, "
            "exception=%s, reason=%s, wkc=%s",
            context,
            iteration,
            target,
            last_position,
            successful_reads,
            elapsed,
            type(base_exception).__name__,
            exception.reason,
            getattr(base_exception, "wkc", None),
        )
        self.log_failure(
            iteration=iteration,
            target=target,
            last_position=last_position,
        )
        pytest.fail(
            f"SDO failure during {context}: iteration={iteration}, "
            f"target={target}, last_position={last_position}, "
            f"successful_reads={successful_reads}, elapsed={elapsed}, "
            f"reason={exception.reason}, "
            f"wkc={getattr(base_exception, 'wkc', None)}"
        )

    def wait_for_target(self, target: int, iteration: int) -> None:
        """Wait for a movement target and diagnose its first failure.

        Args:
            target: Target position of the current movement.
            iteration: Zero-based movement iteration.
        """
        start_time = time.monotonic()
        last_change_time = start_time
        last_position: Optional[int] = None
        successful_reads = 0

        while True:
            elapsed = time.monotonic() - start_time
            try:
                position = self.read_position()
                successful_reads += 1
            except ILRegisterAccessError as exception:
                self.fail_sdo(
                    exception,
                    context="movement",
                    iteration=iteration,
                    target=target,
                    last_position=last_position,
                    successful_reads=successful_reads,
                    elapsed=elapsed,
                )

            if position != last_position:
                last_position = position
                last_change_time = time.monotonic()

            if abs(target - position) < self.settings.position_tolerance:
                logger.info(
                    "Iteration %s completed: target=%s, position=%s, reads=%s, elapsed=%s",
                    iteration,
                    target,
                    position,
                    successful_reads,
                    elapsed,
                )
                return

            stalled_for = time.monotonic() - last_change_time
            if stalled_for >= self.settings.stall_timeout:
                reason = f"Position stopped changing for {stalled_for} seconds"
            elif elapsed >= self.settings.movement_timeout:
                reason = f"Position was not reached after {elapsed} seconds"
            else:
                time.sleep(self.settings.polling_interval)
                continue

            self.log_failure(
                iteration=iteration,
                target=target,
                last_position=position,
            )
            pytest.fail(
                f"{reason}: iteration={iteration}, target={target}, "
                f"last_position={position}, successful_reads={successful_reads}"
            )

    def run_stationary(self, *, motor_enabled: bool, duration: float) -> None:
        """Monitor position feedback while the motor remains stationary.

        Historical errors are captured as a baseline. The test fails only when
        the buffer changes during this run, the drive enters fault, position
        moves outside tolerance, or an SDO read fails.

        Args:
            motor_enabled: Whether the motor must hold its current position.
            duration: Number of seconds to monitor the stationary condition.
        """
        initial_errors = self.capture_error_baseline()
        position_before_test = self.read_position()
        initial_position = (
            self.enable_motor_holding_current_position() if motor_enabled else position_before_test
        )
        set_point = self.read_register("CL_POS_SET_POINT_VALUE")
        status_word = self.read_register("DRV_STATE_STATUS")

        if motor_enabled:
            assert abs(set_point - initial_position) <= self.settings.position_tolerance, (
                "The motor is not holding its current position: "
                f"position={initial_position}, set_point={set_point}"
            )

        logger.info(
            "Starting stationary encoder stress test: motor_enabled=%s, "
            "position_before_test=%s, initial_position=%s, set_point=%s, "
            "status_word=%s, initial_errors=%s, duration=%s",
            motor_enabled,
            position_before_test,
            initial_position,
            set_point,
            hex(status_word),
            initial_errors,
            duration,
        )

        start_time = time.monotonic()
        last_diagnostic_time = start_time
        minimum_position = initial_position
        maximum_position = initial_position
        successful_reads = 0
        position = initial_position

        while time.monotonic() - start_time < duration:
            elapsed = time.monotonic() - start_time
            try:
                position = self.read_position()
                successful_reads += 1
            except ILRegisterAccessError as exception:
                self.fail_sdo(
                    exception,
                    context="stationary test",
                    iteration=0,
                    target=initial_position,
                    last_position=position,
                    successful_reads=successful_reads,
                    elapsed=elapsed,
                )

            minimum_position = min(minimum_position, position)
            maximum_position = max(maximum_position, position)
            if abs(position - initial_position) > self.settings.position_tolerance:
                self.log_failure(
                    iteration=0,
                    target=initial_position,
                    last_position=position,
                )
                pytest.fail(
                    "Position changed outside stationary tolerance: "
                    f"motor_enabled={motor_enabled}, initial={initial_position}, "
                    f"current={position}, minimum={minimum_position}, "
                    f"maximum={maximum_position}, elapsed={elapsed}"
                )

            if time.monotonic() - last_diagnostic_time >= self.settings.diagnostic_interval:
                last_diagnostic_time = time.monotonic()
                status_word = self.read_register("DRV_STATE_STATUS")
                current_errors = self.get_error_buffer()
                error_buffer_changed = current_errors != initial_errors
                drive_faulted = bool(status_word & STATUS_WORD_FAULT_BIT)

                if error_buffer_changed or drive_faulted:
                    self.log_failure(
                        iteration=0,
                        target=initial_position,
                        last_position=position,
                    )
                    pytest.fail(
                        "Drive state changed while stationary: "
                        f"motor_enabled={motor_enabled}, elapsed={elapsed}, "
                        f"status_word={hex(status_word)}, "
                        f"initial_errors={initial_errors}, "
                        f"current_errors={current_errors}"
                    )

            time.sleep(self.settings.polling_interval)

        final_errors = self.get_error_buffer()
        logger.info(
            "Stationary encoder stress test completed: motor_enabled=%s, "
            "initial=%s, last=%s, minimum=%s, maximum=%s, reads=%s, "
            "initial_errors=%s, final_errors=%s, elapsed=%s",
            motor_enabled,
            initial_position,
            position,
            minimum_position,
            maximum_position,
            successful_reads,
            initial_errors,
            final_errors,
            time.monotonic() - start_time,
        )
        assert final_errors == initial_errors, (
            "The drive error buffer changed during the stationary test: "
            f"motor_enabled={motor_enabled}, initial_errors={initial_errors}, "
            f"final_errors={final_errors}"
        )


@pytest.fixture
def encoder_debugger(
    mc: "MotionController",
    alias: str,
) -> Generator[EncoderDebugger, None, None]:
    """Create an encoder debugger and disable its motor after each test.

    Args:
        mc: Motion-controller fixture.
        alias: Servo-alias fixture.

    Yields:
        Configured debugger for the connected servo.
    """
    debugger = EncoderDebugger(mc, alias, StressSettings())
    yield debugger
    debugger.disable_motor()


@pytest.mark.ethernet
@pytest.mark.soem
def test_position_feedback_stationary_motor_disabled(
    encoder_debugger: EncoderDebugger,
) -> None:
    """Verify that no new encoder errors appear with the power stage disabled."""
    encoder_debugger.run_stationary(
        motor_enabled=False,
        duration=STATIONARY_TEST_DURATION_S,
    )


@pytest.mark.ethernet
@pytest.mark.soem
def test_position_feedback_stationary_motor_enabled(
    encoder_debugger: EncoderDebugger,
) -> None:
    """Verify that no new encoder errors appear while holding position."""
    encoder_debugger.run_stationary(
        motor_enabled=True,
        duration=STATIONARY_TEST_DURATION_S,
    )


@pytest.mark.ethernet
@pytest.mark.soem
def test_position_feedback_repeated_motion(
    encoder_debugger: EncoderDebugger,
) -> None:
    """Alternate position targets and stop at the first motion or SDO failure."""
    debugger = encoder_debugger
    debugger.enable_motor_holding_current_position()

    for iteration in range(MOVEMENT_ITERATIONS):
        target = 1000 if iteration % 2 == 0 else -1000
        debugger.mc.motion.move_to_position(
            target,
            servo=debugger.alias,
            blocking=False,
        )
        debugger.wait_for_target(target, iteration)


@pytest.mark.ethernet
@pytest.mark.soem
def test_position_feedback_sdo_timeout_sweep(
    mc: "MotionController",
    alias: str,
    net: "EthercatNetwork",
) -> None:
    """Characterize SDO reads while sweeping the configured read timeout.

    The experiment is nondeterministic, so absence of a WKC failure is logged
    rather than treated as a test failure. Every timeout is restored before the
    recovery read and again during final cleanup.

    Args:
        mc: Motion-controller fixture.
        alias: Servo-alias fixture.
        net: EtherCAT-network fixture.
    """
    normal_read_timeout_us = 2_000_000
    normal_write_timeout_us = 2_000_000
    tested_read_timeouts_us = (1, 10, 100, 1_000, 10_000)
    results: list[dict[str, Any]] = []

    def set_read_timeout(read_timeout_us: int) -> None:
        """Set the SDO read timeout while retaining the normal write timeout."""
        net.update_sdo_timeout(read_timeout_us, normal_write_timeout_us)

    def restore_timeouts() -> None:
        """Restore explicit normal SDO read and write timeout values."""
        set_read_timeout(normal_read_timeout_us)

    restore_timeouts()
    mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION, servo=alias)
    mc.motion.motor_enable(servo=alias)

    try:
        for iteration, read_timeout_us in enumerate(tested_read_timeouts_us):
            target = 1000 if iteration % 2 == 0 else -1000
            successful_reads = 0
            failure: Optional[SdoFailure] = None

            restore_timeouts()
            mc.motion.move_to_position(target, servo=alias, blocking=False)
            set_read_timeout(read_timeout_us)
            start_time = time.monotonic()

            try:
                while time.monotonic() - start_time < 2.0:
                    try:
                        position = mc.motion.get_actual_position(servo=alias)
                        successful_reads += 1
                    except ILRegisterAccessError as exception:
                        base_exception = exception.base_exception
                        failure = {
                            "exception": type(base_exception).__name__,
                            "reason": exception.reason,
                            "wkc": getattr(base_exception, "wkc", None),
                            "elapsed": time.monotonic() - start_time,
                        }
                        break

                    if abs(target - position) < 20:
                        break
                    time.sleep(0.001)
            finally:
                restore_timeouts()

            result: dict[str, Any] = {
                "read_timeout_us": read_timeout_us,
                "successful_reads": successful_reads,
                "failure": failure,
                "recovered_position": mc.motion.get_actual_position(servo=alias),
            }
            results.append(result)
            logger.info("SDO timeout sweep result: %s", result)

        wkc_failures = [
            result
            for result in results
            if result["failure"] is not None and result["failure"]["exception"] == "WkcError"
        ]
        if wkc_failures:
            logger.info(
                "The timeout sweep reproduced %s WKC failure(s): %s",
                len(wkc_failures),
                wkc_failures,
            )
        else:
            logger.info(
                "The timeout sweep did not reproduce a WKC failure. Results: %s",
                results,
            )
    finally:
        restore_timeouts()
        try:
            mc.motion.motor_disable(servo=alias)
        except Exception as exception:
            logger.warning(
                "Could not disable motor during cleanup: %s: %s",
                type(exception).__name__,
                exception,
            )

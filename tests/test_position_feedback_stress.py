"""Stress tests for intermittent EtherCAT and BiSS-C position-feedback failures.

The tests compare position-feedback behavior with the motor disabled, with the
motor enabled while holding position, and during repeated position movements.
The tests stop at the first newly generated drive warning, fault, or SDO error
so that diagnostics describe the event that started the failure sequence.
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
    from ingeniamotion.motion_controller import MotionController


logger = get_logger(__name__)

DriveError = tuple[int, Optional[int], Optional[bool]]
MOTION_REGISTERS = (
    "DRV_STATE_CONTROL",
    "DRV_STATE_STATUS",
    "DRV_OP_CMD",
    "DRV_OP_VALUE",
    "CL_POS_SET_POINT_VALUE",
    "CL_POS_FBK_VALUE",
    "CL_VEL_FBK_VALUE",
    "CL_CUR_Q_VALUE",
    "CL_CUR_D_VALUE",
)
STATUS_WORD_FAULT_BIT = 0x0008
STATUS_WORD_TARGET_REACHED_BIT = 0x0800
MAX_ERROR_BUFFER_SIZE = 32
STATIONARY_TEST_DURATION_S = 120.0
MOVEMENT_ITERATIONS = 1_000


@dataclass(frozen=True)
class StressSettings:
    """Timing and tolerance settings shared by the feedback stress tests."""

    position_tolerance: int = 20
    """Maximum accepted distance from a target position."""

    movement_timeout: float = 10.0
    """Maximum time allowed for one position movement."""

    stall_timeout: float = 1.0
    """Maximum time that position may remain unchanged while the target has not been reached."""

    polling_interval: float = 0.01
    """Delay between consecutive position reads."""

    diagnostic_interval: float = 0.1
    """Delay between status and error-buffer checks."""

    settling_time: float = 1.0
    """Delay after commanding the motor to hold its position."""


class EncoderDebugger:
    """Provide reusable setup, polling, diagnostics, and cleanup operations."""

    def __init__(self, mc: "MotionController", alias: str, settings: "StressSettings") -> None:
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
        """Enable profile-position mode while holding the current position.

        The hold target is configured before enabling the power stage to prevent
        the drive from activating a stale profile-position target.

        Returns:
            Position measured after the position loop has settled.
        """
        self.mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION, servo=self.alias)
        position = self.read_position()
        self.mc.motion.move_to_position(position, servo=self.alias, blocking=False)
        configured_set_point = self.read_register("CL_POS_SET_POINT_VALUE")

        assert abs(configured_set_point - position) <= (self.settings.position_tolerance), (
            "The hold target was not configured before motor enable: "
            f"position={position}, "
            f"configured_set_point={configured_set_point}"
        )

        self.mc.motion.motor_enable(servo=self.alias)
        self.motor_enabled = True

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
                f"Could not disable motor during cleanup: {type(exception).__name__}: {exception}"
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

    def get_error_buffer(self) -> list["DriveError"]:
        """Read the drive error buffer, newest entry first.

        Returns:
            Raw error tuples containing code, axis, and warning state.
        """
        total_errors = self.mc.errors.get_number_total_errors(servo=self.alias, axis=1)
        return [
            self.mc.errors.get_buffer_error_by_index(index, servo=self.alias, axis=1)
            for index in range(min(total_errors, MAX_ERROR_BUFFER_SIZE))
        ]

    def capture_error_baseline(self) -> list["DriveError"]:
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
                f"during this test will be considered. Initial errors: {errors}",
            )
        return errors

    def log_error(self, label: str, error: Optional["DriveError"]) -> None:
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
                f"{label}: code={error_code} (0x{error_code:04X}), axis={error_axis}, "
                f"warning={is_warning}; description unavailable: {type(exception).__name__}: "
                f"{exception}",
            )
            return

        logger.error(
            f"{label}: code={error_code} (0x{error_code:04X}), axis={error_axis}, "
            f"warning={is_warning}, id={error_id}, module={module}, type={error_type}, "
            f"message={message}",
        )

    def log_errors(self) -> None:
        """Log the current error and every available buffered error."""
        getters: tuple[tuple[str, Callable[[], Optional[DriveError]]], ...] = (
            ("Last drive error", lambda: self.mc.errors.get_last_error(servo=self.alias, axis=1)),
            (
                "Last buffered error",
                lambda: self.mc.errors.get_last_buffer_error(servo=self.alias, axis=1),
            ),
        )
        for label, getter in getters:
            try:
                self.log_error(label, getter())
            except Exception as exception:  # noqa: PERF203
                logger.error(
                    f"Could not read {label.lower()}: {type(exception).__name__}: {exception}"
                )

        try:
            errors = self.get_error_buffer()
        except Exception as exception:
            logger.error(f"Could not read buffered errors: {type(exception).__name__}: {exception}")
            return

        logger.error(f"Total buffered errors: {len(errors)}")
        for index, error in enumerate(errors):
            self.log_error(f"Buffered error {index}", error)

    def log_motion_state(
        self, *, iteration: int, target: int, last_position: Optional[int]
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
                    f"{register} could not be read: {type(exception).__name__}: {exception}"
                )
                continue

            if register in {"DRV_STATE_CONTROL", "DRV_STATE_STATUS"}:
                hexadecimal = hex(value) if isinstance(value, int) else "not integer"
                logger.error(f"{register}={value} ({hexadecimal})")
            else:
                logger.error(f"{register}={value}")

            if register == "DRV_STATE_STATUS" and isinstance(value, int):
                logger.error(
                    f"Status flags: fault={bool(value & STATUS_WORD_FAULT_BIT)}, "
                    f"target_reached={bool(value & STATUS_WORD_TARGET_REACHED_BIT)}",
                )

    def log_failure(self, *, iteration: int, target: int, last_position: Optional[int]) -> None:
        """Log motion registers and the drive error buffer after a failure.

        Args:
            iteration: Movement iteration active during the failure.
            target: Requested position.
            last_position: Last position read successfully, if available.
        """
        self.log_motion_state(iteration=iteration, target=target, last_position=last_position)
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
            f"SDO failure: context={context}, iteration={iteration}, target={target}, "
            f"last_position={last_position}, successful_reads={successful_reads}, elapsed={elapsed}"
            f", exception={type(base_exception).__name__}, reason={exception.reason}, "
            f"wkc={getattr(base_exception, 'wkc', None)}",
        )
        self.log_failure(iteration=iteration, target=target, last_position=last_position)
        pytest.fail(
            f"SDO failure during {context}: iteration={iteration}, "
            f"target={target}, last_position={last_position}, "
            f"successful_reads={successful_reads}, elapsed={elapsed}, "
            f"reason={exception.reason}, "
            f"wkc={getattr(base_exception, 'wkc', None)}"
        )

    def wait_for_target(
        self, target: int, iteration: int, initial_errors: list["DriveError"]
    ) -> None:
        """Wait for a movement target and diagnose its first abnormal event.

        This method also polls the drive error buffer, making the test stop at
        the first BiSS-C warning instead of waiting for a final CRC fault.

        Args:
            target: Target position of the current movement.
            iteration: Zero-based movement iteration.
            initial_errors: Error-buffer snapshot captured before motion starts.
        """
        start_time = time.monotonic()
        last_change_time = start_time
        last_diagnostic_time = start_time
        last_position: Optional[int] = None
        successful_reads = 0

        while True:
            current_time = time.monotonic()
            elapsed = current_time - start_time
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

            if current_time - last_diagnostic_time >= self.settings.diagnostic_interval:
                last_diagnostic_time = current_time
                try:
                    status_word = self.read_register("DRV_STATE_STATUS")
                    current_errors = self.get_error_buffer()
                except ILRegisterAccessError as exception:
                    self.fail_sdo(
                        exception,
                        context="movement diagnostics",
                        iteration=iteration,
                        target=target,
                        last_position=position,
                        successful_reads=successful_reads,
                        elapsed=elapsed,
                    )

                if current_errors != initial_errors or status_word & STATUS_WORD_FAULT_BIT:
                    self.log_failure(iteration=iteration, target=target, last_position=position)
                    pytest.fail(
                        "Drive state changed during repeated motion: "
                        f"iteration={iteration}, target={target}, position={position}, "
                        f"elapsed={elapsed}, status_word={hex(status_word)}, "
                        f"initial_errors={initial_errors}, "
                        f"current_errors={current_errors}"
                    )

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
            f"Starting stationary encoder stress test: motor_enabled={motor_enabled}, "
            f"position_before_test={position_before_test}, initial_position={initial_position}, "
            f"set_point={set_point}, status_word={hex(status_word)}, "
            f"initial_errors={initial_errors}, duration={duration}",
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
            f"Stationary encoder stress test completed: motor_enabled={motor_enabled}, "
            f"initial={initial_position}, last={position}, minimum={minimum_position}, "
            f"maximum={maximum_position}, reads={successful_reads}, "
            f"initial_errors={initial_errors}, final_errors={final_errors}, "
            f"elapsed={time.monotonic() - start_time}",
        )
        assert final_errors == initial_errors, (
            "The drive error buffer changed during the stationary test: "
            f"motor_enabled={motor_enabled}, initial_errors={initial_errors}, "
            f"final_errors={final_errors}"
        )

    def run_motor_enable_transition_test(self, *, observation_duration: float) -> None:
        """Monitor encoder errors generated immediately after motor enable.

        The current position is commanded before enabling the power stage. This
        avoids activating a stale profile-position target during motor_enable().
        The test then monitors position, drive status, and the error buffer from
        the moment motor_enable() returns.

        Args:
            observation_duration: Number of seconds to monitor after motor enable.
        """
        initial_errors = self.get_error_buffer()
        assert not initial_errors, (
            "The motor-enable transition test requires an empty error buffer. "
            "Power-cycle or reset the drive before running this test. "
            f"Initial errors: {initial_errors}"
        )

        self.mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION, servo=self.alias)

        initial_position = self.read_position()

        # Preload the desired hold position while the motor is still disabled.
        # This prevents an old profile-position target from becoming active as
        # soon as the power stage is enabled.
        self.mc.motion.move_to_position(initial_position, servo=self.alias, blocking=False)

        configured_set_point = self.read_register("CL_POS_SET_POINT_VALUE")

        assert abs(configured_set_point - initial_position) <= (self.settings.position_tolerance), (
            "The hold target was not configured before motor enable: "
            f"initial_position={initial_position}, "
            f"configured_set_point={configured_set_point}"
        )

        logger.info(
            f"Starting motor-enable transition test: "
            f"initial_position={initial_position}, configured_set_point={configured_set_point}, "
            f"initial_errors={initial_errors}, observation_duration={observation_duration}",
        )

        enable_start_time = time.monotonic()

        self.mc.motion.motor_enable(servo=self.alias)
        self.motor_enabled = True

        motor_enabled_time = time.monotonic()

        position_after_enable = self.read_position()
        errors_after_enable = self.get_error_buffer()
        status_after_enable = self.read_register("DRV_STATE_STATUS")

        logger.info(
            f"Motor enable completed: duration={motor_enabled_time - enable_start_time}, "
            f"position_before_enable={initial_position}, "
            f"position_after_enable={position_after_enable}, "
            f"position_change={abs(position_after_enable - initial_position)}, "
            f"status_word={hex(status_after_enable)}, errors={errors_after_enable}",
        )

        if errors_after_enable != initial_errors:
            self.log_failure(
                iteration=0, target=initial_position, last_position=position_after_enable
            )

            pytest.fail(
                "Encoder warning or fault was generated inside motor_enable(): "
                f"enable_duration={motor_enabled_time - enable_start_time}, "
                f"initial_position={initial_position}, "
                f"position_after_enable={position_after_enable}, "
                f"initial_errors={initial_errors}, "
                f"errors_after_enable={errors_after_enable}"
            )

        minimum_position = min(initial_position, position_after_enable)
        maximum_position = max(initial_position, position_after_enable)
        successful_reads = 0
        last_position = position_after_enable

        while True:
            current_time = time.monotonic()
            elapsed_since_enable = current_time - motor_enabled_time

            if elapsed_since_enable >= observation_duration:
                break

            try:
                last_position = self.read_position()
                status_word = self.read_register("DRV_STATE_STATUS")
                current_errors = self.get_error_buffer()
                successful_reads += 1
            except ILRegisterAccessError as exception:
                self.fail_sdo(
                    exception,
                    context="motor-enable transition",
                    iteration=0,
                    target=initial_position,
                    last_position=last_position,
                    successful_reads=successful_reads,
                    elapsed=elapsed_since_enable,
                )

            minimum_position = min(minimum_position, last_position)
            maximum_position = max(maximum_position, last_position)

            position_change = abs(last_position - initial_position)
            drive_faulted = bool(status_word & STATUS_WORD_FAULT_BIT)
            error_buffer_changed = current_errors != initial_errors

            if error_buffer_changed or drive_faulted:
                logger.error(
                    "Drive state changed after motor enable: "
                    f"elapsed_since_enable={elapsed_since_enable}, "
                    f"initial_position={initial_position}, "
                    f"last_position={last_position}, position_change={position_change}, "
                    f"status_word={hex(status_word)}, initial_errors={initial_errors}, "
                    f"current_errors={current_errors}",
                )

                self.log_failure(iteration=0, target=initial_position, last_position=last_position)

                pytest.fail(
                    "Encoder warning or fault generated after motor enable: "
                    f"elapsed_since_enable={elapsed_since_enable}, "
                    f"initial_position={initial_position}, "
                    f"last_position={last_position}, "
                    f"position_change={position_change}, "
                    f"status_word={hex(status_word)}, "
                    f"initial_errors={initial_errors}, "
                    f"current_errors={current_errors}"
                )

            if position_change > self.settings.position_tolerance:
                self.log_failure(iteration=0, target=initial_position, last_position=last_position)

                pytest.fail(
                    "Motor moved outside tolerance after motor enable: "
                    f"elapsed_since_enable={elapsed_since_enable}, "
                    f"initial_position={initial_position}, "
                    f"last_position={last_position}, "
                    f"position_change={position_change}, "
                    f"minimum_position={minimum_position}, "
                    f"maximum_position={maximum_position}"
                )

            time.sleep(self.settings.polling_interval)

        final_errors = self.get_error_buffer()

        logger.info(
            "Motor-enable transition test completed: "
            f"initial_position={initial_position}, last_position={last_position}, "
            f"minimum_position={minimum_position}, maximum_position={maximum_position}, "
            f"successful_reads={successful_reads}, initial_errors={initial_errors}, "
            f"final_errors={final_errors}, elapsed={time.monotonic() - motor_enabled_time}",
        )

        assert final_errors == initial_errors, (
            "The error buffer changed during the motor-enable transition test: "
            f"initial_errors={initial_errors}, "
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
    initial_errors = debugger.capture_error_baseline()
    initial_position = debugger.enable_motor_holding_current_position()
    logger.info(
        f"Starting repeated-motion stress test: initial_position={initial_position}, "
        f"initial_errors={initial_errors}, iterations={MOVEMENT_ITERATIONS}",
    )

    for iteration in range(MOVEMENT_ITERATIONS):
        target = 1000 if iteration % 2 == 0 else -1000
        debugger.mc.motion.move_to_position(
            target,
            servo=debugger.alias,
            blocking=False,
        )
        debugger.wait_for_target(target, iteration, initial_errors)


@pytest.mark.ethernet
@pytest.mark.soem
def test_position_feedback_motor_enable_transition(
    encoder_debugger: EncoderDebugger,
) -> None:
    """Check for encoder warnings immediately after enabling the power stage."""
    encoder_debugger.run_motor_enable_transition_test(
        observation_duration=10.0,
    )

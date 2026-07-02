import math
from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, Final, Optional, Union, cast

import ingenialogger
from typing_extensions import override

from ingeniamotion.enums import (
    MonitoringProcessStage,
    MonitoringSoCConfig,
    MonitoringSoCType,
    OperationMode,
    PhasingMode,
    SensorCategory,
    SensorType,
    SeverityLevel,
)
from ingeniamotion.exceptions import IMRegisterNotExistError
from ingeniamotion.wizard_tests.base_test import BaseTest, ReportBase, TestError

if TYPE_CHECKING:
    from ingeniamotion import MotionController
    from ingeniamotion.monitoring.base_monitoring import Monitoring


COMMUTATION_ANGLE_VALUE_REGISTER = "COMMU_ANGLE_VALUE"
COMMUTATION_ANGLE_OFFSET_REGISTER = "COMMU_ANGLE_OFFSET"
REFERENCE_ANGLE_VALUE_REGISTER = "COMMU_ANGLE_REF_VALUE"
REFERENCE_ANGLE_OFFSET_REGISTER = "COMMU_ANGLE_REF_OFFSET"
MAX_CURRENT_REGISTER = "CL_CUR_REF_MAX"
PEAK_CURRENT_REGISTER = "DRV_PROT_I2T_PEAK_VALUE"


def circular_mean(values: list[float]) -> float:
    """Mean of values defined on the circular ``[0, 1)`` domain.

    A plain arithmetic mean is wrong near the 0/1 boundary (e.g. 0.99 and 0.01
    should average to 0.0, not 0.5). Each value is mapped to an angle, the unit
    vectors are averaged, and the result is mapped back to ``[0, 1)``.

    Args:
        values: Values in the ``[0, 1)`` domain.

    Returns:
        The circular mean in ``[0, 1)``.
    """
    angles = [v * 2 * math.pi for v in values]
    mean_sin = sum(math.sin(a) for a in angles) / len(angles)
    mean_cos = sum(math.cos(a) for a in angles) / len(angles)
    return (math.atan2(mean_sin, mean_cos) / (2 * math.pi)) % 1


def circular_distance(value1: float, value2: float) -> float:
    """Shortest wrap-around distance between two values on the ``[0, 1)`` domain.

    Args:
        value1: First value.
        value2: Second value.

    Returns:
        The shortest distance in ``[0, 0.5]``.
    """
    distance = abs(value1 - value2) % 1
    return min(distance, 1 - distance)


@dataclass
class DynamicForcedPhasingReport(ReportBase):
    """Report for the Dynamic Forced Phasing test."""

    commutation_angle: float
    """Commutation angle value."""

    commutation_phasing_mode: PhasingMode
    """Commutation phasing mode."""


class PhasingDirection(IntEnum):
    """Direction of the phasing movement."""

    POSITIVE = 1
    NEGATIVE = -1


class DynamicForcedPhasing(BaseTest[DynamicForcedPhasingReport]):
    """Dynamic Forced Phasing test.

    Test measures the commutation and reference angle of a motor avoiding static friction effects.
    Commutation and reference feedbacks must be the same and absolute.
    """

    GENERATOR_FREQUENCIES: Final[list[float]] = [0.1, 0.03, 0.01]
    """Logarithmically spaced frequencies (Hz) tried in descending order."""
    MAX_ATTEMPTS_PER_FREQUENCY: Final[int] = 2
    """Number of monitoring reads attempted at each frequency before escalating."""
    NORM_TOLERANCE: Final[float] = 0.02
    """Maximum allowed difference between the signals to consider them constant."""
    SYMMETRY_ERROR_TOLERANCE: Final[float] = 0.10
    """Maximum allowed asymmetry error between the signals."""
    PHASING_CURRENT_PERCENTAGE: Final[float] = 0.4
    """Percentage of the rated current used for phasing in non-geared motors."""
    PHASING_CURRENT_PERCENTAGE_GEAR: Final[float] = 0.8
    """Percentage of the rated current used for phasing in geared motors."""
    CURRENT_RAMP_TIME_S: Final[float] = 1.0
    """Time in seconds to ramp the current to the phasing max current."""

    def __init__(
        self,
        mc: "MotionController",
        servo: str,
        axis: int,
        phasing_max_current: Optional[float] = None,
        spin_frequency: Optional[float] = None,
        logger_drive_name: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.mc = mc
        self.servo = servo
        self.axis = axis
        self.__monitoring: Optional[Monitoring] = None
        if logger_drive_name is None:
            self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=mc.servo_name(servo))
        else:
            self.logger = ingenialogger.get_logger(__name__, axis=axis, drive=logger_drive_name)

        self._phasing_max_current_override = phasing_max_current
        self.phasing_max_current: float = 0.0
        if spin_frequency is None:
            self.spin_frequency = self.GENERATOR_FREQUENCIES
        elif spin_frequency <= 0:
            raise ValueError("Spin frequency must be positive.")
        else:
            self.spin_frequency = [spin_frequency]

    @property
    def monitoring(self) -> "Monitoring":
        """Get the monitoring object.

        Raises:
            ValueError: If the monitoring has not been configured yet.
        """
        if self.__monitoring is None:
            raise ValueError("Monitoring has not been configured yet.")
        return self.__monitoring

    @BaseTest.stoppable
    def __set_error_event_to_warning(self) -> None:
        """Set the error event to warning to avoid stopping the test if the events are triggered."""
        try:
            self.mc.communication.set_register(
                "COMMU_ANGLE_INTEGRITY1_OPTION", 1, servo=self.servo, axis=self.axis
            )
        except IMRegisterNotExistError:
            self.logger.warning("Could not write COMMU_ANGLE_INTEGRITY1_OPTION")

        try:
            self.mc.communication.set_register(
                "COMMU_ANGLE_INTEGRITY2_OPTION", 1, servo=self.servo, axis=self.axis
            )
        except IMRegisterNotExistError:
            self.logger.warning("Could not write COMMU_ANGLE_INTEGRITY2_OPTION")

    @BaseTest.stoppable
    def __check_initial_state(self) -> None:
        """Check that the drive is in a valid state to start the test.

        The requirements are:
            - The drive should support monitoring.
            - The selected current must not exceed the current limits.
            - Commutation and reference feedback sensors must be the same and absolute.


        Raises:
            TestError: If the motor is not in a valid state to start the test.
            ValueError: If the max current drive or current motor peak are not floats.
        """
        try:
            self.mc.capture._check_version(servo=self.servo)
        except NotImplementedError as e:
            raise TestError(e)
        self.__resolve_phasing_max_current()

        comm = self.mc.configuration.get_commutation_feedback(servo=self.servo, axis=self.axis)
        ref = self.mc.configuration.get_reference_feedback(servo=self.servo, axis=self.axis)

        if ref == SensorType.INTGEN or comm == SensorType.INTGEN:
            raise TestError(
                "Reference or commutation feedback sensor are set to internal generator"
            )

        if (
            self.mc.configuration.get_reference_feedback_category(servo=self.servo, axis=self.axis)
            != SensorCategory.ABSOLUTE
        ):
            raise TestError("Reference feedback sensor is not absolute")

        if comm != ref:
            raise TestError("Commutation and reference feedback sensors are not the same.")

    @BaseTest.stoppable
    def __configure_open_loop_movement(self) -> None:
        """Configure the motor for open loop movement with zero current and zero offsets."""
        pair_poles = self.mc.configuration.get_motor_pair_poles(servo=self.servo, axis=self.axis)
        self.mc.motion.set_internal_generator_configuration(
            OperationMode.CURRENT,
            servo=self.servo,
            axis=self.axis,
            pair_poles=pair_poles,
        )
        self.mc.motion.set_current_direct(0, servo=self.servo, axis=self.axis)
        self.mc.motion.set_current_quadrature(0, servo=self.servo, axis=self.axis)
        self.mc.communication.set_register(
            COMMUTATION_ANGLE_OFFSET_REGISTER, 0, servo=self.servo, axis=self.axis
        )
        self.mc.communication.set_register(
            REFERENCE_ANGLE_OFFSET_REGISTER, 0, servo=self.servo, axis=self.axis
        )

    @BaseTest.stoppable
    def __configure_monitoring(self, direction: PhasingDirection) -> None:
        """Configure the monitoring for the test based on the direction."""
        self.mc.capture.disable_monitoring(servo=self.servo)
        trigger_config = (
            MonitoringSoCConfig.TRIGGER_CONFIG_RISING
            if direction == PhasingDirection.POSITIVE
            else MonitoringSoCConfig.TRIGGER_CONFIG_FALLING
        )
        mon_registers: list[dict[str, Union[int, str]]] = [
            {"name": COMMUTATION_ANGLE_VALUE_REGISTER, "axis": self.axis},
            {"name": REFERENCE_ANGLE_VALUE_REGISTER, "axis": self.axis},
        ]
        self.__monitoring = self.mc.capture.create_monitoring(
            registers=mon_registers,
            prescaler=50,
            sample_time=1,
            trigger_mode=MonitoringSoCType.TRIGGER_EVENT_EDGE,
            trigger_config=trigger_config,
            trigger_signal={"name": COMMUTATION_ANGLE_VALUE_REGISTER, "axis": self.axis},
            trigger_value=0.5,
            servo=self.servo,
            start=True,
        )

    @BaseTest.stoppable
    def __resolve_phasing_max_current(self) -> None:
        """Resolve the phasing maximum current and check that it does not exceed the drive limits.

        If the phasing maximum current is provided as a test parameter, it will be used.
        Otherwise, it will be calculated based on the drive and motor limits.

        Raises:
            TestError: If the phasing max current is higher than the maximum allowed current.
            ValueError: If the max current drive or current motor peak are not floats.

        """
        max_current_drive = self.mc.communication.get_register(
            MAX_CURRENT_REGISTER, servo=self.servo, axis=self.axis
        )
        current_motor_peak = self.mc.communication.get_register(
            PEAK_CURRENT_REGISTER, servo=self.servo, axis=self.axis
        )
        if not isinstance(max_current_drive, float):
            raise ValueError(f"Invalid type for max_current_drive: {type(max_current_drive)}")
        if not isinstance(current_motor_peak, float):
            raise ValueError(f"Invalid type for current_motor_peak: {type(current_motor_peak)}")
        limit_current = min(current_motor_peak, max_current_drive)

        if self._phasing_max_current_override is not None:
            self.phasing_max_current = self._phasing_max_current_override
        else:
            pos_vel_ratio = self.mc.configuration.get_pos_to_vel_ratio(
                servo=self.servo, axis=self.axis
            )
            if pos_vel_ratio == 1:
                self.phasing_max_current = self.PHASING_CURRENT_PERCENTAGE * limit_current
            else:
                self.phasing_max_current = self.PHASING_CURRENT_PERCENTAGE_GEAR * limit_current

        if self.phasing_max_current > limit_current:
            raise TestError(
                f"Phasing max current ({self.phasing_max_current}) is higher than the "
                f"maximum allowed current of the drive ({max_current_drive}) "
                f"or the motor ({current_motor_peak})."
            )

    @override
    def setup(self) -> None:
        self.__check_initial_state()
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.__set_error_event_to_warning()
        self.__configure_open_loop_movement()

    @BaseTest.stoppable
    def __check_signals_difference_is_constant(
        self, signal1: list[float], signal2: list[float], tolerance_norm: float
    ) -> tuple[Optional[float], Optional[float]]:
        """This function check if the difference between two signals is constant.

        Calculates the mean difference between two signals and checks if the relative
        difference between each point and the mean difference is less than the tolerance.

        Args:
            signal1: The first signal to compare.
            signal2: The second signal to compare.
            tolerance_norm: The maximum allowed relative difference between the signals.


        Returns:
            float | None: The mean difference.
            float | None: The maximum difference error.

        Raises:
            ValueError: If the signals have different lengths.
        """
        if len(signal1) != len(signal2):
            raise ValueError("Signals must have the same length.")
        if len(signal1) == 0:
            return None, None

        differences = [(s1 - s2) % 1 for s1, s2 in zip(signal1, signal2)]
        mean_difference = circular_mean(differences)

        max_difference: float = 0.0
        for diff in differences:
            difference = circular_distance(diff, mean_difference)
            if difference > max_difference:
                max_difference = difference
            if difference > tolerance_norm:
                self.logger.debug(
                    f"mean difference: {mean_difference:.4f}, difference: {difference:.4f}"
                )
                return None, None

        self.logger.debug(
            f"mean difference: {mean_difference:.4f}, max difference: {max_difference:.4f}"
        )
        return mean_difference, max_difference

    def __monitoring_stopper(
        self, _mon_process_stage: MonitoringProcessStage, _current_progress: float
    ) -> None:
        """Callback function to check if the test was stopped during monitoring data reading."""
        self.check_stop()

    @BaseTest.stoppable
    def _collect_mean_difference(self, direction: PhasingDirection, tolerance_norm: float) -> float:
        """Move the motor and collect a stable mean angle difference.

        Tries up to ``MAX_ATTEMPTS_PER_FREQUENCY`` monitoring reads at each
        frequency in ``spin_frequency``. Returns the mean angle difference
        with the lowest maximum difference error.

        Args:
            direction: The direction of the movement.
            tolerance_norm: The maximum allowed difference between the signals.

        Returns:
            Mean angle difference between commutation and reference signals.

        Raises:
            TestError: If no constant difference is found at any frequency.

        """
        mean_tuples: list[tuple[float, float]] = []
        for frequency in self.spin_frequency:
            self.logger.debug(
                f"Trying generator frequency {frequency:.3g} Hz, direction {direction.name}"
            )
            self.mc.motion.internal_generator_saw_tooth_move(
                direction.value, 0, frequency, servo=self.servo, axis=self.axis
            )
            for attempt in range(1, self.MAX_ATTEMPTS_PER_FREQUENCY + 1):
                self.check_stop()
                data = self.monitoring.read_monitoring_data(
                    timeout=1 / frequency, progress_callback=self.__monitoring_stopper
                )
                iter_mean_tuple = self.__check_signals_difference_is_constant(
                    data[0], data[1], tolerance_norm
                )
                self.monitoring.rearm_monitoring()
                if iter_mean_tuple[0] is not None and iter_mean_tuple[1] is not None:
                    iter_mean_tuple = cast("tuple[float, float]", iter_mean_tuple)
                    self.logger.debug(
                        f"Constant difference found at {frequency:.3g} Hz "
                        f"(attempt {attempt}/{self.MAX_ATTEMPTS_PER_FREQUENCY})"
                    )
                    mean_tuples.append(iter_mean_tuple)
                    break
        if len(mean_tuples) == 0:
            raise TestError(
                f"Could not find a constant signal difference after trying all "
                f"frequencies: {self.spin_frequency}"
            )
        mean_tuples.sort(key=lambda x: x[1])
        return mean_tuples[0][0]

    @override
    def loop(self) -> DynamicForcedPhasingReport:
        self.mc.motion.motor_enable(servo=self.servo, axis=self.axis)
        self.check_stop()
        self.mc.motion.current_direct_ramp(
            self.phasing_max_current, self.CURRENT_RAMP_TIME_S, servo=self.servo, axis=self.axis
        )
        self.__configure_monitoring(direction=PhasingDirection.POSITIVE)
        mean_difference_pos = self._collect_mean_difference(
            direction=PhasingDirection.POSITIVE, tolerance_norm=self.NORM_TOLERANCE
        )
        self.__configure_monitoring(direction=PhasingDirection.NEGATIVE)
        mean_difference_neg = self._collect_mean_difference(
            direction=PhasingDirection.NEGATIVE, tolerance_norm=self.NORM_TOLERANCE
        )

        commutation_angle = circular_mean([mean_difference_pos, mean_difference_neg])
        asymmetry_error = circular_distance(mean_difference_pos, mean_difference_neg)
        self.logger.info(
            f"Commutation angle: {commutation_angle:.4f}, asymmetry: {asymmetry_error:.4f}"
        )
        severity = (
            SeverityLevel.SUCCESS
            if asymmetry_error < self.SYMMETRY_ERROR_TOLERANCE
            else SeverityLevel.WARNING
        )
        if severity == SeverityLevel.WARNING:
            msg = (
                f"Asymmetry error is higher than the {self.SYMMETRY_ERROR_TOLERANCE * 100:.0f}%."
                " Spin frequency may be too high."
            )
        else:
            msg = "Success"

        return DynamicForcedPhasingReport(
            result_severity=severity,
            result_message=msg,
            commutation_angle=commutation_angle,
            commutation_phasing_mode=PhasingMode.NO_PHASING,
        )

    @override
    def teardown(self) -> None:
        self.mc.motion.motor_disable(servo=self.servo, axis=self.axis)
        self.mc.capture.disable_monitoring(servo=self.servo)

    @override
    def get_result_msg(self, output: DynamicForcedPhasingReport) -> str:
        return output.result_message

    @override
    def get_result_severity(self, output: DynamicForcedPhasingReport) -> SeverityLevel:
        return output.result_severity

    @override
    def generate_report(self, output: DynamicForcedPhasingReport) -> DynamicForcedPhasingReport:
        """Generate report.

        Returns:
            The current tuning results.
        """
        return output

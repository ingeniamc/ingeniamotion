import time
from collections.abc import Generator
from typing import TYPE_CHECKING, Optional, Union

import ingenialogger
from ingenialink.exceptions import ILError

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController
from ingeniamotion.enums import GeneratorMode, OperationMode, PhasingMode, SensorType
from ingeniamotion.exceptions import IMTimeoutError
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO


class Motion:
    """Motion."""

    CONTROL_WORD_REGISTER = "DRV_STATE_CONTROL"
    OPERATION_MODE_REGISTER = "DRV_OP_CMD"
    OPERATION_MODE_DISPLAY_REGISTER = "DRV_OP_VALUE"
    POSITION_SET_POINT_REGISTER = "CL_POS_SET_POINT_VALUE"
    VELOCITY_SET_POINT_REGISTER = "CL_VEL_SET_POINT_VALUE"
    CURRENT_QUADRATURE_SET_POINT_REGISTER = "CL_CUR_Q_SET_POINT"
    CURRENT_DIRECT_SET_POINT_REGISTER = "CL_CUR_D_SET_POINT"
    VOLTAGE_QUADRATURE_SET_POINT_REGISTER = "CL_VOL_Q_SET_POINT"
    VOLTAGE_DIRECT_SET_POINT_REGISTER = "CL_VOL_D_SET_POINT"
    ACTUAL_POSITION_REGISTER = "CL_POS_FBK_VALUE"
    ACTUAL_VELOCITY_REGISTER = "CL_VEL_FBK_VALUE"
    ACTUAL_DIRECT_CURRENT_REGISTER = "CL_CUR_D_VALUE"
    ACTUAL_QUADRATURE_CURRENT_REGISTER = "CL_CUR_Q_VALUE"
    GENERATOR_FREQUENCY_REGISTER = "FBK_GEN_FREQ"
    GENERATOR_GAIN_REGISTER = "FBK_GEN_GAIN"
    GENERATOR_OFFSET_REGISTER = "FBK_GEN_OFFSET"
    GENERATOR_CYCLE_NUMBER_REGISTER = "FBK_GEN_CYCLES"
    GENERATOR_REARM_REGISTER = "FBK_GEN_REARM"

    STATUS_WORD_TARGET_REACHED_BIT = 0x800
    CONTROL_WORD_TARGET_LATCH_BIT = 0x200

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def target_latch(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> None:
        """Active target latch.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        control_word = self.mc.communication.get_register(
            self.CONTROL_WORD_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(control_word, int):
            raise TypeError("Control word register value has to be a integer")
        new_control_word = control_word & (~self.CONTROL_WORD_TARGET_LATCH_BIT)
        self.mc.communication.set_register(
            self.CONTROL_WORD_REGISTER, new_control_word, servo=servo, axis=axis
        )
        new_control_word = control_word | self.CONTROL_WORD_TARGET_LATCH_BIT
        self.mc.communication.set_register(
            self.CONTROL_WORD_REGISTER, new_control_word, servo=servo, axis=axis
        )

    def set_operation_mode(
        self,
        operation_mode: Union[OperationMode, int],
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Set operation mode to a target servo and axis.

        Args:
            operation_mode : operation mode, any of :class:`OperationMode`.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        """
        self.mc.communication.set_register(
            self.OPERATION_MODE_REGISTER, operation_mode, servo=servo, axis=axis
        )
        try:
            self.logger.debug(
                "Operation mode set to %s",
                OperationMode(operation_mode).name,
                axis=axis,
                drive=self.mc.servo_name(servo),
            )
        except ValueError:
            self.logger.debug(
                "Operation mode set to %s",
                operation_mode,
                axis=axis,
                drive=self.mc.servo_name(servo),
            )

    def get_operation_mode(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Union[OperationMode, int]:
        """Return current operation mode.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            Return current operation mode.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        operation_mode = self.mc.communication.get_register(
            self.OPERATION_MODE_DISPLAY_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(operation_mode, (OperationMode, int)):
            raise TypeError("Operation mode value has to be an integer or OperationMode type.")
        try:
            return OperationMode(operation_mode)
        except ValueError:
            return operation_mode

    def motor_enable(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> None:
        """Enable motor.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            ingenialink.exceptions.ILError: If the servo cannot enable the motor.

        """
        drive = self.mc._get_drive(servo)
        try:
            drive.enable(subnode=axis)
        except ILError as e:
            error_code, subnode, warning = self.mc.errors.get_last_buffer_error(
                servo=servo, axis=axis
            )
            error_id, _, _, error_msg = self.mc.errors.get_error_data(error_code, servo=servo)
            exception_type = type(e)
            raise exception_type(f"An error occurred enabling motor. Reason: {error_msg}")

    def motor_disable(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> None:
        """Disable motor.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        """
        drive = self.mc._get_drive(servo)
        try:
            is_motor_enabled = self.mc.configuration.is_motor_enabled(servo=servo, axis=axis)
        except ILError as e:
            self.logger.info(f"Unable to check if motor is enabled. Reason: {e}")
            return
        if is_motor_enabled:
            try:
                drive.disable(subnode=axis)
            except ILError as e:
                self.logger.info(f"Unable to disable the motor. Reason: {e}")

    def fault_reset(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> None:
        """Fault reset.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        """
        drive = self.mc._get_drive(servo)
        try:
            drive.fault_reset(axis)
        except ILError as e:
            self.logger.info(f"Unable to perform a fault reset. Reason: {e}")

    def move_to_position(
        self,
        position: int,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        target_latch: bool = True,
        blocking: bool = False,
        error: int = 20,
        timeout: Optional[float] = None,
        interval: Optional[float] = None,
    ) -> None:
        """Set position set point to a target servo and axis, in counts.

        Args:
            position : target position, in counts.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            target_latch : if ``True`` does target latch at the end.
                ``True`` by default.
            blocking : if ``True``, the function is blocked until the
                target position is reached. ``False`` by default.
            error : If blocking is enabled, allowed error between actual
                position and target position, in counts.
            timeout : If blocking is enabled, how many seconds to wait
                for the servo to reach the target position, if ``None`` it
                will wait forever. ``None`` by default.
            interval : If blocking is enabled, interval of time between
                actual position reads, in seconds. ``None`` by default.

        Raises:
            TypeError: If position is not an int.
            IMTimeoutError: If the target position is not reached in time.

        """
        self.mc.communication.set_register(
            self.POSITION_SET_POINT_REGISTER, position, servo=servo, axis=axis
        )
        if target_latch:
            self.target_latch(servo, axis)
        if blocking:
            if not target_latch:
                self.logger.warning(
                    "Target latch is disabled. Target position may not be reached.",
                    axis=axis,
                    drive=self.mc.servo_name(servo),
                )
            self.wait_for_position(position, servo, axis, error, timeout, interval)

    def set_velocity(
        self,
        velocity: float,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        target_latch: bool = True,
        blocking: bool = False,
        error: float = 0.1,
        timeout: Optional[float] = None,
        interval: Optional[float] = None,
    ) -> None:
        """Set velocity set point to a target servo and axis, in rev/s.

        Args:
            velocity : target velocity, in rev/s.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            target_latch : if ``True`` does target latch at the end.
                ``True`` by default.
            blocking : if ``True``, the function is blocked until the
                target position is reached. ``False`` by default.
            error : If blocking is enabled, allowed error between
                actual velocity and target velocity, in rev/s.
            timeout : If blocking is enabled, how many seconds to wait
                for the servo to reach the target velocity, if ``None`` it
                will wait forever. ``None`` by default.
            interval : If blocking is enabled, interval of time between
                actual velocity reads, in seconds. ``None`` by default.

        Raises:
            TypeError: If velocity is not a float.
            IMTimeoutError: If the target velocity is not reached in time.

        """
        self.mc.communication.set_register(
            self.VELOCITY_SET_POINT_REGISTER, velocity, servo=servo, axis=axis
        )
        if target_latch:
            self.target_latch(servo, axis)
        if blocking:
            if not target_latch:
                self.logger.warning(
                    "Target latch is disabled. Target velocity may not be reached.",
                    axis=axis,
                    drive=self.mc.servo_name(servo),
                )
            self.wait_for_velocity(velocity, servo, axis, error, timeout, interval)

    def set_current_quadrature(
        self, current: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set quadrature current set point to a target servo and axis, in A.

        Args:
            current : target quadrature current, in A.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If current is not a float.

        """
        self.mc.communication.set_register(
            self.CURRENT_QUADRATURE_SET_POINT_REGISTER, current, servo=servo, axis=axis
        )

    def set_current_direct(
        self, current: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set direct current set point to a target servo and axis, in A.

        Args:
            current : target direct current, in A.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If current is not a float.

        """
        self.mc.communication.set_register(
            self.CURRENT_DIRECT_SET_POINT_REGISTER, current, servo=servo, axis=axis
        )

    def set_voltage_quadrature(
        self, voltage: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set quadrature voltage set point to a target servo and axis, in V.

        Args:
            voltage : target quadrature voltage, in V.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If voltage is not a float.

        """
        self.mc.communication.set_register(
            self.VOLTAGE_QUADRATURE_SET_POINT_REGISTER, voltage, servo=servo, axis=axis
        )

    def set_voltage_direct(
        self, voltage: float, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set direct voltage set point to a target servo and axis, in V.

        Args:
            voltage : target direct voltage, in V.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If voltage is not a float.

        """
        self.mc.communication.set_register(
            self.VOLTAGE_DIRECT_SET_POINT_REGISTER, voltage, servo=servo, axis=axis
        )

    def current_quadrature_ramp(
        self,
        target_value: float,
        time_s: float,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        init_value: float = 0,
        interval: Optional[float] = None,
    ) -> None:
        """Generate a current quadrature ramp.

        Given a target value and a time in seconds, changes the current
        quadrature set-point linearly following a ramp. This function is
        blocked until target reached.

        Args:
            target_value : target value of the ramp.
            time_s : duration of the ramp, in seconds.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            init_value : initial value of the ramp. ``0`` by default.
            interval : time interval between register writes, in seconds.
                ``None`` by default, no interval.

        Raises:
            TypeError: If target_value or time_s is not a float.

        """
        for value in self.ramp_generator(init_value, target_value, time_s, interval):
            self.set_current_quadrature(value, servo=servo, axis=axis)

    def current_direct_ramp(
        self,
        target_value: float,
        time_s: float,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        init_value: float = 0,
        interval: Optional[float] = None,
    ) -> None:
        """Generate a current direct ramp.

        Given a target value and a time in seconds, changes the current
        direct set-point linearly following a ramp. This function is
        blocked until target reached.

        Args:
            target_value : target value of the ramp.
            time_s : duration of the ramp, in seconds.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            init_value : initial value of the ramp. ``0`` by default.
            interval : time interval between register writes, in seconds.
                ``None`` by default, no interval.

        Raises:
            TypeError: If target_value or time_s is not a float.

        """
        for value in self.ramp_generator(init_value, target_value, time_s, interval):
            self.set_current_direct(value, servo=servo, axis=axis)

    def voltage_quadrature_ramp(
        self,
        target_value: float,
        time_s: float,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        init_value: float = 0,
        interval: Optional[float] = None,
    ) -> None:
        """Generate a voltage quadrature ramp.

        Given a target value and a time in seconds, changes the voltage
        quadrature set-point linearly following a ramp. This function is
        blocked until target reached.

        Args:
            target_value : target value of the ramp.
            time_s : duration of the ramp, in seconds.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            init_value : initial value of the ramp. ``0`` by default.
            interval : time interval between register writes, in seconds.
                ``None`` by default, no interval.

        Raises:
            TypeError: If target_value or time_s is not a float.

        """
        for value in self.ramp_generator(init_value, target_value, time_s, interval):
            self.set_voltage_quadrature(value, servo=servo, axis=axis)

    def voltage_direct_ramp(
        self,
        target_value: float,
        time_s: float,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        init_value: float = 0,
        interval: Optional[float] = None,
    ) -> None:
        """Generate a voltage direct ramp.

        Given a target value and a time in seconds, changes the voltage
        direct set-point linearly following a ramp. This function is
        blocked until target reached.

        Args:
            target_value : target value of the ramp.
            time_s : duration of the ramp, in seconds.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            init_value : initial value of the ramp. ``0`` by default.
            interval : time interval between register writes, in seconds.
                ``None`` by default, no interval.

        Raises:
            TypeError: If target_value or time_s is not a float.

        """
        for value in self.ramp_generator(init_value, target_value, time_s, interval):
            self.set_voltage_direct(value, servo=servo, axis=axis)

    @staticmethod
    def ramp_generator(
        init_v: float, final_v: float, total_t: float, interval: Optional[float] = None
    ) -> Generator[float, None, None]:
        """Generate a ramp.

        Args:
            init_v: Initial value.
            final_v: Final value.
            total_t: Total time.
            interval: Time between each sample.

        Returns:
            The ramp generator object.

        """
        slope = (final_v - init_v) / total_t
        init_time = time.time()
        yield init_v
        current_time = time.time()
        while current_time < init_time + total_t:
            yield slope * (current_time - init_time) + init_v
            if interval is not None:
                time.sleep(interval)
            current_time = time.time()
        yield final_v

    def get_actual_position(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:
        """Returns actual position register.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            int: actual position value

        Raises:
            TypeError: If some read value has a wrong type.

        """
        actual_position = self.mc.communication.get_register(
            self.ACTUAL_POSITION_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(actual_position, int):
            raise TypeError("Actual position value has to be an integer")
        return actual_position

    def get_actual_velocity(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> float:
        """Returns actual velocity register.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Returns:
            int: actual velocity value

        Raises:
            TypeError: If some read value has a wrong type.

        """
        actual_velocity = self.mc.communication.get_register(
            self.ACTUAL_VELOCITY_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(actual_velocity, float):
            raise TypeError("Actual velocity value has to be an integer")
        return actual_velocity

    def get_actual_current_direct(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> float:
        """Returns actual direct current register.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            axis: servo axis. ``1`` by default.

        Returns:
            float: actual direct current value

        Raises:
            TypeError: If some read value has a wrong type.

        """
        actual_current_direct = self.mc.communication.get_register(
            self.ACTUAL_DIRECT_CURRENT_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(actual_current_direct, float):
            raise TypeError("Actual current direct value has to be a float")
        return actual_current_direct

    def get_actual_current_quadrature(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> float:
        """Returns actual quadrature current register.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            float: actual quadrature current value

        Raises:
            TypeError: If some read value has a wrong type.

        """
        actual_current_quadrature = self.mc.communication.get_register(
            self.ACTUAL_QUADRATURE_CURRENT_REGISTER, servo=servo, axis=axis
        )
        if not isinstance(actual_current_quadrature, float):
            raise TypeError("Actual current quadrature value has to be a float")
        return actual_current_quadrature

    def wait_for_position(
        self,
        position: int,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        error: int = 20,
        timeout: Optional[float] = None,
        interval: Optional[float] = None,
    ) -> None:
        """Wait until actual position is equal to a target position, with an error.

        Args:
            position : target position, in counts.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            error : allowed error between actual position and target
                position, in counts.
            timeout : how many seconds to wait for the servo to reach the
                target position, if ``None`` it will wait forever .
                ``None`` by default.
            interval : interval of time between actual position reads,
                in seconds. ``None`` by default.

        Raises:
            IMTimeoutError: If the target position is not reached in time.

        """
        target_reached = False
        init_time = time.time()
        self.logger.debug(
            "Wait for position %s", position, axis=axis, drive=self.mc.servo_name(servo)
        )
        while not target_reached:
            if interval:
                time.sleep(interval)
            curr_position = self.get_actual_position(servo=servo, axis=axis)
            target_reached = abs(position - curr_position) < abs(error)
            if timeout and (init_time + timeout) < time.time():
                target_reached = True
                self.logger.warning(
                    "Timeout: position %s was not reached",
                    position,
                    axis=axis,
                    drive=self.mc.servo_name(servo),
                )
                raise IMTimeoutError("Position was not reached in time")

    def wait_for_velocity(
        self,
        velocity: float,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        error: float = 0.1,
        timeout: Optional[float] = None,
        interval: Optional[float] = None,
    ) -> None:
        """Wait until actual velocity is equal to a target velocity, with an error.

        Args:
            velocity : target velocity, in rev/s.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            error : allowed error between actual velocity and target
                velocity, in rev/s.
            timeout : how many seconds to wait for the servo to reach the
                target velocity, if ``None`` it will wait forever.
                ``None`` by default.
            interval : interval of time between actual velocity reads,
                in seconds. ``None`` by default.

        Raises:
            IMTimeoutError: If the target velocity is not reached in time.

        """
        target_reached = False
        init_time = time.time()
        self.logger.debug(
            "Wait for velocity %s", velocity, axis=axis, drive=self.mc.servo_name(servo)
        )
        while not target_reached:
            if interval:
                time.sleep(interval)
            curr_velocity = self.get_actual_velocity(servo=servo, axis=axis)
            target_reached = abs(velocity - curr_velocity) < abs(error)
            if timeout and (init_time + timeout) < time.time():
                target_reached = True
                self.logger.warning(
                    "Timeout: velocity %s was not reached",
                    velocity,
                    axis=axis,
                    drive=self.mc.servo_name(servo),
                )
                raise IMTimeoutError("Velocity was not reached in time")

    def set_internal_generator_configuration(
        self, op_mode: OperationMode, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set internal generator configuration.

        .. note::
            This functions affects the following drive registers: **motor pair poles**,
            **operation mode**, **phasing mode** and **commutation feedback**.
            This is an advanced-user oriented method, you could lose your drive
            configuration, use it at your own risk.

        Args:
            op_mode : select Current or Voltage operation mode
             for internal generator configuration.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            ValueError: If operation mode is not set to Current or Voltage.

        """
        if op_mode not in [OperationMode.CURRENT, OperationMode.VOLTAGE]:
            raise ValueError("Operation mode must be Current or Voltage")
        self.set_operation_mode(op_mode, servo=servo, axis=axis)
        self.mc.configuration.set_motor_pair_poles(1, servo=servo, axis=axis)
        self.mc.configuration.set_phasing_mode(PhasingMode.NO_PHASING, servo=servo, axis=axis)
        if op_mode == OperationMode.CURRENT:
            self.set_current_quadrature(0, servo=servo, axis=axis)
            self.set_current_direct(0, servo=servo, axis=axis)
        elif op_mode == OperationMode.VOLTAGE:
            self.set_voltage_quadrature(0, servo=servo, axis=axis)
            self.set_voltage_direct(0, servo=servo, axis=axis)
        self.mc.configuration.set_commutation_feedback(SensorType.INTGEN, servo=servo, axis=axis)

    def internal_generator_saw_tooth_move(
        self,
        direction: int,
        cycles: int,
        frequency: float,
        gain: float = 1.0,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Move motor in internal generator configuration with generator mode saw tooth.

        Args:
            direction : ``1`` for positive direction and
             ``-1`` for negative direction.
            cycles : movement cycles.
            frequency : cycles for second.
            gain: positive generator gain.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If direction, cycles or frequency is not of the correct type.
            ValueError: If gain is not positive.

        """
        if gain < 0:
            raise ValueError("Gain should be positive")
        self.mc.configuration.set_generator_mode(GeneratorMode.SAW_TOOTH, servo=servo, axis=axis)
        self.mc.communication.set_register(
            self.GENERATOR_FREQUENCY_REGISTER, frequency, servo=servo, axis=axis
        )
        if direction > 0:
            self.mc.communication.set_register(
                self.GENERATOR_GAIN_REGISTER, gain, servo=servo, axis=axis
            )
            self.mc.communication.set_register(
                self.GENERATOR_OFFSET_REGISTER, 0, servo=servo, axis=axis
            )
        else:
            self.mc.communication.set_register(
                self.GENERATOR_GAIN_REGISTER, -gain, servo=servo, axis=axis
            )
            self.mc.communication.set_register(
                self.GENERATOR_OFFSET_REGISTER, gain, servo=servo, axis=axis
            )

        self.mc.communication.set_register(
            self.GENERATOR_CYCLE_NUMBER_REGISTER, cycles, servo=servo, axis=axis
        )
        self.mc.communication.set_register(self.GENERATOR_REARM_REGISTER, 1, servo=servo, axis=axis)

    def internal_generator_constant_move(
        self, offset: int, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Move motor in internal generator configuration with generator mode constant.

        Args:
            offset : internal generator offset.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.

        Raises:
            TypeError: If offset is not an int.

        """
        self.mc.configuration.set_generator_mode(GeneratorMode.CONSTANT, servo=servo, axis=axis)
        self.mc.communication.set_register(self.GENERATOR_GAIN_REGISTER, 0, servo=servo, axis=axis)
        self.mc.communication.set_register(
            self.GENERATOR_OFFSET_REGISTER, offset, servo=servo, axis=axis
        )

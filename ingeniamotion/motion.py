import time
import ingenialogger
from ingenialink.exceptions import ILError

from .metaclass import MCMetaClass, DEFAULT_AXIS, DEFAULT_SERVO
from ingeniamotion.enums import OperationMode, SensorType,\
    PhasingMode, GeneratorMode


class Motion(metaclass=MCMetaClass):
    """Motion.
    """

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
    GENERATOR_FREQUENCY_REGISTER = "FBK_GEN_FREQ"
    GENERATOR_GAIN_REGISTER = "FBK_GEN_GAIN"
    GENERATOR_OFFSET_REGISTER = "FBK_GEN_OFFSET"
    GENERATOR_CYCLE_NUMBER_REGISTER = "FBK_GEN_CYCLES"
    GENERATOR_REARM_REGISTER = "FBK_GEN_REARM"

    STATUS_WORD_TARGET_REACHED_BIT = 0x800
    CONTROL_WORD_TARGET_LATCH_BIT = 0x200

    def __init__(self, motion_controller):
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def target_latch(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Active target latch.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        control_word = self.mc.communication.get_register(self.CONTROL_WORD_REGISTER,
                                                          servo=servo, axis=axis)
        new_control_word = control_word & (~self.CONTROL_WORD_TARGET_LATCH_BIT)
        self.mc.communication.set_register(self.CONTROL_WORD_REGISTER, new_control_word,
                                           servo=servo, axis=axis)
        new_control_word = control_word | self.CONTROL_WORD_TARGET_LATCH_BIT
        self.mc.communication.set_register(self.CONTROL_WORD_REGISTER, new_control_word,
                                           servo=servo, axis=axis)

    def set_operation_mode(self, operation_mode, servo=DEFAULT_SERVO,
                           axis=DEFAULT_AXIS):
        """
        Set operation mode to a target servo and axis.

        Args:
            operation_mode (OperationMode): operation mode, any of
                :class:`OperationMode`.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(self.OPERATION_MODE_REGISTER, operation_mode,
                                           servo=servo, axis=axis)
        try:
            self.logger.debug("Operation mode set to %s",
                              OperationMode(operation_mode).name,
                              axis=axis, drive=self.mc.servo_name(servo))
        except ValueError:
            self.logger.debug("Operation mode set to %s", operation_mode, axis=axis,
                              drive=self.mc.servo_name(servo))

    def get_operation_mode(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Return current operation mode.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            OperationMode: Return current operation mode.
        """
        operation_mode = self.mc.communication.get_register(
            self.OPERATION_MODE_DISPLAY_REGISTER,
            servo=servo, axis=axis
        )
        try:
            return OperationMode(operation_mode)
        except ValueError:
            return operation_mode

    def motor_enable(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Enable motor.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        drive = self.mc.servos[servo]
        try:
            drive.enable(subnode=axis)
        except ILError as e:
            error_code = self.mc.errors.get_last_buffer_error(servo=servo, axis=axis)
            error_id, _, _, error_msg = self.mc.errors.get_error_data(
                error_code, servo=servo)
            exception_type = type(e)
            raise exception_type("An error occurred enabling motor. Reason: {}"
                                 .format(error_msg))

    def motor_disable(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Disable motor.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        if self.mc.configuration.is_motor_enabled(servo=servo, axis=axis):
            drive = self.mc.servos[servo]
            drive.disable(subnode=axis)

    def move_to_position(self, position, servo=DEFAULT_SERVO,
                         axis=DEFAULT_AXIS, target_latch=True,
                         blocking=False):
        """
        Set position set point to a target servo and axis, in counts.


        Args:
            position (int): target position, in counts.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            target_latch (bool): if ``True`` does target latch at the end.
                ``True`` by default.
            blocking (bool): if ``True``, the function is blocked until the
                target position is reached. ``False`` by default.
        """
        self.mc.communication.set_register(self.POSITION_SET_POINT_REGISTER,
                                           position, servo=servo, axis=axis)
        if target_latch:
            self.target_latch(servo, axis)
            if blocking:
                self.wait_for_position(position, servo, axis)

    def set_velocity(self, velocity, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                     target_latch=True, blocking=False):
        """
        Set velocity set point to a target servo and axis, in rev/s.

        Args:
            velocity (float): target velocity, in rev/s.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            target_latch (bool): if ``True`` does target latch at the end.
                ``True`` by default.
            blocking (bool): if ``True``, the function is blocked until the
                target position is reached. ``False`` by default.
        """
        self.mc.communication.set_register(self.VELOCITY_SET_POINT_REGISTER,
                                           velocity, servo=servo, axis=axis)
        if target_latch:
            self.target_latch(servo, axis)
            if blocking:
                self.wait_for_velocity(velocity, servo, axis)

    def set_current_quadrature(self, current, servo=DEFAULT_SERVO,
                               axis=DEFAULT_AXIS):
        """
        Set quadrature current set point to a target servo and axis, in A.

        Args:
            current (float): target quadrature current, in A.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(
            self.CURRENT_QUADRATURE_SET_POINT_REGISTER,
            current, servo=servo, axis=axis
        )

    def set_current_direct(self, current, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Set direct current set point to a target servo and axis, in A.

        Args:
            current (float): target direct current, in A.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(self.CURRENT_DIRECT_SET_POINT_REGISTER,
                                           current, servo=servo, axis=axis)

    def set_voltage_quadrature(self, voltage, servo=DEFAULT_SERVO,
                               axis=DEFAULT_AXIS):
        """
        Set quadrature voltage set point to a target servo and axis, in V.

        Args:
            voltage (float): target quadrature voltage, in V.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(self.VOLTAGE_QUADRATURE_SET_POINT_REGISTER,
                                           voltage, servo=servo, axis=axis)

    def set_voltage_direct(self, voltage, servo=DEFAULT_SERVO,
                           axis=DEFAULT_AXIS):
        """
        Set direct voltage set point to a target servo and axis, in V.

        Args:
            voltage (float): target direct voltage, in V.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(self.VOLTAGE_DIRECT_SET_POINT_REGISTER,
                                           voltage, servo=servo, axis=axis)

    def current_quadrature_ramp(self, target_value, time_s, servo=DEFAULT_SERVO,
                                axis=DEFAULT_AXIS, init_value=0, interval=None):
        """
        Given a target value and a time in seconds, changes the current
        quadrature set-point linearly following a ramp. This function is
        blocked until target reached.

        Args:
            target_value (float): target value of the ramp.
            time_s (float): duration of the ramp, in seconds.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            init_value (float): initial value of the ramp. ``0`` by default.
            interval (float): time interval between register writes, in seconds.
                ``None`` by default, no interval.
        """
        for value in self.ramp_generator(init_value, target_value, time_s, interval):
            self.set_current_quadrature(value, servo=servo, axis=axis)

    def current_direct_ramp(self, target_value, time_s, servo=DEFAULT_SERVO,
                            axis=DEFAULT_AXIS, init_value=0, interval=None):
        """
        Given a target value and a time in seconds, changes the current
        direct set-point linearly following a ramp. This function is
        blocked until target reached.

        Args:
            target_value (float): target value of the ramp.
            time_s (float): duration of the ramp, in seconds.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            init_value (float): initial value of the ramp. ``0`` by default.
            interval (float): time interval between register writes, in seconds.
                ``None`` by default, no interval.
        """
        for value in self.ramp_generator(init_value, target_value, time_s, interval):
            self.set_current_direct(value, servo=servo, axis=axis)

    def voltage_quadrature_ramp(self, target_value, time_s, servo=DEFAULT_SERVO,
                                axis=DEFAULT_AXIS, init_value=0, interval=None):
        """
        Given a target value and a time in seconds, changes the voltage
        quadrature set-point linearly following a ramp. This function is
        blocked until target reached.

        Args:
            target_value (float): target value of the ramp.
            time_s (float): duration of the ramp, in seconds.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            init_value (float): initial value of the ramp. ``0`` by default.
            interval (float): time interval between register writes, in seconds.
                ``None`` by default, no interval.
        """
        for value in self.ramp_generator(init_value, target_value, time_s, interval):
            self.set_voltage_quadrature(value, servo=servo, axis=axis)

    def voltage_direct_ramp(self, target_value, time_s, servo=DEFAULT_SERVO,
                            axis=DEFAULT_AXIS, init_value=0, interval=None):
        """
        Given a target value and a time in seconds, changes the voltage
        direct set-point linearly following a ramp. This function is
        blocked until target reached.

        Args:
            target_value (float): target value of the ramp.
            time_s (float): duration of the ramp, in seconds.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            init_value (float): initial value of the ramp. ``0`` by default.
            interval (float): time interval between register writes, in seconds.
                ``None`` by default, no interval.
        """
        for value in self.ramp_generator(init_value, target_value, time_s, interval):
            self.set_voltage_direct(value, servo=servo, axis=axis)

    @staticmethod
    def ramp_generator(init_v, final_v, total_t, interval=None):
        slope = (final_v-init_v) / total_t
        init_time = time.time()
        yield init_v
        current_time = time.time()
        while current_time < init_time+total_t:
            yield slope * (current_time-init_time) + init_v
            if interval is not None:
                time.sleep(interval)
            current_time = time.time()
        yield final_v

    def get_actual_position(self, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Returns actual position register.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.

        Returns:
            int: actual position value
        """
        return self.mc.communication.get_register(self.ACTUAL_POSITION_REGISTER,
                                                  servo=servo, axis=axis)

    def wait_for_position(self, position, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                          error=20, timeout=None, interval=None):
        """
        Wait until actual position is equal to a target position, with an error.

        Args:
            position (int): target position, in counts.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            error (int): allowed error between actual position and target
                position, in counts.
            timeout (int): how many seconds to wait for the servo to reach the
                target position, if ``None`` it will wait forever .
                ``None`` by default.
            interval (float): interval of time between actual position reads,
                in seconds. ``None`` by default.
        """
        target_reached = False
        init_time = time.time()
        self.logger.debug("Wait for position %s", position, axis=axis,
                          drive=self.mc.servo_name(servo))
        while not target_reached:
            if interval:
                time.sleep(interval)
            curr_position = self.get_actual_position(servo=servo, axis=axis)
            target_reached = abs(position - curr_position) < abs(error)
            if timeout and (init_time + timeout) < time.time():
                target_reached = True
                self.logger.warning("Timeout: position %s was not reached", position,
                                    axis=axis, drive=self.mc.servo_name(servo))

    def wait_for_velocity(self, velocity, servo=DEFAULT_SERVO, axis=DEFAULT_AXIS,
                          error=0.1, timeout=None, interval=None):
        """
        Wait until actual velocity is equal to a target velocity, with an error.

        Args:
            velocity (float): target velocity, in rev/s.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            error (int): allowed error between actual velocity and target
                velocity, in counts.
            timeout (int): how many seconds to wait for the servo to reach the
                target velocity, if ``None`` it will wait forever.
                ``None`` by default.
            interval (float): interval of time between actual velocity reads,
                in seconds. ``None`` by default.
        """
        target_reached = False
        init_time = time.time()
        self.logger.debug("Wait for velocity %s", velocity, axis=axis,
                          drive=self.mc.servo_name(servo))
        while not target_reached:
            if interval:
                time.sleep(interval)
            curr_velocity = self.mc.communication.get_register(
                self.ACTUAL_VELOCITY_REGISTER,
                servo=servo, axis=axis
            )
            target_reached = abs(velocity - curr_velocity) < abs(error)
            if timeout and (init_time + timeout) < time.time():
                target_reached = True
                self.logger.warning("Timeout: velocity %s was not reached",
                                    velocity, axis=axis,
                                    drive=self.mc.servo_name(servo))

    def set_internal_generator_configuration(self, op_mode, servo=DEFAULT_SERVO,
                                             axis=DEFAULT_AXIS):
        """
        Set internal generator configuration.

        .. note::
            This functions affects the following drive registers: **motor pair poles**,
            **operation mode**, **phasing mode** and **commutation feedback**.
            This is an advanced-user oriented method, you could lose your drive
            configuration, use it at your own risk.

        Args:
            op_mode (OperationMode): select Current or Voltage operation mode
             for internal generator configuration.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        if op_mode not in [OperationMode.CURRENT, OperationMode.VOLTAGE]:
            raise ValueError("Operation mode must be Current or Voltage")
        self.set_operation_mode(op_mode, servo=servo, axis=axis)
        self.mc.configuration.set_motor_pair_poles(1, servo=servo, axis=axis)
        self.mc.configuration.set_phasing_mode(PhasingMode.NO_PHASING,
                                               servo=servo, axis=axis)
        if op_mode == OperationMode.CURRENT:
            self.set_current_quadrature(0, servo=servo, axis=axis)
            self.set_current_direct(0, servo=servo, axis=axis)
        elif op_mode == OperationMode.VOLTAGE:
            self.set_voltage_quadrature(0, servo=servo, axis=axis)
            self.set_voltage_direct(0, servo=servo, axis=axis)
        self.mc.configuration.set_commutation_feedback(SensorType.INTGEN,
                                                       servo=servo, axis=axis)

    def internal_generator_saw_tooth_move(self, direction, cycles, frequency,
                                          servo=DEFAULT_SERVO, axis=DEFAULT_AXIS):
        """
        Move motor in internal generator configuration with generator mode saw tooth.

        Args:
            direction (int): ``1`` for positive direction and
             ``-1`` for negative direction.
            cycles (int): movement cycles.
            frequency (int): cycles for second.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.configuration.set_generator_mode(GeneratorMode.SAW_TOOTH,
                                                 servo=servo, axis=axis)
        self.mc.communication.set_register(self.GENERATOR_FREQUENCY_REGISTER, frequency,
                                           servo=servo, axis=axis)
        if direction > 0:
            self.mc.communication.set_register(self.GENERATOR_GAIN_REGISTER, 1,
                                               servo=servo, axis=axis)
            self.mc.communication.set_register(self.GENERATOR_OFFSET_REGISTER, 0,
                                               servo=servo, axis=axis)
        else:
            self.mc.communication.set_register(self.GENERATOR_GAIN_REGISTER, -1,
                                               servo=servo, axis=axis)
            self.mc.communication.set_register(self.GENERATOR_OFFSET_REGISTER, 1,
                                               servo=servo, axis=axis)

        self.mc.communication.set_register(self.GENERATOR_CYCLE_NUMBER_REGISTER, cycles,
                                           servo=servo, axis=axis)
        self.mc.communication.set_register(self.GENERATOR_REARM_REGISTER, 1,
                                           servo=servo, axis=axis)

    def internal_generator_constant_move(self, offset, servo=DEFAULT_SERVO,
                                         axis=DEFAULT_AXIS):
        """
        Move motor in internal generator configuration with generator mode constant.

        Args:
            offset (int): internal generator offset.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.configuration.set_generator_mode(GeneratorMode.CONSTANT,
                                                 servo=servo, axis=axis)
        self.mc.communication.set_register(self.GENERATOR_GAIN_REGISTER, 0,
                                           servo=servo, axis=axis)
        self.mc.communication.set_register(self.GENERATOR_OFFSET_REGISTER, offset,
                                           servo=servo, axis=axis)

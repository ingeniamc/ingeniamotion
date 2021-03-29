import time

from enum import IntEnum


class Motion:
    """Motion.
    """

    class OperationMode(IntEnum):
        """
        Operation Mode Enum
        """
        VOLTAGE = 0x00
        CURRENT_AMPLIFIER = 0x01
        CURRENT = 0x02
        CYCLIC_CURRENT = 0x22
        VELOCITY = 0x03
        PROFILE_VELOCITY = 0x13
        CYCLIC_VELOCITY = 0x23
        POSITION = 0x04
        PROFILE_POSITION = 0x14
        CYCLIC_POSITION = 0x24
        CYCLIC_POSITION_S_CURVE = 0x44
        PVT = 0xB4
        HOMING = 0x113

    CONTROL_WORD_REGISTER = 'DRV_STATE_CONTROL'
    OPERATION_MODE_REGISTER = "DRV_OP_CMD"
    POSITION_SET_POINT_REGISTER = "CL_POS_SET_POINT_VALUE"
    VELOCITY_SET_POINT_REGISTER = "CL_VEL_SET_POINT_VALUE"
    CURRENT_QUADRATURE_SET_POINT_REGISTER = "CL_CUR_Q_SET_POINT"
    ACTUAL_POSITION_REGISTER = "CL_POS_FBK_VALUE"
    ACTUAL_VELOCITY_REGISTER = "CL_VEL_FBK_VALUE"

    def __init__(self, motion_controller):
        self.mc = motion_controller

    def target_latch(self, servo="default", axis=1):
        """
        Active target latch.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        control_word = self.mc.communication.get_register(self.CONTROL_WORD_REGISTER, servo=servo, axis=axis)
        new_control_word = control_word & (~0x200)
        self.mc.communication.set_register(self.CONTROL_WORD_REGISTER, new_control_word, servo=servo, axis=axis)
        new_control_word = control_word | 0x200
        self.mc.communication.set_register(self.CONTROL_WORD_REGISTER, new_control_word, servo=servo, axis=axis)

    def set_operation_mode(self, operation_mode, servo="default", axis=1):
        """
        Set operation mode to a target servo and axis.

        Args:
            operation_mode (int): operation mode, any of :class:`OperationMode`.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(self.OPERATION_MODE_REGISTER, operation_mode, servo=servo, axis=axis)

    def motor_enable(self, servo="default", axis=1):
        """
        Enable motor.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        drive = self.mc.servos[servo]
        drive.enable(subnode=axis)

    def motor_disable(self, servo="default", axis=1):
        """
        Disable motor.

        Args:
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        drive = self.mc.servos[servo]
        drive.disable(subnode=axis)

    def move_to_position(self, position, servo="default", axis=1, target_latch=True, blocking=False):
        """
        Set position set point to a target servo and axis, in counts.


        Args:
            position (int): target position, in counts.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            target_latch (bool): if ``True`` does target latch at the end. ``True`` by default.
            blocking (bool): if ```True``, the function is blocked until the target position is reached.
             ``False`` by default.
        """
        self.mc.communication.set_register(self.POSITION_SET_POINT_REGISTER, position, servo=servo, axis=axis)
        if target_latch:
            self.target_latch(servo, axis)
            if blocking:
                self.wait_for_position(position, servo, axis)

    def set_velocity(self, velocity, servo="default", axis=1, target_latch=True, blocking=False):
        """
        Set velocity set point to a target servo and axis, in rev/s.

        Args:
            velocity (float): target velocity, in rev/s.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            target_latch (bool): if ``True`` does target latch at the end. ``True`` by default.
            blocking (bool): if ```True``, the function is blocked until the target position is reached.
             ``False`` by default.
        """
        self.mc.communication.set_register(self.VELOCITY_SET_POINT_REGISTER, velocity, servo=servo, axis=axis)
        if target_latch:
            self.target_latch(servo, axis)
            if blocking:
                self.wait_for_velocity(velocity, servo, axis)

    def set_current_quadrature(self, current, servo="default", axis=1):
        """
        Set quadrature current set point to a target servo and axis, in A.

        Args:
            current (float): target quadrature current, in A.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(self.CURRENT_QUADRATURE_SET_POINT_REGISTER,
                                           current, servo=servo, axis=axis)

    def wait_for_position(self, position, servo="default", axis=1, error=20, timeout=None, interval=None):
        """
        Wait until actual position is equal to a target position, with an error.

        Args:
            position (int): target position, in counts.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            error (int): allowed error between actual position and target position, in counts.
            timeout (int): how many seconds to wait for the servo to reach the target position,
             if ``None`` it will wait forever . ``None`` by default.
            interval (float): interval of time between actual position reads, in seconds.
             ``None`` by default.
        """
        target_reached = False
        init_time = time.time()
        while not target_reached:
            if interval:
                time.sleep(interval)
            curr_position = self.mc.communication.get_register(self.ACTUAL_POSITION_REGISTER,
                                                               servo=servo, axis=axis)
            target_reached = abs(position - curr_position) < error
            if timeout and (init_time + timeout) < time.time():
                target_reached = True

    def wait_for_velocity(self, velocity, servo="default", axis=1, error=0.1, timeout=None, interval=None):
        """
        Wait until actual position is equal to a target position, with an error.

        Args:
            velocity (float): target velocity, in rev/s.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            error (int): allowed error between actual position and target position, in counts.
            timeout (int): how many seconds to wait for the servo to reach the target position,
             if ``None`` it will wait forever . ``None`` by default.
            interval (float): interval of time between actual position reads, in seconds.
             ``None`` by default.
        """
        target_reached = False
        init_time = time.time()
        while not target_reached:
            if interval:
                time.sleep(interval)
            curr_velocity = self.mc.communication.get_register(self.ACTUAL_VELOCITY_REGISTER,
                                                               servo=servo, axis=axis)
            target_reached = abs(velocity - curr_velocity) < error
            if timeout and (init_time + timeout) < time.time():
                target_reached = True

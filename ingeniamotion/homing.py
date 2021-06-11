import ingenialogger

from enum import IntEnum
from ingeniamotion.enums import OperationMode


class HomingMode(IntEnum):
    HOM_CURRENT_POS = 0
    HOM_POS_LIM_SWITCH = 1
    HOM_NEG_LIM_SWITCH = 2
    HOM_POS_IDX_PULSE = 3
    HOM_NEG_IDX_PULSE = 4
    HOM_POS_LIM_AND_IDX = 5
    HOM_NEG_LIM_AND_IDX = 6


class Homing:

    HOMING_MODE_REGISTER = "HOM_MODE"
    HOMING_OFFSET_REGISTER = "HOM_OFFSET"
    HOMING_TIMEOUT_REGISTER = "HOM_SEQ_TIMEOUT"
    POSITIVE_HOMING_SWITCH_REGISTER = "IO_IN_POS_HOM_SWITCH"
    NEGATIVE_HOMING_SWITCH_REGISTER = "IO_IN_NEG_HOM_SWITCH"
    HOMING_SEARCH_VELOCITY_REGISTER = "HOM_SPEED_SEARCH"
    HOMING_ZERO_VELOCITY_REGISTER = "HOM_SPEED_ZERO"
    HOMING_INDEX_PULSE_SOURCE_REGISTER = "HOM_IDX_PULSE_SRC"

    def __init__(self, motion_controller):
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def set_homing_mode(self, homing_mode, servo="default", axis=1):
        """
        Set homing mode.

        Args:
            homing_mode (HomingMode): homing mode.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(self.HOMING_MODE_REGISTER,
                                           homing_mode, servo, axis)

    def set_homing_offset(self, homing_offset, servo="default", axis=1):
        """
        Set homing offset configuration.

        Args:
            homing_offset (int): homing offset.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(self.HOMING_OFFSET_REGISTER,
                                           homing_offset, servo, axis)

    def set_homing_timeout(self, timeout_ms, servo="default", axis=1):
        """
        Set homing timeout configuration.

        Args:
            timeout_ms (int): homing timeout in milliseconds.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        self.mc.communication.set_register(self.HOMING_TIMEOUT_REGISTER,
                                           timeout_ms, servo, axis)

    def homing_on_current_position(self, hom_offset, servo="default", axis=1):
        """
        Do current position homing.

        Args:
            hom_offset (int): homing offset.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
        """
        # Save previous mode
        prev_op_mode = self.mc.motion.get_operation_mode(servo, axis)

        self.mc.communication.set_register(self.HOMING_MODE_REGISTER,
                                           HomingMode.HOM_CURRENT_POS,
                                           servo, axis)
        self.mc.communication.set_register(self.HOMING_OFFSET_REGISTER,
                                           hom_offset,
                                           servo, axis)
        self.mc.motion.set_operation_mode(OperationMode.HOMING, servo, axis)

        # Perform the homing
        self.mc.motion.target_latch(servo, axis)
        # Restore op mode
        self.mc.motion.set_operation_mode(prev_op_mode, servo, axis)

    def homing_on_switch_limit(self, hom_offset, direction, switch, timeout_ms, lim_vel, zero_vel,
                               servo="default", axis=1, motor_enable=True):
        """
        Do homing on switch limit.

        Args:
            hom_offset (int): homing offset.
            direction (int): direction. ``1`` is positive, ``0`` is negative.
            switch (int): switch index.
            timeout_ms (int): homing timeout in milliseconds.
            lim_vel (int): speed to search for the switch, in mrev/s.
            zero_vel (int): speed to search for the actual homing point, in mrev/s.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            motor_enable (bool): if ``True`` do motor enable. ``True`` by default.
        """
        self.mc.motion.set_operation_mode(OperationMode.HOMING, servo, axis)
        if direction > 0:
            # Positive direction
            self.set_homing_mode(HomingMode.HOM_POS_LIM_SWITCH, servo, axis)
            self.mc.communication.set_register(self.POSITIVE_HOMING_SWITCH_REGISTER,
                                               switch, servo, axis)
        else:
            # Negative direction
            self.set_homing_mode(HomingMode.HOM_NEG_LIM_SWITCH, servo, axis)
            self.mc.communication.set_register(self.NEGATIVE_HOMING_SWITCH_REGISTER,
                                               switch, servo, axis)
        self.set_homing_offset(hom_offset, servo, axis)
        self.set_homing_timeout(timeout_ms, servo, axis)
        self.mc.communication.set_register(self.HOMING_SEARCH_VELOCITY_REGISTER,
                                           lim_vel, servo, axis)
        self.mc.communication.set_register(self.HOMING_ZERO_VELOCITY_REGISTER,
                                           zero_vel, servo, axis)
        # Perform the homing
        if motor_enable:
            self.mc.motion.motor_enable(servo, axis)
        self.mc.motion.target_latch(servo, axis)

    def homing_on_index_pulse(self, hom_offset, direction, index, timeout_ms, zero_vel,
                              servo="default", axis=1, motor_enable=True):
        """
        Do homing on index pulse.

        Args:
            hom_offset (int): homing offset.
            direction (int): direction. ``1`` is positive, ``0`` is negative.
            index (int): select incremental encoder, ``0`` for incremental encoder 1,
             ``1`` for incremental encoder 2.
            timeout_ms (int): homing timeout in milliseconds.
            zero_vel (int): speed to search for the actual homing point, in mrev/s.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            motor_enable (bool): if ``True`` do motor enable. ``True`` by default.
        """
        self.mc.motion.set_operation_mode(OperationMode.HOMING, servo, axis)
        if direction > 0:
            # Positive direction
            self.set_homing_mode(HomingMode.HOM_POS_IDX_PULSE, servo, axis)
        else:
            # Negative direction
            self.set_homing_mode(HomingMode.HOM_NEG_IDX_PULSE, servo, axis)
        self.set_homing_offset(hom_offset, servo, axis)
        self.set_homing_timeout(timeout_ms, servo, axis)
        self.mc.communication.set_register(self.HOMING_INDEX_PULSE_SOURCE_REGISTER,
                                           index, servo, axis)
        self.mc.communication.set_register(self.HOMING_ZERO_VELOCITY_REGISTER,
                                           zero_vel, servo, axis)

        # Perform the homing
        if motor_enable:
            self.mc.motion.motor_enable(servo, axis)
        self.mc.motion.target_latch(servo, axis)

    def homing_on_switch_limit_and_index_pulse(self, hom_offset, direction, switch, index,
                                               timeout_ms, lim_vel, zero_vel, servo="default",
                                               axis=1, motor_enable=True):
        """
        Do homing on switch limit and index pulse.

        Args:
            hom_offset (int): homing offset.
            direction (int): direction. ``1`` is positive, ``0`` is negative.
            switch (int): switch index.
            index (int): select incremental encoder, ``0`` for incremental encoder 1,
             ``1`` for incremental encoder 2.
            timeout_ms (int): homing timeout in milliseconds.
            lim_vel (int): speed to search for the switch, in mrev/s.
            zero_vel (int): speed to search for the actual homing point, in mrev/s.
            servo (str): servo alias to reference it. ``default`` by default.
            axis (int): servo axis. ``1`` by default.
            motor_enable (bool): if ``True`` do motor enable. ``True`` by default.
        """
        self.mc.motion.set_operation_mode(OperationMode.HOMING, servo, axis)
        if direction > 0:
            # Positive direction
            self.set_homing_mode(HomingMode.HOM_POS_LIM_AND_IDX, servo, axis)
            self.mc.communication.set_register(self.POSITIVE_HOMING_SWITCH_REGISTER,
                                               switch, servo, axis)
        else:
            # Negative direction
            self.set_homing_mode(HomingMode.HOM_NEG_LIM_AND_IDX, servo, axis)
            self.mc.communication.set_register(self.NEGATIVE_HOMING_SWITCH_REGISTER,
                                               switch, servo, axis)
        self.set_homing_offset(hom_offset, servo, axis)
        self.set_homing_timeout(timeout_ms, servo, axis)
        self.mc.communication.set_register(self.HOMING_INDEX_PULSE_SOURCE_REGISTER,
                                           index, servo, axis)
        self.mc.communication.set_register(self.HOMING_SEARCH_VELOCITY_REGISTER,
                                           lim_vel, servo, axis)
        self.mc.communication.set_register(self.HOMING_ZERO_VELOCITY_REGISTER,
                                           zero_vel, servo, axis)

        # Perform the homing
        if motor_enable:
            self.mc.motion.motor_enable(servo, axis)
        self.mc.motion.target_latch(servo, axis)

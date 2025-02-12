from typing import TYPE_CHECKING

import ingenialogger

from ingeniamotion.enums import HomingMode, OperationMode

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO


class Homing:
    """Class that contains the homing functionalities."""

    HOMING_MODE_REGISTER = "HOM_MODE"
    HOMING_OFFSET_REGISTER = "HOM_OFFSET"
    HOMING_TIMEOUT_REGISTER = "HOM_SEQ_TIMEOUT"
    POSITIVE_HOMING_SWITCH_REGISTER = "IO_IN_POS_HOM_SWITCH"
    NEGATIVE_HOMING_SWITCH_REGISTER = "IO_IN_NEG_HOM_SWITCH"
    HOMING_SEARCH_VELOCITY_REGISTER = "HOM_SPEED_SEARCH"
    HOMING_ZERO_VELOCITY_REGISTER = "HOM_SPEED_ZERO"
    HOMING_INDEX_PULSE_SOURCE_REGISTER = "HOM_IDX_PULSE_SRC"

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def set_homing_mode(
        self, homing_mode: HomingMode, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set homing mode.

        Args:
            homing_mode : homing mode.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
        """
        self.__mc._get_drive(servo)
        self.mc.communication.set_register(self.HOMING_MODE_REGISTER, homing_mode, servo, axis)

    def set_homing_offset(
        self, homing_offset: int, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set homing offset configuration.

        Args:
            homing_offset : homing offset.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
        """
        self.__mc._get_drive(servo)
        self.mc.communication.set_register(self.HOMING_OFFSET_REGISTER, homing_offset, servo, axis)

    def set_homing_timeout(
        self, timeout_ms: int, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Set homing timeout configuration.

        Args:
            timeout_ms : homing timeout in milliseconds.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
        """
        self.__mc._get_drive(servo)
        self.mc.communication.set_register(self.HOMING_TIMEOUT_REGISTER, timeout_ms, servo, axis)

    def __check_motor_phasing(self, servo: str, axis: int) -> None:
        if not self.mc.configuration.is_commutation_feedback_aligned(servo=servo, axis=axis):
            self.logger.warning(
                "Motor must be well phased before run any homing.",
                axis=axis,
                drive=self.mc.servo_name(servo),
            )

    def homing_on_current_position(
        self, hom_offset: int, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Do current position homing.

        Args:
            hom_offset : homing offset.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
        """
        self.__mc._get_drive(servo)
        # Save previous mode
        prev_op_mode = self.mc.motion.get_operation_mode(servo, axis)

        self.mc.communication.set_register(
            self.HOMING_MODE_REGISTER, HomingMode.CURRENT_POSITION, servo, axis
        )
        self.mc.communication.set_register(self.HOMING_OFFSET_REGISTER, hom_offset, servo, axis)
        self.mc.motion.set_operation_mode(OperationMode.HOMING, servo, axis)

        # Perform the homing
        self.mc.motion.target_latch(servo, axis)
        # Restore op mode
        self.mc.motion.set_operation_mode(prev_op_mode, servo, axis)

    def homing_on_switch_limit(
        self,
        hom_offset: int,
        direction: int,
        switch: int,
        timeout_ms: int,
        lim_vel: int,
        zero_vel: int,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        motor_enable: bool = True,
    ) -> None:
        """Do homing on switch limit.

        .. note::
            Motor must be well phased before run any homing.

        Args:
            hom_offset : homing offset.
            direction : direction. ``1`` is positive, ``0`` is negative.
            switch : switch index.
            timeout_ms : homing timeout in milliseconds.
            lim_vel : speed to search for the switch, in mrev/s.
            zero_vel : speed to search for the actual homing point, in mrev/s.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            motor_enable : if ``True`` do motor enable. ``True`` by default.

        """
        self.__mc._get_drive(servo)
        self.mc.motion.set_operation_mode(OperationMode.HOMING, servo, axis)
        if direction > 0:
            # Positive direction
            self.set_homing_mode(HomingMode.POSITIVE_LIMIT_SWITCH, servo, axis)
            self.mc.communication.set_register(
                self.POSITIVE_HOMING_SWITCH_REGISTER, switch, servo, axis
            )
        else:
            # Negative direction
            self.set_homing_mode(HomingMode.NEGATIVE_LIMIT_SWITCH, servo, axis)
            self.mc.communication.set_register(
                self.NEGATIVE_HOMING_SWITCH_REGISTER, switch, servo, axis
            )
        self.set_homing_offset(hom_offset, servo, axis)
        self.set_homing_timeout(timeout_ms, servo, axis)
        self.mc.communication.set_register(
            self.HOMING_SEARCH_VELOCITY_REGISTER, lim_vel, servo, axis
        )
        self.mc.communication.set_register(
            self.HOMING_ZERO_VELOCITY_REGISTER, zero_vel, servo, axis
        )
        self.__check_motor_phasing(servo, axis)
        # Perform the homing
        if motor_enable:
            self.mc.motion.motor_enable(servo, axis)
            self.mc.motion.target_latch(servo, axis)

    def homing_on_index_pulse(
        self,
        hom_offset: int,
        direction: int,
        index: int,
        timeout_ms: int,
        zero_vel: int,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        motor_enable: bool = True,
    ) -> None:
        """Do homing on index pulse.

        .. note::
            Motor must be well phased before run any homing.

        Args:
            hom_offset : homing offset.
            direction : direction. ``1`` is positive, ``0`` is negative.
            index : select incremental encoder, ``0`` for incremental encoder 1,
             ``1`` for incremental encoder 2.
            timeout_ms : homing timeout in milliseconds.
            zero_vel : speed to search for the actual homing point, in mrev/s.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            motor_enable : if ``True`` do motor enable. ``True`` by default.
        """
        self.__mc._get_drive(servo)
        self.mc.motion.set_operation_mode(OperationMode.HOMING, servo, axis)
        if direction > 0:
            # Positive direction
            self.set_homing_mode(HomingMode.POSITIVE_IDX_PULSE, servo, axis)
        else:
            # Negative direction
            self.set_homing_mode(HomingMode.NEGATIVE_IDX_PULSE, servo, axis)
        self.set_homing_offset(hom_offset, servo, axis)
        self.set_homing_timeout(timeout_ms, servo, axis)
        self.mc.communication.set_register(
            self.HOMING_INDEX_PULSE_SOURCE_REGISTER, index, servo, axis
        )
        self.mc.communication.set_register(
            self.HOMING_ZERO_VELOCITY_REGISTER, zero_vel, servo, axis
        )
        self.__check_motor_phasing(servo, axis)
        # Perform the homing
        if motor_enable:
            self.mc.motion.motor_enable(servo, axis)
        self.mc.motion.target_latch(servo, axis)

    def homing_on_switch_limit_and_index_pulse(
        self,
        hom_offset: int,
        direction: int,
        switch: int,
        index: int,
        timeout_ms: int,
        lim_vel: int,
        zero_vel: int,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
        motor_enable: bool = True,
    ) -> None:
        """Do homing on switch limit and index pulse.

        .. note::
            Motor must be well phased before run any homing.

        Args:
            hom_offset : homing offset.
            direction : direction. ``1`` is positive, ``0`` is negative.
            switch : switch index.
            index : select incremental encoder, ``0`` for incremental encoder 1,
             ``1`` for incremental encoder 2.
            timeout_ms : homing timeout in milliseconds.
            lim_vel : speed to search for the switch, in mrev/s.
            zero_vel : speed to search for the actual homing point, in mrev/s.
            servo : servo alias to reference it. ``default`` by default.
            axis : servo axis. ``1`` by default.
            motor_enable : if ``True`` do motor enable. ``True`` by default.
        """
        self.__mc._get_drive(servo)
        self.mc.motion.set_operation_mode(OperationMode.HOMING, servo, axis)
        if direction > 0:
            # Positive direction
            self.set_homing_mode(HomingMode.POSITIVE_LIMIT_SWITCH_IDX_PULSE, servo, axis)
            self.mc.communication.set_register(
                self.POSITIVE_HOMING_SWITCH_REGISTER, switch, servo, axis
            )
        else:
            # Negative direction
            self.set_homing_mode(HomingMode.NEGATIVE_LIMIT_SWITCH_IDX_PULSE, servo, axis)
            self.mc.communication.set_register(
                self.NEGATIVE_HOMING_SWITCH_REGISTER, switch, servo, axis
            )
        self.set_homing_offset(hom_offset, servo, axis)
        self.set_homing_timeout(timeout_ms, servo, axis)
        self.mc.communication.set_register(
            self.HOMING_INDEX_PULSE_SOURCE_REGISTER, index, servo, axis
        )
        self.mc.communication.set_register(
            self.HOMING_SEARCH_VELOCITY_REGISTER, lim_vel, servo, axis
        )
        self.mc.communication.set_register(
            self.HOMING_ZERO_VELOCITY_REGISTER, zero_vel, servo, axis
        )
        self.__check_motor_phasing(servo, axis)
        # Perform the homing
        if motor_enable:
            self.mc.motion.motor_enable(servo, axis)
        self.mc.motion.target_latch(servo, axis)

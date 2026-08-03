import typing
from typing import TYPE_CHECKING, Final, Optional, Union

import ingenialogger

from ingeniamotion.enums import FeedbackPolarity, SensorCategory, SensorType

if TYPE_CHECKING:
    from ingeniamotion.axis import Axis
    from ingeniamotion.motion_controller import MotionController
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO, MCMetaClass

COMMUTATION_FEEDBACK_REGISTER = "COMMU_ANGLE_SENSOR"
REFERENCE_FEEDBACK_REGISTER = "COMMU_ANGLE_REF_SENSOR"
VELOCITY_FEEDBACK_REGISTER = "CL_VEL_FBK_SENSOR"
POSITION_FEEDBACK_REGISTER = "CL_POS_FBK_SENSOR"
AUXILIAR_FEEDBACK_REGISTER = "CL_AUX_FBK_SENSOR"

FEEDBACK_TYPE_DICT: Final[dict[SensorType, SensorCategory]] = {
    SensorType.ABS1: SensorCategory.ABSOLUTE,
    SensorType.QEI: SensorCategory.INCREMENTAL,
    SensorType.HALLS: SensorCategory.ABSOLUTE,
    SensorType.SSI2: SensorCategory.ABSOLUTE,
    SensorType.BISSC2: SensorCategory.ABSOLUTE,
    SensorType.QEI2: SensorCategory.INCREMENTAL,
    SensorType.INTGEN: SensorCategory.ABSOLUTE,
    SensorType.SINCOS: SensorCategory.INCREMENTAL,
}


class Feedbacks:
    """Feedbacks Wizard Class description."""

    __feedback_polarity_register_dict: Final[dict[SensorType, str]] = {
        SensorType.ABS1: "FBK_BISS1_SSI1_POS_POLARITY",
        SensorType.QEI: "FBK_DIGENC1_POLARITY",
        SensorType.HALLS: "FBK_DIGHALL_POLARITY",
        SensorType.SSI2: "FBK_SSI2_POS_POLARITY",
        SensorType.BISSC2: "FBK_BISS2_POS_POLARITY",
        SensorType.QEI2: "FBK_DIGENC2_POLARITY",
        SensorType.SINCOS: "FBK_SINCOS_POLARITY",
    }

    COMMUTATION_FEEDBACK_REGISTER = COMMUTATION_FEEDBACK_REGISTER
    REFERENCE_FEEDBACK_REGISTER = REFERENCE_FEEDBACK_REGISTER
    VELOCITY_FEEDBACK_REGISTER = VELOCITY_FEEDBACK_REGISTER
    POSITION_FEEDBACK_REGISTER = POSITION_FEEDBACK_REGISTER
    AUXILIAR_FEEDBACK_REGISTER = AUXILIAR_FEEDBACK_REGISTER

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)
        self.feedback_resolution_functions = {
            SensorType.ABS1: self.get_absolute_encoder_1_resolution,
            SensorType.QEI: self.get_incremental_encoder_1_resolution,
            SensorType.HALLS: self.get_digital_halls_resolution,
            SensorType.SSI2: self.get_secondary_ssi_resolution,
            SensorType.BISSC2: self.get_absolute_encoder_2_resolution,
            SensorType.QEI2: self.get_incremental_encoder_2_resolution,
            SensorType.SINCOS: self.get_sincos_encoder_resolution,
            SensorType.INTGEN: self.__no_feedback_resolution,
        }

    # Commutation feedback
    def get_commutation_feedback(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorType:
        """Reads commutation feedbacks value in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Type of feedback configured.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        commutation_feedback = self.mc._get_motion_node(servo).get_axis(axis).feedbacks.commutation
        return commutation_feedback.feedback

    @MCMetaClass.check_motor_disabled
    def set_commutation_feedback(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Writes commutation feedbacks value in the target servo and axis.

        Args:
            feedback : feedback sensor number
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.
        """
        self.mc._get_motion_node(servo).get_axis(axis).feedbacks.commutation.feedback = feedback

    def get_commutation_feedback_category(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorCategory:
        """Get the commutation feedback category.

        Reads commutation feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Category {ABSOLUTE, INCREMENTAL} of the selected feedback.
        """
        commutation_feedback = self.mc._get_motion_node(servo).get_axis(axis).feedbacks.commutation
        return commutation_feedback.category

    def get_commutation_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads commutation feedbacks resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of the selected feedback.
        """
        sensor_type = self.get_commutation_feedback(servo, axis)
        return self.feedback_resolution_functions[sensor_type](servo, axis)

    # Reference feedback
    def get_reference_feedback(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorType:
        """Reads reference feedbacks value in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Type of feedback configured

        Raises:
            TypeError: If some read value has a wrong type.

        """
        reference_feedback = self.mc._get_motion_node(servo).get_axis(axis).feedbacks.reference
        return reference_feedback.feedback

    @MCMetaClass.check_motor_disabled
    def set_reference_feedback(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Writes reference feedbacks value in the target servo and axis.

        Args:
            feedback : feedback sensor number
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.
        """
        self.mc._get_motion_node(servo).get_axis(axis).feedbacks.reference.feedback = feedback

    def get_reference_feedback_category(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorCategory:
        """Get the reference feedback category.

        Reads reference feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Category {ABSOLUTE, INCREMENTAL} of the selected feedback.
        """
        reference_feedback = self.mc._get_motion_node(servo).get_axis(axis).feedbacks.reference
        return reference_feedback.category

    def get_reference_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads reference feedbacks resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of the selected feedback.
        """
        sensor_type = self.get_reference_feedback(servo, axis)
        return self.feedback_resolution_functions[sensor_type](servo, axis)

    # Velocity feedback
    def get_velocity_feedback(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorType:
        """Reads velocity feedbacks value in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Type of feedback configured

        Raises:
            TypeError: If some read value has a wrong type.

        """
        velocity_feedback = self.mc._get_motion_node(servo).get_axis(axis).feedbacks.velocity
        return velocity_feedback.feedback

    @MCMetaClass.check_motor_disabled
    def set_velocity_feedback(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Writes velocity feedbacks value in the target servo and axis.

        Args:
            feedback : feedback sensor number
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.
        """
        self.mc._get_motion_node(servo).get_axis(axis).feedbacks.velocity.feedback = feedback

    def get_velocity_feedback_category(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorCategory:
        """Get the velocity feedback category.

        Reads velocity feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Category {ABSOLUTE, INCREMENTAL} of the selected feedback.
        """
        velocity_feedback = self.mc._get_motion_node(servo).get_axis(axis).feedbacks.velocity
        return velocity_feedback.category

    def get_velocity_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads velocity feedbacks resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of the selected feedback.
        """
        sensor_type = self.get_velocity_feedback(servo, axis)
        return self.feedback_resolution_functions[sensor_type](servo, axis)

    # Position feedback
    def get_position_feedback(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorType:
        """Reads position feedbacks value in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Type of feedback configured.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        position_feedback = self.mc._get_motion_node(servo).get_axis(axis).feedbacks.position
        return position_feedback.feedback

    @MCMetaClass.check_motor_disabled
    def set_position_feedback(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Writes position feedbacks value in the target servo and axis.

        Args:
            feedback : feedback sensor number
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.
        """
        self.mc._get_motion_node(servo).get_axis(axis).feedbacks.position.feedback = feedback

    def get_position_feedback_category(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorCategory:
        """Get the position feedback category.

        Reads position feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Category {ABSOLUTE, INCREMENTAL} of the selected feedback.
        """
        position_feedback = self.mc._get_motion_node(servo).get_axis(axis).feedbacks.position
        return position_feedback.category

    def get_position_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads position feedbacks resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of the selected feedback.
        """
        sensor_type = self.get_position_feedback(servo, axis)
        return self.feedback_resolution_functions[sensor_type](servo, axis)

    # Auxiliar feedback
    def get_auxiliar_feedback(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorType:
        """Reads auxiliar feedbacks value in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Type of feedback configured

        Raises:
            TypeError: If some read value has a wrong type.

        """
        auxiliar_feedback = self.mc._get_motion_node(servo).get_axis(axis).feedbacks.auxiliar
        return auxiliar_feedback.feedback

    @MCMetaClass.check_motor_disabled
    def set_auxiliar_feedback(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> None:
        """Writes auxiliar feedbacks value in the target servo and axis.

        Args:
            feedback : feedback sensor number
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            IMStatusWordError: If motor is enabled.
        """
        self.mc._get_motion_node(servo).get_axis(axis).feedbacks.auxiliar.feedback = feedback

    def get_auxiliar_feedback_category(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> SensorCategory:
        """Get the auxiliar feedback category.

        Reads auxiliar feedbacks type {ABSOLUTE or INCREMENTAL}
        in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Category {ABSOLUTE, INCREMENTAL} of the selected feedback.
        """
        auxiliar_feedback = self.mc._get_motion_node(servo).get_axis(axis).feedbacks.auxiliar
        return auxiliar_feedback.category

    def get_auxiliar_feedback_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> Optional[int]:
        """Reads auxiliar feedbacks resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of the selected feedback.
        """
        sensor_type = self.get_auxiliar_feedback(servo, axis)
        return self.feedback_resolution_functions[sensor_type](servo, axis)

    def get_absolute_encoder_1_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads ABS1 encoder resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Number of bits that represent single-turn information.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        single_turn_bits = self.mc.communication.get_register(
            "FBK_BISS1_SSI1_POS_ST_BITS", servo=servo, axis=axis
        )
        if not isinstance(single_turn_bits, int):
            raise TypeError("Single-turn bits has to be an integer")
        resolution = 2**single_turn_bits
        if not isinstance(resolution, int):
            raise TypeError("Resolution value has to be an integer")
        return resolution

    def get_incremental_encoder_1_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads incremental encoder 1 resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Number of counts per mechanical revolution.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        resolution = self.mc.communication.get_register(
            "FBK_DIGENC1_RESOLUTION", servo=servo, axis=axis
        )
        if not isinstance(resolution, int):
            raise TypeError("Resolution value has to be an integer")
        return resolution

    def get_digital_halls_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads digital halls pole pairs in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Number of counts per mechanical revolution.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        pair_poles = self.mc.communication.get_register(
            "FBK_DIGHALL_PAIRPOLES", servo=servo, axis=axis
        )
        resolution = 6 * pair_poles
        if not isinstance(resolution, int):
            raise TypeError("Resolution value has to be an integer")
        return resolution

    def get_secondary_ssi_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads secondary SSI encoder resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Number of bits that represent single-turn information.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        secondary_single_turn_bits = self.mc.communication.get_register(
            "FBK_SSI2_POS_ST_BITS", servo=servo, axis=axis
        )
        if not isinstance(secondary_single_turn_bits, int):
            raise TypeError("Resolution value has to be an integer")
        resolution = int(2**secondary_single_turn_bits)
        return resolution

    def get_absolute_encoder_2_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads ABS2 encoder resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Number of bits that represent single-turn information.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        serial_slave_1_single_turn_bits = self.mc.communication.get_register(
            "FBK_BISS2_POS_ST_BITS", servo=servo, axis=axis
        )
        if not isinstance(serial_slave_1_single_turn_bits, int):
            raise TypeError("Single-turn bits has to be an integer")
        resolution = int(2**serial_slave_1_single_turn_bits)
        return resolution

    def get_incremental_encoder_2_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads incremental encoder 2 resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Number of counts per mechanical revolution.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        resolution = self.mc.communication.get_register(
            "FBK_DIGENC2_RESOLUTION", servo=servo, axis=axis
        )
        if not isinstance(resolution, int):
            raise TypeError("Resolution value has to be an integer")
        return resolution

    def get_sincos_encoder_resolution(
        self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads the SinCos encoder resolution in the target servo and axis.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Number of counts per mechanical revolution.

        Raises:
            TypeError: If some read value has a wrong type.

        """
        resolution = self.mc.communication.get_register(
            "FBK_SINCOS_RESOLUTION", servo=servo, axis=axis
        )
        multiplier_reg_value = self.mc.communication.get_register(
            "FBK_SINCOS_MULT_FACTOR", servo=servo, axis=axis
        )
        if not isinstance(resolution, int):
            raise TypeError("Resolution value has to be an integer")
        if not isinstance(multiplier_reg_value, int):
            raise TypeError("Multiplier factor value has to be an integer")
        multiplier_factor = typing.cast("int", 2**multiplier_reg_value)
        return resolution * multiplier_factor

    def __no_feedback_resolution(self, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS) -> int:  # noqa: ARG002
        """Used for feedbacks that have no resolution.

        Args:
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Raises:
            ValueError: If the selected feedback does not have resolution.
        """
        raise ValueError("The selected feedback does not have resolution")

    def get_feedback_resolution(
        self, feedback: SensorType, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> int:
        """Reads target feedback resolution in the target servo and axis.

        Resolution units per SensorType:
            ABS1: Number of bits that represent single-turn information.
            INTGEN: N/A.
            QEI: Number of counts per mechanical revolution.
            HALLS: Number of counts per mechanical revolution.
            SSI2: Number of bits that represent single-turn information.
            BISSC2: Number of bits that represent single-turn information.
            QEI2: Number of counts per mechanical revolution.
            SINCOS: Number of counts per mechanical revolution.

        Args:
            feedback : target feedback.
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of target feedback.
        """
        return self.feedback_resolution_functions[feedback](servo, axis)

    def get_feedback_polarity_register_uid(self, feedback: SensorType) -> str:
        """Returns feedback polarity register UID.

        Args:
           feedback: target feedback sensor.

        Returns:
            Register UID

        """
        polarity_register = self.__feedback_polarity_register_dict.get(feedback)
        if polarity_register is None:
            raise NotImplementedError(f"Sensor {feedback.name} polarity is not implemented")
        return polarity_register

    def set_feedback_polarity(
        self,
        polarity: FeedbackPolarity,
        feedback: SensorType,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Set target feedback polarity in the target servo and axis.

        Args:
            polarity: target polarity.
            feedback: target feedback.
            servo: servo alias to reference it. ``default`` by default.
            axis: axis that will run the test. ``1`` by default.

        """
        polarity_register = self.get_feedback_polarity_register_uid(feedback)
        self.mc.communication.set_register(polarity_register, polarity, servo=servo, axis=axis)
        self.logger.debug(
            f"Feedback {feedback.name} polarity set to {polarity.name}",
            axis=axis,
            drive=self.mc.servo_name(servo),
        )

    def get_feedback_polarity(
        self,
        feedback: SensorType,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> Union[int, FeedbackPolarity]:
        """Get target feedback polarity of the target servo and axis.

        Args:
            feedback: target feedback.
            servo: servo alias to reference it. ``default`` by default.
            axis: axis that will run the test. ``1`` by default.

        Returns:
            Feedback polarity

        Raises:
            TypeError: If some read value has a wrong type.

        """
        polarity_register = self.get_feedback_polarity_register_uid(feedback)
        raw_polarity = self.mc.communication.get_register(polarity_register, servo=servo, axis=axis)
        if not isinstance(raw_polarity, int):
            raise TypeError("Polarity value has to be an integer")
        try:
            return FeedbackPolarity(raw_polarity)
        except ValueError:
            return raw_polarity


class FeedbackSlot:
    """Class to represent a feedback slot of an axis."""

    def __init__(self, register_uid: str, axis: "Axis") -> None:
        """Constructor.

        Args:
            register_uid: Register UID of the feedback selector.
            axis: Axis associated with the feedback slot.
        """
        self.__register_uid = register_uid
        self.__servo = axis.motion_node.servo
        self.__axis_number = axis.axis_number

    @property
    def feedback(self) -> SensorType:
        """The feedback sensor configured in the slot.

        Returns:
            The feedback sensor configured in the slot.

        Raises:
            TypeError: If the read value has a wrong type.
        """
        feedback = self.__servo.read(self.__register_uid, subnode=self.__axis_number)
        if not isinstance(feedback, int):
            raise TypeError("Feedback value has to be an integer")
        return SensorType(feedback)

    @feedback.setter
    def feedback(self, sensor: SensorType) -> None:
        """Set the feedback sensor of the slot.

        Args:
            sensor: Feedback sensor to configure.
        """
        self.__servo.write(self.__register_uid, sensor, subnode=self.__axis_number)

    @property
    def category(self) -> SensorCategory:
        """The category of the feedback sensor configured in the slot.

        Returns:
            The category of the feedback sensor configured in the slot.
        """
        return FEEDBACK_TYPE_DICT[self.feedback]


class AxisFeedbacks:
    """Class to manage the feedback slots of an axis."""

    def __init__(self, axis: "Axis") -> None:
        """Constructor.

        Args:
            axis: Axis associated with the feedback slots.
        """
        self.__axis = axis

    @property
    def commutation(self) -> FeedbackSlot:
        """The commutation feedback slot."""
        return FeedbackSlot(COMMUTATION_FEEDBACK_REGISTER, self.__axis)

    @property
    def reference(self) -> FeedbackSlot:
        """The reference feedback slot."""
        return FeedbackSlot(REFERENCE_FEEDBACK_REGISTER, self.__axis)

    @property
    def velocity(self) -> FeedbackSlot:
        """The velocity feedback slot."""
        return FeedbackSlot(VELOCITY_FEEDBACK_REGISTER, self.__axis)

    @property
    def position(self) -> FeedbackSlot:
        """The position feedback slot."""
        return FeedbackSlot(POSITION_FEEDBACK_REGISTER, self.__axis)

    @property
    def auxiliar(self) -> FeedbackSlot:
        """The auxiliar feedback slot."""
        return FeedbackSlot(AUXILIAR_FEEDBACK_REGISTER, self.__axis)

    def get_all_slots(self) -> tuple[FeedbackSlot, ...]:
        """Get all the feedback slots of the axis.

        Returns:
            A tuple with all the feedback slots of the axis.
        """
        return (self.commutation, self.reference, self.velocity, self.position, self.auxiliar)

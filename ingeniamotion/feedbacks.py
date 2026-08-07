from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar, Final, Optional

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


class Encoder(ABC):
    """Physical encoder of an axis.

    An encoder is what a feedback slot uses to sense the axis position. This
    class holds the encoder metadata (sensor type, category and polarity
    register) and computes its resolution from the drive registers.
    """

    SENSOR_TYPE: ClassVar[SensorType]
    CATEGORY: ClassVar[SensorCategory]
    POLARITY_REGISTER_UID: ClassVar[Optional[str]] = None

    def __init__(self, axis: "Axis") -> None:
        """Constructor.

        Args:
            axis: Axis associated with the encoder.
        """
        self.__servo = axis.motion_node.servo
        self.__axis_number = axis.axis_number

    def _read(self, reg_uid: str) -> int:
        """Read an integer register with type validation.

        Args:
            reg_uid: register UID to read.

        Returns:
            The register value as an integer.

        Raises:
            TypeError: If the register value is not an integer.
        """
        value = self.__servo.read(reg_uid, subnode=self.__axis_number)
        if not isinstance(value, int):
            raise TypeError(f"Register {reg_uid} value has to be an integer")
        return value

    def _write(self, reg_uid: str, value: int) -> None:
        """Write a register value.

        Args:
            reg_uid: register UID to write.
            value: value to write.
        """
        self.__servo.write(reg_uid, value, subnode=self.__axis_number)

    def get_polarity(self) -> FeedbackPolarity:
        """Get the polarity of the encoder.

        Returns:
            The polarity of the encoder.

        Raises:
            NotImplementedError: If the encoder polarity is not implemented.
            TypeError: If the read value has a wrong type.
            ValueError: If the polarity value is not a valid :class:`FeedbackPolarity`.
        """
        if self.POLARITY_REGISTER_UID is None:
            raise NotImplementedError(f"Sensor {self.SENSOR_TYPE.name} polarity is not implemented")
        raw_polarity = self._read(self.POLARITY_REGISTER_UID)
        return FeedbackPolarity(raw_polarity)

    def set_polarity(self, polarity: FeedbackPolarity) -> None:
        """Set the polarity of the encoder.

        Args:
            polarity: target polarity.

        Raises:
            NotImplementedError: If the encoder polarity is not implemented.
        """
        if self.POLARITY_REGISTER_UID is None:
            raise NotImplementedError(f"Sensor {self.SENSOR_TYPE.name} polarity is not implemented")
        self._write(self.POLARITY_REGISTER_UID, polarity)

    @abstractmethod
    def get_resolution(self) -> int:
        """The resolution of the encoder."""


class InternalGeneratorEncoder(Encoder):
    """Placeholder encoder for feedbacks without a physical encoder."""

    SENSOR_TYPE = SensorType.INTGEN
    CATEGORY = SensorCategory.ABSOLUTE

    def get_resolution(self) -> int:
        """The resolution of the encoder.

        Raises:
            ValueError: If the encoder has no resolution.
        """
        raise ValueError("Internal generator encoder has no resolution")


class AbsoluteEncoder(Encoder):
    """Encoder whose resolution is two raised to the single-turn bits."""

    CATEGORY = SensorCategory.ABSOLUTE
    _BITS_REGISTER_UID: ClassVar[str]

    def get_resolution(self) -> int:
        """The resolution of the encoder.

        Returns:
            The resolution of the encoder.

        Raises:
            TypeError: If some read value has a wrong type.
        """
        return int(2 ** self._read(self._BITS_REGISTER_UID))


class Abs1Encoder(AbsoluteEncoder):
    """ABS1 absolute encoder."""

    SENSOR_TYPE = SensorType.ABS1
    POLARITY_REGISTER_UID = "FBK_BISS1_SSI1_POS_POLARITY"
    _BITS_REGISTER_UID = "FBK_BISS1_SSI1_POS_ST_BITS"


class Ssi2Encoder(AbsoluteEncoder):
    """Secondary SSI absolute encoder."""

    SENSOR_TYPE = SensorType.SSI2
    POLARITY_REGISTER_UID = "FBK_SSI2_POS_POLARITY"
    _BITS_REGISTER_UID = "FBK_SSI2_POS_ST_BITS"


class Bissc2Encoder(AbsoluteEncoder):
    """BISSC2 absolute encoder."""

    SENSOR_TYPE = SensorType.BISSC2
    POLARITY_REGISTER_UID = "FBK_BISS2_POS_POLARITY"
    _BITS_REGISTER_UID = "FBK_BISS2_POS_ST_BITS"


class IncrementalEncoder(Encoder):
    """Encoder whose resolution is a register value."""

    CATEGORY = SensorCategory.INCREMENTAL
    _RESOLUTION_REGISTER_UID: ClassVar[str]

    def get_resolution(self) -> int:
        """The resolution of the encoder.

        Returns:
            The resolution of the encoder.

        Raises:
            TypeError: If some read value has a wrong type.
        """
        return self._read(self._RESOLUTION_REGISTER_UID)


class QeiEncoder(IncrementalEncoder):
    """QEI incremental encoder."""

    SENSOR_TYPE = SensorType.QEI
    POLARITY_REGISTER_UID = "FBK_DIGENC1_POLARITY"
    _RESOLUTION_REGISTER_UID = "FBK_DIGENC1_RESOLUTION"


class Qei2Encoder(IncrementalEncoder):
    """QEI2 incremental encoder."""

    SENSOR_TYPE = SensorType.QEI2
    POLARITY_REGISTER_UID = "FBK_DIGENC2_POLARITY"
    _RESOLUTION_REGISTER_UID = "FBK_DIGENC2_RESOLUTION"


class HallsEncoder(Encoder):
    """Digital halls encoder."""

    SENSOR_TYPE = SensorType.HALLS
    CATEGORY = SensorCategory.ABSOLUTE
    POLARITY_REGISTER_UID = "FBK_DIGHALL_POLARITY"
    _PAIR_POLES_REGISTER_UID = "FBK_DIGHALL_PAIRPOLES"

    def get_resolution(self) -> int:
        """The resolution of the encoder.

        Returns:
            The resolution of the encoder.

        Raises:
            TypeError: If some read value has a wrong type.
        """
        return 6 * self._read(self._PAIR_POLES_REGISTER_UID)


_ENCODER_TYPES: Final[dict[SensorType, type[Encoder]]] = {
    SensorType.ABS1: Abs1Encoder,
    SensorType.QEI: QeiEncoder,
    SensorType.HALLS: HallsEncoder,
    SensorType.SSI2: Ssi2Encoder,
    SensorType.BISSC2: Bissc2Encoder,
    SensorType.QEI2: Qei2Encoder,
    SensorType.INTGEN: InternalGeneratorEncoder,
}


class Feedbacks:
    """Feedbacks Wizard Class description."""

    COMMUTATION_FEEDBACK_REGISTER = COMMUTATION_FEEDBACK_REGISTER
    REFERENCE_FEEDBACK_REGISTER = REFERENCE_FEEDBACK_REGISTER
    VELOCITY_FEEDBACK_REGISTER = VELOCITY_FEEDBACK_REGISTER
    POSITION_FEEDBACK_REGISTER = POSITION_FEEDBACK_REGISTER
    AUXILIAR_FEEDBACK_REGISTER = AUXILIAR_FEEDBACK_REGISTER

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    def __axis_feedbacks(self, servo: str, axis: int) -> "AxisFeedbacks":
        """Get the feedback slots of the target servo and axis.

        Args:
            servo: servo alias to reference it.
            axis: axis that will run the test.

        Returns:
            The feedback slots of the target axis.
        """
        return self.mc._get_motion_node(servo).get_axis(axis).feedbacks

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
        return self.__axis_feedbacks(servo, axis).commutation.get_encoder_type()

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
        self.__axis_feedbacks(servo, axis).commutation.set_encoder_type(feedback)

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
        return self.__axis_feedbacks(servo, axis).commutation.get_encoder().CATEGORY

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
        return self.__axis_feedbacks(servo, axis).commutation.get_encoder().get_resolution()

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
        return self.__axis_feedbacks(servo, axis).reference.get_encoder_type()

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
        self.__axis_feedbacks(servo, axis).reference.set_encoder_type(feedback)

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
        return self.__axis_feedbacks(servo, axis).reference.get_encoder().CATEGORY

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
        return self.__axis_feedbacks(servo, axis).reference.get_encoder().get_resolution()

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
        return self.__axis_feedbacks(servo, axis).velocity.get_encoder_type()

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
        self.__axis_feedbacks(servo, axis).velocity.set_encoder_type(feedback)

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
        return self.__axis_feedbacks(servo, axis).velocity.get_encoder().CATEGORY

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
        return self.__axis_feedbacks(servo, axis).velocity.get_encoder().get_resolution()

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
        return self.__axis_feedbacks(servo, axis).position.get_encoder_type()

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
        self.__axis_feedbacks(servo, axis).position.set_encoder_type(feedback)

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
        return self.__axis_feedbacks(servo, axis).position.get_encoder().CATEGORY

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
        return self.__axis_feedbacks(servo, axis).position.get_encoder().get_resolution()

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
        return self.__axis_feedbacks(servo, axis).auxiliar.get_encoder_type()

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
        self.__axis_feedbacks(servo, axis).auxiliar.set_encoder_type(feedback)

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
        return self.__axis_feedbacks(servo, axis).auxiliar.get_encoder().CATEGORY

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
        return self.__axis_feedbacks(servo, axis).auxiliar.get_encoder().get_resolution()

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
        return self.__axis_feedbacks(servo, axis).get_resolution(SensorType.ABS1)

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
        return self.__axis_feedbacks(servo, axis).get_resolution(SensorType.QEI)

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
        return self.__axis_feedbacks(servo, axis).get_resolution(SensorType.HALLS)

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
        return self.__axis_feedbacks(servo, axis).get_resolution(SensorType.SSI2)

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
        return self.__axis_feedbacks(servo, axis).get_resolution(SensorType.BISSC2)

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
        return self.__axis_feedbacks(servo, axis).get_resolution(SensorType.QEI2)

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

        Args:
            feedback : target feedback.
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. ``1`` by default.

        Returns:
            Resolution of target feedback.
        """
        return self.__axis_feedbacks(servo, axis).get_resolution(feedback)

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

        Raises:
            NotImplementedError: If the sensor polarity is not implemented.

        """
        self.__axis_feedbacks(servo, axis).get_encoder(feedback).set_polarity(polarity)
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
    ) -> FeedbackPolarity:
        """Get target feedback polarity of the target servo and axis.

        Args:
            feedback: target feedback.
            servo: servo alias to reference it. ``default`` by default.
            axis: axis that will run the test. ``1`` by default.

        Returns:
            Feedback polarity

        Raises:
            NotImplementedError: If the sensor polarity is not implemented.
            TypeError: If some read value has a wrong type.
            ValueError: If the polarity value is not a valid :class:`FeedbackPolarity`.

        """
        return self.__axis_feedbacks(servo, axis).get_encoder(feedback).get_polarity()


class FeedbackSlot:
    """Class to represent a feedback slot of an axis."""

    def __init__(self, register_uid: str, axis: "Axis") -> None:
        """Constructor.

        Args:
            register_uid: Register UID of the feedback selector.
            axis: Axis associated with the feedback slot.
        """
        self.__register_uid = register_uid
        self.__axis = axis
        self.__servo = axis.motion_node.servo
        self.__axis_number = axis.axis_number

    def get_encoder_type(self) -> SensorType:
        """Get the sensor type configured in the slot.

        Returns:
            The sensor type configured in the slot.

        Raises:
            TypeError: If the read value has a wrong type.
        """
        feedback = self.__servo.read(self.__register_uid, subnode=self.__axis_number)
        if not isinstance(feedback, int):
            raise TypeError("Feedback value has to be an integer")
        return SensorType(feedback)

    def get_encoder(self) -> Encoder:
        """Get the encoder configured in the slot.

        Returns:
            The encoder configured in the slot.
        """
        return self.__axis.feedbacks.get_encoder(self.get_encoder_type())

    def set_encoder_type(self, sensor: SensorType) -> None:
        """Configure the sensor type of the slot.

        Args:
            sensor: Feedback sensor to configure.
        """
        self.__servo.write(self.__register_uid, sensor, subnode=self.__axis_number)

    def set_encoder(self, encoder: Encoder) -> None:
        """Configure the encoder of the slot.

        Args:
            encoder: Encoder to configure.
        """
        self.set_encoder_type(encoder.SENSOR_TYPE)


class AxisFeedbacks:
    """Class to manage the feedback slots of an axis."""

    def __init__(self, axis: "Axis") -> None:
        """Constructor.

        Args:
            axis: Axis associated with the feedback slots.
        """
        self.__axis = axis
        self.__encoders = {
            sensor: encoder_type(axis) for sensor, encoder_type in _ENCODER_TYPES.items()
        }

    def get_encoder(self, sensor: SensorType) -> Encoder:
        """Get the encoder of the target feedback sensor in the axis.

        Args:
            sensor: target feedback sensor.

        Returns:
            The encoder of the target feedback sensor.
        """
        return self.__encoders[sensor]

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

    def get_resolution(self, sensor: SensorType) -> int:
        """Get the resolution of the target feedback sensor in the axis.

        Args:
            sensor: target feedback sensor.

        Returns:
            The resolution of the target feedback sensor.

        Raises:
            ValueError: If the feedback sensor has no resolution.
            TypeError: If some read value has a wrong type.
        """
        return self.get_encoder(sensor).get_resolution()

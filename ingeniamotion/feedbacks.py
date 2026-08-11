from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, ClassVar, Final, Optional

import ingenialogger

from ingeniamotion._utils import weak_lru, weak_lru_prop
from ingeniamotion.enums import FeedbackPolarity, SensorCategory, SensorType

if TYPE_CHECKING:
    from ingeniamotion.axis import Axis
    from ingeniamotion.motion_controller import MotionController
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO, MCMetaClass

COMMUTATION_FEEDBACK_REGISTER = "COMMU_ANGLE_SENSOR"
REFERENCE_FEEDBACK_REGISTER = "COMMU_ANGLE_REF_SENSOR"
VELOCITY_FEEDBACK_REGISTER = "CL_VEL_FBK_SENSOR"
POSITION_FEEDBACK_REGISTER = "CL_POS_FBK_SENSOR"
AUXILIARY_FEEDBACK_REGISTER = "CL_AUX_FBK_SENSOR"

FEEDBACK_SELECTOR_REGISTERS: Final[tuple[str, ...]] = (
    COMMUTATION_FEEDBACK_REGISTER,
    REFERENCE_FEEDBACK_REGISTER,
    VELOCITY_FEEDBACK_REGISTER,
    POSITION_FEEDBACK_REGISTER,
    AUXILIARY_FEEDBACK_REGISTER,
)
MAX_SIMULTANEOUS_FEEDBACKS = 4


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
        self.__axis = axis

    def __eq__(self, other: object) -> bool:
        """Compare encoders by their axis and sensor type.

        Returns:
            Whether both encoders refer to the same axis and sensor type.
        """
        if not isinstance(other, Encoder):
            return NotImplemented
        return self.__axis is other.__axis and self.SENSOR_TYPE == other.SENSOR_TYPE

    def __hash__(self) -> int:
        """Hash the encoder by its axis and sensor type.

        Returns:
            A hash derived from the axis identity and sensor type.
        """
        return hash((id(self.__axis), self.SENSOR_TYPE))

    def _read(self, reg_uid: str) -> int:
        """Read an integer register with type validation.

        Args:
            reg_uid: register UID to read.

        Returns:
            The register value as an integer.

        Raises:
            TypeError: If the register value is not an integer.
        """
        value = self.__axis.read(reg_uid)
        if not isinstance(value, int):
            raise TypeError(f"Register {reg_uid} value has to be an integer")
        return value

    def _write(self, reg_uid: str, value: int) -> None:
        """Write a register value.

        Args:
            reg_uid: register UID to write.
            value: value to write.
        """
        self.__axis.write(reg_uid, value)

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

    @property
    def register_uid(self) -> str:
        """Register UID of the feedback selector."""
        return self.__register_uid

    def get_encoder_type(self) -> SensorType:
        """Get the sensor type configured in the slot.

        Returns:
            The sensor type configured in the slot.

        Raises:
            TypeError: If the read value has a wrong type.
        """
        feedback = self.__axis.read(self.__register_uid)
        if not isinstance(feedback, int):
            raise TypeError("Feedback value has to be an integer")
        return SensorType(feedback)

    def get_encoder(self) -> Encoder:
        """Get the encoder configured in the slot.

        Returns:
            The encoder configured in the slot.
        """
        return self.__axis.feedbacks.get_sensor(self.get_encoder_type())

    def set_encoder_type(self, sensor: SensorType) -> None:
        """Configure the sensor type of the slot.

        Args:
            sensor: Feedback sensor to configure.

        Raises:
            ValueError: If the drive does not allow this sensor type in the slot.
        """
        if not self.supports(sensor):
            raise ValueError(f"{sensor.name} is not a valid sensor type for {self.__register_uid}.")
        self.__axis.write(self.__register_uid, sensor)

    def set_encoder(self, encoder: Encoder) -> None:
        """Configure the encoder of the slot.

        Args:
            encoder: Encoder to configure.
        """
        self.set_encoder_type(encoder.SENSOR_TYPE)

    def supports(self, sensor_type: SensorType) -> bool:
        """Return whether the drive allows this sensor type in the slot.

        Not every sensor type is a legal value for every selector register;
        the connected drive's dictionary defines, per register, which values
        it accepts.

        Args:
            sensor_type: Sensor type to check.

        Returns:
            Whether the drive's dictionary lists ``sensor_type`` as a valid
            value for this slot's selector register.
        """
        register = self.__axis.motion_node.servo.dictionary.registers(self.__axis.axis_number)[
            self.__register_uid
        ]
        return sensor_type.value in register.enums.values()


class FeedbacksConfiguration:
    """Encoder assigned to each feedback slot of an axis."""

    def __init__(self, encoders: Mapping[FeedbackSlot, Encoder]) -> None:
        """Constructor.

        Args:
            encoders: Encoder assigned to each feedback slot.
        """
        self.__encoders = dict(encoders)

    @classmethod
    def from_axis_feedbacks(cls, axis_feedbacks: "AxisFeedbacks") -> "FeedbacksConfiguration":
        """Read the encoder currently assigned to every feedback slot of an axis.

        Args:
            axis_feedbacks: Feedback slots container to read.

        Returns:
            The current feedback configuration.
        """
        return cls({
            slot: axis_feedbacks.get_sensor(slot.get_encoder_type())
            for slot in axis_feedbacks._slots
        })

    @classmethod
    def from_sensor_types(
        cls,
        axis_feedbacks: "AxisFeedbacks",
        *,
        commutation: SensorType,
        reference: SensorType,
        velocity: SensorType,
        position: SensorType,
        auxiliary: SensorType,
    ) -> "FeedbacksConfiguration":
        """Build a configuration assigning sensor types to named feedback slots.

        Args:
            axis_feedbacks: Feedback slots container to build the configuration for.
            commutation: Sensor type to assign to the commutation slot.
            reference: Sensor type to assign to the reference slot.
            velocity: Sensor type to assign to the velocity slot.
            position: Sensor type to assign to the position slot.
            auxiliary: Sensor type to assign to the auxiliary slot.

        Returns:
            A configuration assigning each sensor to the corresponding feedback slot.
        """
        return cls({
            axis_feedbacks.commutation: axis_feedbacks.get_sensor(commutation),
            axis_feedbacks.reference: axis_feedbacks.get_sensor(reference),
            axis_feedbacks.velocity: axis_feedbacks.get_sensor(velocity),
            axis_feedbacks.position: axis_feedbacks.get_sensor(position),
            axis_feedbacks.auxiliary: axis_feedbacks.get_sensor(auxiliary),
        })

    def encoder_at(self, slot: FeedbackSlot) -> Encoder:
        """Return the encoder assigned to the given feedback slot.

        Args:
            slot: Feedback slot to look up.

        Returns:
            The encoder assigned to that slot.
        """
        return self.__encoders[slot]

    def with_encoder_at(self, slot: FeedbackSlot, encoder: Encoder) -> "FeedbacksConfiguration":
        """Return a copy with the encoder at the given slot changed.

        Args:
            slot: Feedback slot to update.
            encoder: Encoder to assign to that slot.

        Returns:
            A new configuration with the slot updated.
        """
        return FeedbacksConfiguration({**self.__encoders, slot: encoder})

    def replace(self, changes: Mapping[FeedbackSlot, Encoder]) -> "FeedbacksConfiguration":
        """Return a copy with the given slots changed.

        Args:
            changes: Encoder to assign per feedback slot to update.

        Returns:
            A new configuration containing the requested changes.
        """
        return FeedbacksConfiguration({**self.__encoders, **changes})

    def active_sensors(self) -> frozenset[SensorType]:
        """Return the distinct sensor types assigned across all slots."""
        return frozenset(encoder.SENSOR_TYPE for encoder in self.__encoders.values())

    def can_execute_transition(self, slot: FeedbackSlot, encoder: Encoder) -> bool:
        """Return whether the drive accepts assigning an encoder to a slot.

        The drive checks the number of active sensor types before replacing an
        encoder. This is conservative and can reject a write that would leave
        four active types after the replacement, but it reflects the drive's
        actual implementation. The slot is part of the operation because a
        smarter drive could also apply slot-specific rules. This does not check
        whether ``encoder`` is a legal value for the target slot on the
        connected drive; that is enforced when the write is actually issued,
        by :meth:`FeedbackSlot.set_encoder_type`.

        Args:
            slot: Feedback slot that would receive the encoder.
            encoder: Encoder that would be assigned to a slot.

        Returns:
            Whether the drive accepts the individual selector write.
        """
        current_encoder = self.encoder_at(slot)
        active_sensors = self.active_sensors()
        return (
            current_encoder == encoder
            or len(active_sensors) < MAX_SIMULTANEOUS_FEEDBACKS
            or encoder.SENSOR_TYPE in active_sensors
        )

    def active_encoders_in_order(self) -> tuple[Encoder, ...]:
        """Return distinct assigned encoders in deterministic first-seen order.

        The transition algorithm uses these encoders as parking candidates. A
        slot can be temporarily assigned an encoder that is already active in
        another slot to free one of the drive's limited sensor entries. Keeping
        the first-seen order makes that search deterministic.
        """
        return tuple(dict.fromkeys(self.__encoders.values()))


def _find_feedback_order(  # noqa: C901
    target: FeedbacksConfiguration,
    state: FeedbacksConfiguration,
    pending: tuple[FeedbackSlot, ...],
) -> Optional[list[tuple[FeedbackSlot, Encoder]]]:
    """Find a safe order for reaching the target configuration.

    The drive supports at most four distinct active feedback sensors across
    five selector slots. The search first tries direct target writes that do
    not introduce a new fifth sensor. If no direct write is possible, it
    temporarily parks a pending slot on an encoder already active elsewhere,
    reducing the number of distinct sensors and making room for the target.
    The returned order includes these temporary parking writes.

    Args:
        target: Target feedback configuration.
        state: Feedback configuration reached so far.
        pending: Slots that still need to reach their target.

    Returns:
        Slot and encoder pairs in safe write order, or ``None`` if no safe
        order exists from this state.
    """
    if not pending:
        return []

    # First, try to apply a pending target directly. This is safe when the
    # target encoder is already active or there is still room for a new sensor.
    for slot in pending:
        target_encoder = target.encoder_at(slot)
        if not state.can_execute_transition(slot, target_encoder):
            continue
        # Candidate configuration with the target encoder assigned to this slot.
        candidate_state = state.with_encoder_at(slot, target_encoder)
        remaining = tuple(s for s in pending if s != slot)
        suffix = _find_feedback_order(target, candidate_state, remaining)
        if suffix is not None:
            return [(slot, target_encoder), *suffix]

    # If every direct write is blocked, temporarily park a pending slot on an
    # encoder already in use. This removes a distinct sensor and makes room for
    # one of the target encoders in a later recursive step.
    for slot in pending:
        for parking_encoder in state.active_encoders_in_order():
            if state.encoder_at(slot) == parking_encoder:
                continue
            if not state.can_execute_transition(slot, parking_encoder):
                continue
            # Candidate configuration with this slot temporarily assigned to an
            # encoder that is already active in another slot.
            candidate_state = state.with_encoder_at(slot, parking_encoder)
            if len(candidate_state.active_sensors()) >= len(state.active_sensors()):
                continue
            suffix = _find_feedback_order(target, candidate_state, pending)
            if suffix is not None:
                return [(slot, parking_encoder), *suffix]
    return None


class AxisFeedbacks:
    """Class to manage the feedback slots of an axis.

    Attributes:
        commutation: The commutation feedback slot.
        reference: The reference feedback slot.
        velocity: The velocity feedback slot.
        position: The position feedback slot.
        auxiliary: The auxiliary feedback slot.
    """

    def __init__(self, axis: "Axis") -> None:
        """Constructor.

        Args:
            axis: Axis associated with the feedback slots.
        """
        self.__axis = axis

    @weak_lru_prop
    def commutation(self) -> FeedbackSlot:
        """The commutation feedback slot.

        Returns:
            The commutation feedback slot, built on first access.
        """
        return FeedbackSlot(COMMUTATION_FEEDBACK_REGISTER, self.__axis)

    @weak_lru_prop
    def reference(self) -> FeedbackSlot:
        """The reference feedback slot.

        Returns:
            The reference feedback slot, built on first access.
        """
        return FeedbackSlot(REFERENCE_FEEDBACK_REGISTER, self.__axis)

    @weak_lru_prop
    def velocity(self) -> FeedbackSlot:
        """The velocity feedback slot.

        Returns:
            The velocity feedback slot, built on first access.
        """
        return FeedbackSlot(VELOCITY_FEEDBACK_REGISTER, self.__axis)

    @weak_lru_prop
    def position(self) -> FeedbackSlot:
        """The position feedback slot.

        Returns:
            The position feedback slot, built on first access.
        """
        return FeedbackSlot(POSITION_FEEDBACK_REGISTER, self.__axis)

    @weak_lru_prop
    def auxiliary(self) -> FeedbackSlot:
        """The auxiliary feedback slot.

        Returns:
            The auxiliary feedback slot, built on first access.
        """
        return FeedbackSlot(AUXILIARY_FEEDBACK_REGISTER, self.__axis)

    @property
    def _slots(self) -> tuple[FeedbackSlot, ...]:
        """The feedback slots in feedback selector order."""
        return (self.commutation, self.reference, self.velocity, self.position, self.auxiliary)

    @weak_lru(maxsize=None)
    def get_sensor(self, sensor: SensorType) -> Encoder:
        """Get the target feedback sensor in the axis.

        Args:
            sensor: target feedback sensor.

        Returns:
            The encoder of the target feedback sensor.
        """
        return _ENCODER_TYPES[sensor](self.__axis)

    def get_configuration(self) -> FeedbacksConfiguration:
        """Read the sensor configuration of every feedback slot.

        Returns:
            The current feedback selector configuration.
        """
        return FeedbacksConfiguration.from_axis_feedbacks(self)

    def set_configuration(self, target: FeedbacksConfiguration) -> None:
        """Safely transition all feedback slots to a target configuration.

        The drive allows at most four distinct feedback sensors across its five
        selector registers. Writes are ordered so that this limit is never
        exceeded: if a target introduces a fifth sensor, an active sensor is
        temporarily parked in another slot before the target is written. The
        temporary parking writes are part of the transition and are applied
        automatically.

        Args:
            target: Desired feedback selector configuration.

        Raises:
            ValueError: If the target cannot be reached without exceeding the drive
                feedback limit.
        """
        for slot, encoder in self.transition_order(self.get_configuration(), target):
            slot.set_encoder(encoder)

    def transition_order(
        self,
        current: FeedbacksConfiguration,
        target: FeedbacksConfiguration,
    ) -> Iterator[tuple[FeedbackSlot, Encoder]]:
        """Order feedback writes without exceeding four active sensors.

        Args:
            current: Current feedback selector configuration.
            target: Target feedback selector configuration.

        Yields:
            Feedback slot and encoder pairs in safe write order.

        Raises:
            ValueError: If the target cannot be reached without exceeding the drive
                feedback limit.
        """
        pending = tuple(
            slot for slot in self._slots if current.encoder_at(slot) != target.encoder_at(slot)
        )
        order = _find_feedback_order(target, current, pending)
        if order is None:
            raise ValueError("Feedback configurations cannot be transitioned safely.")
        yield from order


class Feedbacks:
    """Feedbacks Wizard Class description."""

    COMMUTATION_FEEDBACK_REGISTER = COMMUTATION_FEEDBACK_REGISTER
    REFERENCE_FEEDBACK_REGISTER = REFERENCE_FEEDBACK_REGISTER
    VELOCITY_FEEDBACK_REGISTER = VELOCITY_FEEDBACK_REGISTER
    POSITION_FEEDBACK_REGISTER = POSITION_FEEDBACK_REGISTER
    AUXILIAR_FEEDBACK_REGISTER = AUXILIARY_FEEDBACK_REGISTER

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
        return self.__axis_feedbacks(servo, axis).auxiliary.get_encoder_type()

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
        self.__axis_feedbacks(servo, axis).auxiliary.set_encoder_type(feedback)

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
        return self.__axis_feedbacks(servo, axis).auxiliary.get_encoder().CATEGORY

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
        return self.__axis_feedbacks(servo, axis).auxiliary.get_encoder().get_resolution()

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
        return self.__axis_feedbacks(servo, axis).get_sensor(SensorType.ABS1).get_resolution()

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
        return self.__axis_feedbacks(servo, axis).get_sensor(SensorType.QEI).get_resolution()

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
        return self.__axis_feedbacks(servo, axis).get_sensor(SensorType.HALLS).get_resolution()

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
        return self.__axis_feedbacks(servo, axis).get_sensor(SensorType.SSI2).get_resolution()

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
        return self.__axis_feedbacks(servo, axis).get_sensor(SensorType.BISSC2).get_resolution()

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
        return self.__axis_feedbacks(servo, axis).get_sensor(SensorType.QEI2).get_resolution()

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
        return self.__axis_feedbacks(servo, axis).get_sensor(feedback).get_resolution()

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
        self.__axis_feedbacks(servo, axis).get_sensor(feedback).set_polarity(polarity)
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
        return self.__axis_feedbacks(servo, axis).get_sensor(feedback).get_polarity()

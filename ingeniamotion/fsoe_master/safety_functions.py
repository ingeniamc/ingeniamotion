# ruff: noqa: ERA001, PERF203
import dataclasses
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Union, get_args, get_origin

from ingeniamotion.fsoe_master.fsoe import (
    FSoEDictionaryItem,
    FSoEDictionaryItemInput,
    FSoEDictionaryItemInputOutput,
)
from ingeniamotion.fsoe_master.parameters import SafetyParameter

if TYPE_CHECKING:
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler

__all__ = [
    "SafeHomingFunction",
    "SafeInputsFunction",
    "SafetyFunction",
    "SLPFunction",
    "SLSFunction",
    "SOSFunction",
    "SOutFunction",
    "SPFunction",
    "SS1Function",
    "SS2Function",
    "SSRFunction",
    "STOFunction",
    "SVFunction",
]


@dataclass(frozen=True)
class SafetyFieldMetadata:
    """Metadata for safety fields.

    Can either represent a prototype for a field (with placeholders in the UID),
    or a specific instance (with concrete values in the UID).

    Attributes:
        uid: Unique identifier for the safety field.
            May include an instance index, e.g. `FSOE_SS1_{i}`.
        display_name: Name of the safety field for documentation and display.
        attr_name: Attribute name of the field in the SafetyFunction class.
    """

    uid: str
    display_name: str
    attr_name: str


def safety_field(uid: str, display_name: str):  # type: ignore[no-untyped-def]
    """Create a dataclass field with metadata for safety functions.

    Args:
        uid: Unique identifier of the register associated with the field.
            May include an instance index, e.g. `FSOE_SS1_{i}`.

        display_name: Name of the field for documentation and display.

    Returns:
        dataclass field with safety metadata
    """
    return dataclasses.field(metadata={"uid": uid, "display_name": display_name})


def is_optional(field_type: type) -> tuple[bool, type]:
    """Check if a field type is Optional and get the internal type.

    Returns:
        A tuple with a boolean indicating if the field is Optional,
        and the internal type if it is Optional, or the original type if not.
    """
    is_optional = get_origin(field_type) is Optional or (
        get_origin(field_type) is Union and type(None) in get_args(field_type)
    )

    if not is_optional:
        return False, field_type

    internal_type = next(x for x in get_args(field_type) if x is not None)
    return True, internal_type


@dataclass()
class SafetyFunction:
    """Base class for Safety Functions.

    Wraps input/output items and parameters used by the FSoE Master handler.
    """

    n_instance: Optional[int]
    """Number of instances of the safety function, if applicable."""

    name: str
    """Name of the safety function.
    In the class var it may include an instance index, e.g. `Safe Stop {i}`."""

    ios: dict[SafetyFieldMetadata, FSoEDictionaryItem]
    parameters: dict[SafetyFieldMetadata, SafetyParameter]

    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        """Get the safety function instances for a given FSoE master handler.

        Yields:
            All safety function instances available for the handler.
        """
        yield from STOFunction._explore_instances(handler)
        yield from SS1Function._explore_instances(handler)
        yield from SafeInputsFunction._explore_instances(handler)
        yield from SOSFunction._explore_instances(handler)
        yield from SS2Function._explore_instances(handler)
        yield from SOutFunction._explore_instances(handler)
        yield from SPFunction._explore_instances(handler)
        yield from SVFunction._explore_instances(handler)
        yield from SafeHomingFunction._explore_instances(handler)
        yield from SLSFunction._explore_instances(handler)
        yield from SSRFunction._explore_instances(handler)
        yield from SLPFunction._explore_instances(handler)

    @classmethod
    def _create_instance(
        cls, handler: "FSoEMasterHandler", n_instance: Optional[int] = None
    ) -> Iterator["SafetyFunction"]:
        """Create an instance of the safety function.

        Args:
            handler: The FSoE master handler to use.
            n_instance: The instance index to use for the safety function.
                Formatted into the UID if provided.
                If not the function is assumed to be single-instance.

        Raises:
            KeyError: If the required input/output items
                or parameters are not found in the handler's dictionary.

        Yields:
            Iterator[SafetyFunction]: An iterator yielding the safety function instance.
        """
        ios: dict[SafetyFieldMetadata, Optional[FSoEDictionaryItem]] = {}
        parameters: dict[SafetyFieldMetadata, Optional[SafetyParameter]] = {}
        for field in dataclasses.fields(cls):
            metadata_dict = field.metadata.copy()
            if "uid" not in metadata_dict:
                continue

            if n_instance is not None:
                metadata_dict["uid"] = metadata_dict["uid"].format(i=n_instance)

            metadata = SafetyFieldMetadata(**metadata_dict, attr_name=field.name)

            optional, field_type = is_optional(field.type)

            if field_type == FSoEDictionaryItemInputOutput:
                ios[metadata] = cls._get_input_output(handler, metadata.uid, optional)
            elif field_type == FSoEDictionaryItemInput:
                ios[metadata] = cls._get_input(handler, metadata.uid, optional)
            elif field_type == SafetyParameter:
                parameters[metadata] = cls._get_parameter(handler, metadata.uid, optional)

        name = cls.name.format(i=n_instance) if n_instance else cls.name

        yield cls(
            n_instance=n_instance,
            name=name,
            ios={metadata: io for metadata, io in ios.items() if io is not None},
            parameters={
                metadata: parameter
                for metadata, parameter in parameters.items()
                if parameter is not None
            },
            **{field.attr_name: io for field, io in ios.items()},
            **{field.attr_name: parameter for field, parameter in parameters.items()},
        )

    @classmethod
    def _explore_instances(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        """Explore instances of the safety function.

        Tries to create instances of each safety functions according to the availability of
        the input/output items and parameters in the handler's dictionary.

        Yields:
            int: Instances of the safety function available for the handler.
        """
        # Check if the instance is single-instance
        try:
            yield from cls._create_instance(handler)
            return
        except KeyError:
            pass

        # If not single-instance, explore instances until a KeyError is raised.
        i = 1
        try:
            while True:
                yield from cls._create_instance(handler, n_instance=i)
                i += 1
        except KeyError:
            return

    @classmethod
    def _get_input_output(
        cls, handler: "FSoEMasterHandler", uid: str, optional: bool
    ) -> Optional[FSoEDictionaryItemInputOutput]:
        """Get the input/output item from the handler's dictionary.

        Args:
            handler: The FSoE master handler to use.
            uid: The unique identifier of the input/output item.
            optional: Whether the item is optional or required.

        Raises:
            KeyError: if the item is not found.
            TypeError: if the item is not of type FSoEDictionaryItemInputOutput.

        Returns:
            FSoEDictionaryItemInputOutput: The required input/output item.
        """
        item = handler.dictionary.name_map.get(uid)
        if not optional:
            if item is None:
                raise KeyError(f"Dictionary item {uid} not found in the handler's dictionary")
            if not isinstance(item, FSoEDictionaryItemInputOutput):
                raise TypeError(
                    f"Expected DictionaryItemInputOutput {uid} "
                    f"on the safe dictionary, got {type(item)}"
                )
        return item

    @classmethod
    def _get_input(
        cls, handler: "FSoEMasterHandler", uid: str, optional: bool
    ) -> Optional[FSoEDictionaryItemInput]:
        """Get the input item from the handler's dictionary.

        Args:
            handler: The FSoE master handler to use.
            uid: The unique identifier of the input item.
            optional: Whether the item is optional or required.

        Raises:
            KeyError: if the item is not found.
            TypeError: if the item is not of type FSoEDictionaryItemInput.

        Returns:
            FSoEDictionaryItemInput: The required input item.
        """
        item = handler.dictionary.name_map.get(uid)
        if not optional:
            if item is None:
                raise KeyError(f"Dictionary item {uid} not found in the handler's dictionary")
            if not isinstance(item, FSoEDictionaryItemInput):
                raise TypeError(
                    f"Expected DictionaryItemInput {uid} on the safe dictionary, got {type(item)}"
                )
        return item

    @classmethod
    def _get_parameter(
        cls, handler: "FSoEMasterHandler", uid: str, optional: bool
    ) -> Optional[SafetyParameter]:
        """Get the parameter from the handler's safety parameters.

        Args:
            handler: The FSoE master handler to use.
            uid: The unique identifier of the safety parameter.
            optional: Whether the parameter is optional or required.

        Raises:
             KeyError: if the parameter is not found.

        Returns:
                SafetyParameter: The required safety parameter.
        """
        param = handler.safety_parameters.get(uid, None)
        if not optional and uid not in handler.safety_parameters:
            raise KeyError(f"Safety parameter {uid} not found in the handler's safety parameters")

        return param


@dataclass()
class STOFunction(SafetyFunction):
    """Safe Torque Off Safety Function."""

    name = "Safe Torque Off"

    COMMAND_UID = "FSOE_STO"

    command: FSoEDictionaryItemInputOutput = safety_field(uid=COMMAND_UID, display_name="Command")
    activate_sout: Optional[SafetyParameter] = safety_field(
        uid="FSOE_STO_ACTIVATE_SOUT", display_name="Activate SOUT"
    )


@dataclass()
class SS1Function(SafetyFunction):
    """Safe Stop 1 Safety Function."""

    name = "Safe Stop {i}"

    COMMAND_UID = "FSOE_SS1_{i}"

    command: FSoEDictionaryItemInputOutput = safety_field(uid=COMMAND_UID, display_name="Command")
    time_to_sto: SafetyParameter = safety_field(
        uid="FSOE_SS1_TIME_TO_STO_{i}", display_name="Time to STO"
    )
    velocity_zero_window: Optional[SafetyParameter] = safety_field(
        uid="FSOE_SS1_VEL_ZERO_WINDOW_{i}", display_name="Velocity Zero Window"
    )
    time_for_velocity_zero: Optional[SafetyParameter] = safety_field(
        uid="FSOE_SS1_TIME_FOR_VEL_ZERO_{i}", display_name="Time for Velocity Zero"
    )

    time_delay_for_deceleration: Optional[SafetyParameter] = safety_field(
        "FSOE_SS1_TIME_DELAY_DEC_{i}", display_name="Time Delay for Deceleration"
    )
    deceleration_limit: Optional[SafetyParameter] = safety_field(
        uid="FSOE_SS1_DEC_LIMIT_{i}", display_name="Deceleration Limit"
    )
    activate_sout: Optional[SafetyParameter] = safety_field(
        uid="FSOE_SS1_ACTIVATE_SOUT_{i}", display_name="Activate SOUT"
    )


@dataclass()
class SafeInputsFunction(SafetyFunction):
    """Safe Inputs Safety Function."""

    name = "Safe Inputs"

    SAFE_INPUTS_UID = "FSOE_SAFE_INPUTS_VALUE"
    value: FSoEDictionaryItemInput = safety_field(uid=SAFE_INPUTS_UID, display_name="Value")
    map: SafetyParameter = safety_field(uid="FSOE_SAFE_INPUTS_MAP", display_name="Map")


@dataclass()
class SOSFunction(SafetyFunction):
    """Safe Operation Stop Safety Function."""

    name = "Safe Operation Stop {i}"

    command: FSoEDictionaryItemInputOutput = safety_field(
        uid="FSOE_SOS_{i}", display_name="Command"
    )
    position_zero_window: SafetyParameter = safety_field(
        uid="FSOE_SOS_POS_ZERO_WINDOW_{i}", display_name="Position Zero Window"
    )
    velocity_zero_window: SafetyParameter = safety_field(
        uid="FSOE_SOS_VEL_ZERO_WINDOW_{i}", display_name="Velocity Zero Window"
    )


@dataclass()
class SS2Function(SafetyFunction):
    """Safe Stop 2 Safety Function."""

    name = "Safe Stop 2 {i}"

    command: FSoEDictionaryItemInputOutput = safety_field(
        uid="FSOE_SS2_{i}", display_name="Command"
    )
    time_to_sos: SafetyParameter = safety_field(
        uid="FSOE_SS2_TIME_TO_SOS_{i}", display_name="Time to SOS"
    )
    deceleration_limit: SafetyParameter = safety_field(
        uid="FSOE_SS2_DEC_LIMIT_{i}", display_name="Deceleration Limit"
    )
    time_delay_deceleration_limit: SafetyParameter = safety_field(
        uid="FSOE_SS2_TIME_DELAY_DEC_{i}", display_name="Time Delay Deceleration Limit"
    )
    error_reaction: SafetyParameter = safety_field(
        uid="FSOE_SS2_ERROR_REACTION_{i}", display_name="Error Reaction"
    )


@dataclass()
class SOutFunction(SafetyFunction):
    """Safe Output Safety Function."""

    name = "Safe Output"

    command: FSoEDictionaryItemInputOutput = safety_field(uid="FSOE_SOUT", display_name="Command")
    brake_time_delay: SafetyParameter = safety_field(
        uid="FSOE_SOUT_BRAKE_TIME_DELAY", display_name="Electromechanical delay for a brake"
    )
    sout_disable: SafetyParameter = safety_field(
        uid="FSOE_SOUT_DISABLE", display_name="Disables the SOUT functionality"
    )


@dataclass()
class SPFunction(SafetyFunction):
    """Safe Position Safety Function."""

    name = "Safe Position"

    value: FSoEDictionaryItemInput = safety_field(uid="FSOE_SAFE_POSITION", display_name="Value")
    tolerance: SafetyParameter = safety_field(
        uid="FSOE_POSITION_TOLERANCE", display_name="Tolerance"
    )


@dataclass()
class SVFunction(SafetyFunction):
    """Safe Velocity Safety Function."""

    name = "Safe Velocity"

    value: FSoEDictionaryItemInput = safety_field("FSOE_SAFE_VELOCITY", display_name="Value")


@dataclass()
class SafeHomingFunction(SafetyFunction):
    """Safe Homing Safety Function."""

    name = "Safe Homing"

    command: FSoEDictionaryItemInputOutput = safety_field(
        uid="FSOE_SAFE_HOMING", display_name="Command"
    )
    homing_ref: SafetyParameter = safety_field(
        uid="FSOE_SAFE_HOMING_REFERENCE", display_name="Reference"
    )


@dataclass()
class SLSFunction(SafetyFunction):
    """Safe Limited Speed Safety Function."""

    name = "Safe Limited Speed {i}"

    command: FSoEDictionaryItemInputOutput = safety_field(
        uid="FSOE_SLS_CMD_{i}", display_name="Command"
    )
    velocity_limit: SafetyParameter = safety_field(
        uid="FSOE_SLS_VELOCITY_LIMIT_{i}", display_name="Limit"
    )
    error_reaction: SafetyParameter = safety_field(
        uid="FSOE_SLS_ERROR_REACTION_{i}", display_name="Error Reaction"
    )


@dataclass()
class SSRFunction(SafetyFunction):
    """Safe Speed Range Safety Function."""

    name = "Safe Speed Range {i}"

    command: FSoEDictionaryItemInputOutput = safety_field(
        uid="FSOE_SSR_COMMAND_{i}", display_name="Command"
    )
    upper_limit: SafetyParameter = safety_field(
        uid="FSOE_SSR_UPPER_LIMIT_{i}", display_name="Upper Limit"
    )
    lower_limit: SafetyParameter = safety_field(
        uid="FSOE_SSR_LOWER_LIMIT_{i}", display_name="Lower Limit"
    )
    error_reaction: SafetyParameter = safety_field(
        uid="FSOE_SSR_ERROR_REACTION_{i}", display_name="Error Reaction"
    )


@dataclass()
class SLPFunction(SafetyFunction):
    """Safe Limited Speed Safety Function."""

    name = "Safe Limited Position {i}"

    command: FSoEDictionaryItemInputOutput = safety_field(
        uid="FSOE_SLP_COMMAND_{i}", display_name="Command"
    )
    upper_limit: SafetyParameter = safety_field(
        uid="FSOE_SLP_UPPER_LIMIT_{i}", display_name="Upper Limit"
    )
    lower_limit: SafetyParameter = safety_field(
        uid="FSOE_SLP_LOWER_LIMIT_{i}", display_name="Lower Limit"
    )
    error_reaction: SafetyParameter = safety_field(
        uid="FSOE_SLP_ERROR_REACTION_{i}", display_name="Error Reaction"
    )


@dataclass()
class SDIFunction(SafetyFunction):
    """Safe Direction Safety Function."""
    name = "Safe Direction"

    command_positive: FSoEDictionaryItemInputOutput = safety_field(
        uid="FSOE_SDI_P", display_name="Command Positive"
    )
    command_negative: FSoEDictionaryItemInputOutput = safety_field(
        uid="FSOE_SDI_N", display_name="Command Negative"
    )
    pos_zero_window: SafetyParameter = safety_field(
        uid="FSOE_SDI_POS_ZERO_WINDOW", display_name="Position Zero Window"
    )

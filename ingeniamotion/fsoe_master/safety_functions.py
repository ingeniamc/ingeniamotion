# ruff: noqa: ERA001, PERF203
import dataclasses
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

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


def safety_field(uid: str, name: str):  # type: ignore[no-untyped-def]
    """Create a dataclass field with metadata for safety functions."""
    return dataclasses.field(metadata={"uid": uid, "name": name})


@dataclass()
class SafetyFunction:
    """Base class for Safety Functions.

    Wraps input/output items and parameters used by the FSoE Master handler.
    """

    io: tuple["FSoEDictionaryItem", ...]
    parameters: tuple[SafetyParameter, ...]

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
        cls, handler: "FSoEMasterHandler", instance_i: Optional[int] = None
    ) -> Iterator["SafetyFunction"]:
        ios: dict[dataclasses.Field[Any], FSoEDictionaryItem] = {}
        parameters: dict[dataclasses.Field[Any], FSoEDictionaryItem] = {}
        for field in dataclasses.fields(cls):
            if "uid" not in field.metadata:
                continue
            uid = field.metadata["uid"]
            if instance_i:
                uid = uid.format(i=instance_i)

            if field.type == FSoEDictionaryItemInputOutput:
                ios[field] = cls._get_required_input_output(handler, uid)
            elif field.type == FSoEDictionaryItemInput:
                ios[field] = cls._get_required_input(handler, uid)
            elif field.type == SafetyParameter:
                parameters[field] = cls._get_required_parameter(handler, uid)

        yield cls(
            io=tuple(ios.values()),  # TODO Convert to dict
            parameters=tuple(parameters.values()),
            **{field.name: ios[field] for field, io in ios.items()},
            **{field.name: parameters[field] for field, parameter in parameters.items()},
        )

    @classmethod
    def _explore_instances(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        """Explore instances of the safety function.

        Yields:
            int: An increasing integer starting from 1, representing the instance index.
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
                yield from cls._create_instance(handler, instance_i=i)
                i += 1
        except KeyError:
            return

    @classmethod
    def _get_required_input_output(
        cls, hander: "FSoEMasterHandler", uid: str
    ) -> FSoEDictionaryItemInputOutput:
        """Get the required input/output item from the handler's dictionary.

        Raises:
            KeyError: if the item is not found.
            TypeError: if the item is not of type FSoEDictionaryItemInputOutput.

        Returns:
            FSoEDictionaryItemInputOutput: The required input/output item.
        """
        item = hander.dictionary.name_map.get(uid)
        if item is None:
            raise KeyError(f"Dictionary item {uid} not found in the handler's dictionary")
        if not isinstance(item, FSoEDictionaryItemInputOutput):
            raise TypeError(
                f"Expected DictionaryItemInputOutput {uid} on the safe dictionary, got {type(item)}"
            )
        return item

    @classmethod
    def _get_required_input(cls, handler: "FSoEMasterHandler", uid: str) -> FSoEDictionaryItemInput:
        """Get the required input item from the handler's dictionary.

        Raises:
            KeyError: if the item is not found.
            TypeError: if the item is not of type FSoEDictionaryItemInput.

        Returns:
            FSoEDictionaryItemInput: The required input item.
        """
        item = handler.dictionary.name_map.get(uid)
        if item is None:
            raise KeyError(f"Dictionary item {uid} not found in the handler's dictionary")
        if not isinstance(item, FSoEDictionaryItemInput):
            raise TypeError(
                f"Expected DictionaryItemInput {uid} on the safe dictionary, got {type(item)}"
            )
        return item

    @classmethod
    def _get_required_parameter(cls, handler: "FSoEMasterHandler", uid: str) -> SafetyParameter:
        """Get the required parameter from the handler's safety parameters.

        Raises:
             KeyError: if the parameter is not found.

        Returns:
                SafetyParameter: The required safety parameter.
        """
        if uid not in handler.safety_parameters:
            raise KeyError(f"Safety parameter {uid} not found in the handler's safety parameters")
        return handler.safety_parameters[uid]


@dataclass()
class STOFunction(SafetyFunction):
    """Safe Torque Off Safety Function."""

    COMMAND_UID = "FSOE_STO"

    command: FSoEDictionaryItemInputOutput = safety_field(uid=COMMAND_UID, name="Command")


@dataclass()
class SS1Function(SafetyFunction):
    """Safe Stop 1 Safety Function."""

    COMMAND_UID = "FSOE_SS1_{i}"

    command: FSoEDictionaryItemInputOutput = safety_field(uid=COMMAND_UID, name="Command")
    time_to_sto: SafetyParameter = safety_field(uid="FSOE_SS1_TIME_TO_STO_{i}", name="Time to STO")


@dataclass()
class SafeInputsFunction(SafetyFunction):
    """Safe Inputs Safety Function."""

    SAFE_INPUTS_UID = "FSOE_SAFE_INPUTS_VALUE"
    value: FSoEDictionaryItemInput = safety_field(uid=SAFE_INPUTS_UID, name="Value")
    map: SafetyParameter = safety_field(uid="FSOE_SAFE_INPUTS_MAP", name="Map")


@dataclass()
class SOSFunction(SafetyFunction):
    """Safe Operation Stop Safety Function."""

    command: FSoEDictionaryItemInputOutput = safety_field(uid="FSOE_SOS_{i}", name="Command")
    position_zero_window: SafetyParameter = safety_field(
        uid="FSOE_SOS_POS_ZERO_WINDOW_{i}", name="Position Zero Window"
    )
    velocity_zero_window: SafetyParameter = safety_field(
        uid="FSOE_SOS_VEL_ZERO_WINDOW_{i}", name="Velocity Zero Window"
    )


@dataclass()
class SS2Function(SafetyFunction):
    """Safe Stop 2 Safety Function."""

    command: FSoEDictionaryItemInputOutput = safety_field(uid="FSOE_SS2_{i}", name="Command")
    time_to_sos: SafetyParameter = safety_field(uid="FSOE_SS2_TIME_TO_SOS_{i}", name="Time to SOS")
    deceleration_limit: SafetyParameter = safety_field(
        uid="FSOE_SS2_DEC_LIMIT_{i}", name="Deceleration Limit"
    )
    time_delay_deceleration_limit: SafetyParameter = safety_field(
        uid="FSOE_SS2_TIME_DELAY_DEC_{i}", name="Time Delay Deceleration Limit"
    )
    error_reaction: SafetyParameter = safety_field(
        uid="FSOE_SS2_ERROR_REACTION_{i}", name="Error Reaction"
    )


@dataclass()
class SOutFunction(SafetyFunction):
    """Safe Output Safety Function."""

    command: FSoEDictionaryItemInputOutput = safety_field(uid="FSOE_SBC_OUT", name="Command")
    time_delay: SafetyParameter = safety_field(uid="FSOE_SBC_TIME_DELAY", name="Time Delay")


@dataclass()
class SPFunction(SafetyFunction):
    """Safe Position Safety Function."""

    value: FSoEDictionaryItemInput = safety_field(uid="FSOE_SAFE_POSITION", name="Value")
    tolerance: SafetyParameter = safety_field(uid="FSOE_POSITION_TOLERANCE", name="Tolerance")


@dataclass()
class SVFunction(SafetyFunction):
    """Safe Velocity Safety Function."""

    value: FSoEDictionaryItemInput = safety_field("FSOE_SAFE_VELOCITY", name="Value")


@dataclass()
class SafeHomingFunction(SafetyFunction):
    """Safe Homing Safety Function."""

    command: FSoEDictionaryItemInputOutput = safety_field(uid="FSOE_SAFE_HOMING", name="Command")
    homing_ref: SafetyParameter = safety_field(uid="FSOE_SAFE_HOMING_REFERENCE", name="Reference")


@dataclass()
class SLSFunction(SafetyFunction):
    """Safe Limited Speed Safety Function."""

    command: FSoEDictionaryItemInputOutput = safety_field(uid="FSOE_SLS_CMD_{i}", name="Command")
    velocity_limit: SafetyParameter = safety_field(uid="FSOE_SLS_VELOCITY_LIMIT_{i}", name="Limit")
    error_reaction: SafetyParameter = safety_field(
        uid="FSOE_SLS_ERROR_REACTION_{i}", name="Error Reaction"
    )


@dataclass()
class SSRFunction(SafetyFunction):
    """Safe Speed Range Safety Function."""

    command: FSoEDictionaryItemInputOutput = safety_field(
        uid="FSOE_SSR_COMMAND_{i}", name="Command"
    )
    upper_limit: SafetyParameter = safety_field(uid="FSOE_SSR_UPPER_LIMIT_{i}", name="Upper Limit")
    lower_limit: SafetyParameter = safety_field(uid="FSOE_SSR_LOWER_LIMIT_{i}", name="Lower Limit")
    error_reaction: SafetyParameter = safety_field(
        uid="FSOE_SSR_ERROR_REACTION_{i}", name="Error Reaction"
    )


@dataclass()
class SLPFunction(SafetyFunction):
    """Safe Limited Speed Safety Function."""

    command: FSoEDictionaryItemInputOutput = safety_field(
        uid="FSOE_SLP_COMMAND_{i}", name="Command"
    )
    upper_limit: SafetyParameter = safety_field(uid="FSOE_SLP_UPPER_LIMIT_{i}", name="Upper Limit")
    lower_limit: SafetyParameter = safety_field(uid="FSOE_SLP_LOWER_LIMIT_{i}", name="Lower Limit")
    error_reaction: SafetyParameter = safety_field(
        uid="FSOE_SLP_ERROR_REACTION_{i}", name="Error Reaction"
    )

# ruff: noqa: ERA001, PERF203
import dataclasses
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from typing_extensions import override

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


def safety_field(uid: str, name: str) -> dataclasses.Field:
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
        yield from STOFunction.for_handler(handler)
        yield from SS1Function.for_handler(handler)
        yield from SafeInputsFunction.for_handler(handler)
        yield from SOSFunction.for_handler(handler)
        yield from SS2Function.for_handler(handler)
        yield from SOutFunction.for_handler(handler)
        yield from SPFunction.for_handler(handler)
        yield from SVFunction.for_handler(handler)
        yield from SafeHomingFunction.for_handler(handler)
        yield from SLSFunction.for_handler(handler)
        yield from SSRFunction.for_handler(handler)
        yield from SLPFunction.for_handler(handler)

    @classmethod
    def _create_instance(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        ios: dict[dataclasses.Field, FSoEDictionaryItem] = {}
        parameters: dict[dataclasses.Field, FSoEDictionaryItem] = {}
        for field in dataclasses.fields(cls):
            if field.type == FSoEDictionaryItemInputOutput:
                ios[field] = cls._get_required_input_output(handler, field.metadata["uid"])
            elif field.type == FSoEDictionaryItemInput:
                ios[field] = cls._get_required_input(handler, field.metadata["uid"])
            elif field.type == SafetyParameter:
                parameters[field] = cls._get_required_parameter(handler, field.metadata["uid"])

        yield cls(
            io=tuple(ios.values()),  # TODO Convert to dict
            parameters=tuple(parameters.values()),
            **{field.name: ios[field] for field, io in ios.items()},
            **{field.name: parameters[field] for field, parameter in parameters.items()},
        )

    @classmethod
    def _explore_instances(cls) -> Iterator[int]:
        """Explore instances of the safety function.

        Yields:
            int: An increasing integer starting from 1, representing the instance index.
        """
        i = 1
        while True:
            yield i
            i += 1

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
    def _get_required_input(
        cls, handler: "FSoEMasterHandler", uid: str
    ) -> "FSoEDictionaryItemInput":
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

    command: FSoEDictionaryItemInputOutput = safety_field(uid="FSOE_STO", name="Command")

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["STOFunction"]:
        yield from cls._create_instance(handler)


@dataclass()
class SS1Function(SafetyFunction):
    """Safe Stop 1 Safety Function."""

    COMMAND_UID = "FSOE_SS1_{i}"

    TIME_TO_STO_UID = "FSOE_SS1_TIME_TO_STO_{i}"

    command: FSoEDictionaryItemInputOutput
    time_to_sto: SafetyParameter

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SS1Function"]:
        for i in cls._explore_instances():
            try:
                ss1_command = cls._get_required_input_output(handler, cls.COMMAND_UID.format(i=i))
                time_to_sto = cls._get_required_parameter(handler, cls.TIME_TO_STO_UID.format(i=i))
                yield cls(
                    command=ss1_command,
                    time_to_sto=time_to_sto,
                    io=(ss1_command,),
                    parameters=(time_to_sto,),
                )
            except KeyError:  # noqa: PERF203
                break


@dataclass()
class SafeInputsFunction(SafetyFunction):
    """Safe Inputs Safety Function."""

    SAFE_INPUTS_UID = "FSOE_SAFE_INPUTS_VALUE"

    INPUTS_MAP_UID = "FSOE_SAFE_INPUTS_MAP"

    value: "FSoEDictionaryItemInput"
    map: SafetyParameter

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SafeInputsFunction"]:
        safe_inputs = cls._get_required_input(handler, cls.SAFE_INPUTS_UID)
        inputs_map = cls._get_required_parameter(handler, cls.INPUTS_MAP_UID)
        yield cls(value=safe_inputs, map=inputs_map, io=(safe_inputs,), parameters=(inputs_map,))


@dataclass()
class SOSFunction(SafetyFunction):
    """Safe Operation Stop Safety Function."""

    COMMAND_UID = "FSOE_SOS_{i}"
    POSITION_ZERO_WINDOW_UID = "FSOE_SOS_POS_ZERO_WINDOW_{i}"
    VELOCITY_ZERO_WINDOW_UID = "FSOE_SOS_VEL_ZERO_WINDOW_{i}"

    command: FSoEDictionaryItemInputOutput
    position_zero_window: SafetyParameter
    velocity_zero_window: SafetyParameter

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SOSFunction"]:
        for i in cls._explore_instances():
            try:
                command = cls._get_required_input_output(handler, cls.COMMAND_UID.format(i=i))
                position_zero_window = cls._get_required_parameter(
                    handler, cls.POSITION_ZERO_WINDOW_UID.format(i=i)
                )
                velocity_zero_window = cls._get_required_parameter(
                    handler, cls.VELOCITY_ZERO_WINDOW_UID.format(i=i)
                )
                yield cls(
                    command=command,
                    position_zero_window=position_zero_window,
                    velocity_zero_window=velocity_zero_window,
                    io=(command,),
                    parameters=(position_zero_window, velocity_zero_window),
                )
            except KeyError:  # noqa: PERF203
                break


@dataclass()
class SS2Function(SafetyFunction):
    """Safe Stop 2 Safety Function."""

    COMMAND_UID = "FSOE_SS2_{i}"
    TIME_TO_SOS_UID = "FSOE_SS2_TIME_TO_SOS_{i}"
    DECELERATION_LIMIT_UID = "FSOE_SS2_DEC_LIMIT_{i}"
    TIME_DELAY_DECELERATION_LIMIT_UID = "FSOE_SS2_TIME_DELAY_DEC_{i}"
    ERROR_REACTION_UID = "FSOE_SS2_ERROR_REACTION_{i}"

    command: FSoEDictionaryItemInputOutput
    time_to_sos: "SafetyParameter"
    deceleration_limit: "SafetyParameter"
    time_delay_deceleration_limit: "SafetyParameter"
    error_reaction: "SafetyParameter"

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        for i in cls._explore_instances():
            try:
                command = cls._get_required_input_output(handler, cls.COMMAND_UID.format(i=i))
                time_to_sos = cls._get_required_parameter(handler, cls.TIME_TO_SOS_UID.format(i=i))
                deceleration_limit = cls._get_required_parameter(
                    handler, cls.DECELERATION_LIMIT_UID.format(i=i)
                )
                time_delay_deceleration_limit = cls._get_required_parameter(
                    handler, cls.TIME_DELAY_DECELERATION_LIMIT_UID.format(i=i)
                )
                error_reaction = cls._get_required_parameter(
                    handler, cls.ERROR_REACTION_UID.format(i=i)
                )
                yield cls(
                    command=command,
                    time_to_sos=time_to_sos,
                    deceleration_limit=deceleration_limit,
                    time_delay_deceleration_limit=time_delay_deceleration_limit,
                    error_reaction=error_reaction,
                    io=(command,),
                    parameters=(
                        time_to_sos,
                        deceleration_limit,
                        time_delay_deceleration_limit,
                        error_reaction,
                    ),
                )
            except KeyError:  # noqa: PERF203
                break


@dataclass()
class SOutFunction(SafetyFunction):
    """Safe Output Safety Function."""

    COMMAND_UID = "FSOE_SBC"
    TIME_DELAY_UID = "FSOE_SBC_BRAKE_TIME_DELAY"

    command: FSoEDictionaryItemInputOutput
    time_delay: SafetyParameter

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        for _ in cls._explore_instances():
            try:
                command = cls._get_required_input_output(handler, cls.COMMAND_UID)
                time_delay = cls._get_required_parameter(handler, cls.TIME_DELAY_UID)

                yield cls(
                    command=command,
                    time_delay=time_delay,
                    io=(command,),
                    parameters=(time_delay,),
                )
            except KeyError:  # noqa: PERF203
                break


@dataclass()
class SPFunction(SafetyFunction):
    """Safe Position Safety Function."""

    ACTUAL_VALUE_UID = "FSOE_SAFE_POSITION"
    TOLERANCE_UID = "FSOE_POSITION_TOLERANCE"

    value: FSoEDictionaryItemInput
    tolerance: SafetyParameter

    @classmethod
    @override
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SPFunction"]:
        try:
            value = cls._get_required_input(handler, cls.ACTUAL_VALUE_UID)
            tolerance = cls._get_required_parameter(handler, cls.TOLERANCE_UID)
            yield cls(value=value, tolerance=tolerance, io=(value,), parameters=(tolerance,))
        except KeyError:  # noqa: PERF203
            return


@dataclass()
class SVFunction(SafetyFunction):
    """Safe Velocity Safety Function."""

    ACTUAL_VALUE_UID = "FSOE_SAFE_VELOCITY"

    value: FSoEDictionaryItemInput

    @classmethod
    @override
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SVFunction"]:
        try:
            value = cls._get_required_input(handler, cls.ACTUAL_VALUE_UID)
            yield cls(value=value, io=(value,), parameters=())
        except KeyError:
            return


@dataclass()
class SafeHomingFunction(SafetyFunction):
    """Safe Homing Safety Function."""

    COMMAND_UID = "FSOE_SAFE_HOMING"
    HOMING_REF_UID = "FSOE_SAFE_HOMING_REFERENCE"

    command: FSoEDictionaryItemInputOutput
    homing_ref: SafetyParameter

    @classmethod
    @override
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SafeHomingFunction"]:
        try:
            command = cls._get_required_input_output(handler, cls.COMMAND_UID)
            homing_ref = cls._get_required_parameter(handler, cls.HOMING_REF_UID)
            yield cls(
                command=command, homing_ref=homing_ref, io=(command,), parameters=(homing_ref,)
            )
        except KeyError:
            return


@dataclass()
class SLSFunction(SafetyFunction):
    """Safe Limited Speed Safety Function."""

    COMMAND_UID = "FSOE_SLS_CMD_{i}"
    VELOCITY_LIMIT_UID = "FSOE_SLS_VELOCITY_LIMIT_{i}"
    ERROR_REACTION_UID = "FSOE_SLS_ERROR_REACTION_{i}"

    command: FSoEDictionaryItemInputOutput
    speed_limit: SafetyParameter
    error_reaction: SafetyParameter

    @classmethod
    @override
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SLSFunction"]:
        for i in cls._explore_instances():
            try:
                command = cls._get_required_input_output(handler, cls.COMMAND_UID.format(i=i))
                velocity_limit = cls._get_required_parameter(
                    handler, cls.VELOCITY_LIMIT_UID.format(i=i)
                )
                error_reaction = cls._get_required_parameter(
                    handler, cls.ERROR_REACTION_UID.format(i=i)
                )
                yield cls(
                    command=command,
                    speed_limit=velocity_limit,
                    error_reaction=error_reaction,
                    io=(command,),
                    parameters=(velocity_limit, error_reaction),
                )
            except KeyError:
                return


@dataclass()
class SSRFunction(SafetyFunction):
    """Safe Speed Range Safety Function."""

    COMMAND_UID = "FSOE_SSR_COMMAND_{i}"
    UPPER_LIMIT_UID = "FSOE_SSR_UPPER_LIMIT_{i}"
    LOWER_LIMIT_UID = "FSOE_SSR_LOWER_LIMIT_{i}"
    ERROR_REACTION_UID = "FSOE_SSR_ERROR_REACTION_{i}"

    command: FSoEDictionaryItemInputOutput
    upper_limit: SafetyParameter
    lower_limit: SafetyParameter
    error_reaction: SafetyParameter

    @classmethod
    @override
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        for i in cls._explore_instances():
            try:
                command = cls._get_required_input_output(handler, cls.COMMAND_UID.format(i=i))
                upper_limit = cls._get_required_parameter(handler, cls.UPPER_LIMIT_UID.format(i=i))
                lower_limit = cls._get_required_parameter(handler, cls.LOWER_LIMIT_UID.format(i=i))
                error_reaction = cls._get_required_parameter(
                    handler, cls.ERROR_REACTION_UID.format(i=i)
                )
                yield cls(
                    command=command,
                    upper_limit=upper_limit,
                    lower_limit=lower_limit,
                    error_reaction=error_reaction,
                    io=(command,),
                    parameters=(upper_limit, lower_limit, error_reaction),
                )
            except KeyError:
                return


@dataclass()
class SLPFunction(SafetyFunction):
    """Safe Limited Speed Safety Function."""

    COMMAND_UID = "FSOE_SLP_COMMAND_{i}"
    UPPER_LIMIT_UID = "FSOE_SLP_UPPER_LIMIT_{i}"
    LOWER_LIMIT_UID = "FSOE_SLP_LOWER_LIMIT_{i}"
    ERROR_REACTION_UID = "FSOE_SLP_ERROR_REACTION_{i}"

    command: FSoEDictionaryItemInputOutput
    upper_limit: SafetyParameter
    lower_limit: SafetyParameter
    error_reaction: SafetyParameter

    @classmethod
    @override
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        for i in cls._explore_instances():
            try:
                command = cls._get_required_input_output(handler, cls.COMMAND_UID.format(i=i))
                upper_limit = cls._get_required_parameter(handler, cls.UPPER_LIMIT_UID.format(i=i))
                lower_limit = cls._get_required_parameter(handler, cls.LOWER_LIMIT_UID.format(i=i))
                error_reaction = cls._get_required_parameter(
                    handler, cls.ERROR_REACTION_UID.format(i=i)
                )
                yield cls(
                    command=command,
                    upper_limit=upper_limit,
                    lower_limit=lower_limit,
                    error_reaction=error_reaction,
                    io=(command,),
                    parameters=(upper_limit, lower_limit, error_reaction),
                )
            except KeyError:
                return

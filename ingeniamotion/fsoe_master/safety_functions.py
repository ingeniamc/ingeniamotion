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
    "SafetyFunction",
    "STOFunction",
    "SS1Function",
    "SafeInputsFunction",
]


@dataclass()
class SafetyFunction:
    """Base class for Safety Functions.

    Wraps input/output items and parameters used by the FSoE Master handler.
    """

    io: tuple["FSoEDictionaryItem", ...]
    parameters: tuple[SafetyParameter, ...]

    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        """Get the safety function instances for a given FSoE master handler."""
        yield from STOFunction.for_handler(handler)
        yield from SS1Function.for_handler(handler)
        yield from SafeInputsFunction.for_handler(handler)
        yield from SOSFunction.for_handler(handler)
        yield from SS2Function.for_handler(handler)
        yield from SOutFunction.for_handler(handler)
        yield from SPFunction.for_handler(handler)
        yield from SPFunction.for_handler(handler)
        yield from SVFunction.for_handler(handler)

    @classmethod
    def _explore_instances(cls) -> Iterator[int]:
        """Explore instances of the safety function."""
        i = 1
        while True:
            try:
                yield i
            except KeyError:
                # If a KeyError is raised, it means the instance does not exist
                break
            i += 1

    @classmethod
    def _get_required_input_output(
        cls, hander: "FSoEMasterHandler", uid: str
    ) -> "FSoEDictionaryItemInputOutput":
        """Get the required input/output item from the handler's dictionary."""
        item = hander.dictionary.name_map.get(uid)
        if not isinstance(item, FSoEDictionaryItemInputOutput):
            raise TypeError(
                f"Expected DictionaryItemInputOutput {uid} on the safe dictionary, got {type(item)}"
            )
        return item

    @classmethod
    def _get_required_input(
        cls, handler: "FSoEMasterHandler", uid: str
    ) -> "FSoEDictionaryItemInput":
        """Get the required input item from the handler's dictionary."""
        item = handler.dictionary.name_map.get(uid)
        if not isinstance(item, FSoEDictionaryItemInput):
            raise TypeError(
                f"Expected DictionaryItemInput {uid} on the safe dictionary, got {type(item)}"
            )
        return item

    @classmethod
    def _get_required_parameter(cls, handler: "FSoEMasterHandler", uid: str) -> SafetyParameter:
        """Get the required parameter from the handler's safety parameters."""
        if uid not in handler.safety_parameters:
            raise KeyError(f"Safety parameter {uid} not found in the handler's safety parameters")
        return handler.safety_parameters[uid]


@dataclass()
class STOFunction(SafetyFunction):
    """Safe Torque Off Safety Function."""

    COMMAND_UID = "FSOE_STO"

    command: "FSoEDictionaryItemInputOutput"

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["STOFunction"]:
        sto_command = cls._get_required_input_output(handler, cls.COMMAND_UID)
        yield cls(command=sto_command, io=(sto_command,), parameters=())


@dataclass()
class SS1Function(SafetyFunction):
    """Safe Stop 1 Safety Function."""

    COMMAND_UID = "FSOE_SS1_{i}"

    TIME_TO_STO_UID = "FSOE_SS1_TIME_TO_STO_{i}"

    command: "FSoEDictionaryItemInputOutput"
    time_to_sto: SafetyParameter

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SS1Function"]:
        for i in cls._explore_instances():
            ss1_command = cls._get_required_input_output(handler, cls.COMMAND_UID.format(i))
            time_to_sto = cls._get_required_parameter(handler, cls.TIME_TO_STO_UID.format(i))
            yield cls(
                command=ss1_command,
                time_to_sto=time_to_sto,
                io=(ss1_command,),
                parameters=(time_to_sto,),
            )


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

    command: "FSoEDictionaryItemInputOutput"
    position_zero_window: SafetyParameter
    velocity_zero_window: SafetyParameter

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SOSFunction"]:
        for i in cls._explore_instances():
            command = cls._get_required_input_output(handler, cls.COMMAND_UID.format(i))
            position_zero_window = cls._get_required_parameter(
                handler, cls.POSITION_ZERO_WINDOW_UID.format(i)
            )
            velocity_zero_window = cls._get_required_parameter(
                handler, cls.VELOCITY_ZERO_WINDOW_UID.format(i)
            )
            yield cls(
                command=command,
                position_zero_window=position_zero_window,
                velocity_zero_window=velocity_zero_window,
                io=(command,),
                parameters=(position_zero_window, velocity_zero_window),
            )


@dataclass()
class SS2Function(SafetyFunction):
    """Safe Stop 2 Safety Function."""

    COMMAND_UID = "FSOE_SS2_{i}"
    TIME_TO_SOS_UID = "FSOE_SS2_TIME_TO_SOS_{i}"
    TIME_TO_VELOCITY_ZERO_UID = "FSOE_SS2_TIME_FOR_VEL_ZERO_{i}"
    DECELERATION_LIMIT_UID = "FSOE_SS2_DEC_LIMIT_{i}"
    TIME_DELAY_DECELERATION_LIMIT_UID = "FSOE_SS2_TIME_DELAY_DEC_{i}"
    ERROR_REACTION_UID = "FSOE_SS2_ERROR_REACTION_{i}"

    command: "FSoEDictionaryItemInputOutput"
    time_to_sos: "SafetyParameter"
    time_to_velocity_zero: "SafetyParameter"
    deceleration_limit: "SafetyParameter"
    time_delay_deceleration_limit: "SafetyParameter"
    error_reaction: "SafetyParameter"

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        for i in cls._explore_instances():
            command = cls._get_required_input_output(handler, cls.COMMAND_UID.format(i))
            time_to_sos = cls._get_required_parameter(handler, cls.TIME_TO_SOS_UID.format(i))
            time_to_velocity_zero = cls._get_required_parameter(
                handler, cls.TIME_TO_VELOCITY_ZERO_UID.format(i)
            )
            deceleration_limit = cls._get_required_parameter(
                handler, cls.DECELERATION_LIMIT_UID.format(i)
            )
            time_delay_deceleration_limit = cls._get_required_parameter(
                handler, cls.TIME_DELAY_DECELERATION_LIMIT_UID.format()
            )
            error_reaction = cls._get_required_parameter(handler, cls.ERROR_REACTION_UID.format(i))
            yield cls(
                command=command,
                time_to_sos=time_to_sos,
                time_to_velocity_zero=time_to_velocity_zero,
                deceleration_limit=deceleration_limit,
                time_delay_deceleration_limit=time_delay_deceleration_limit,
                error_reaction=error_reaction,
                io=(command,),
                parameters=(
                    time_to_sos,
                    time_to_velocity_zero,
                    deceleration_limit,
                    time_delay_deceleration_limit,
                    error_reaction,
                ),
            )


@dataclass()
class SOutFunction(SafetyFunction):
    """Safe Output Safety Function."""

    COMMAND_UID = "FSOE_SBC"
    TIME_DELAY_UID = "FSOE_SBC_BRAKE_TIME_DELAY"

    command: FSoEDictionaryItemInputOutput
    time_delay: SafetyParameter

    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SafetyFunction"]:
        for _ in cls._explore_instances():
            command = cls._get_required_input_output(handler, cls.COMMAND_UID)
            time_delay = cls._get_required_parameter(handler, cls.TIME_DELAY_UID)

            yield cls(
                command=command,
                time_delay=time_delay,
                io=(command,),
                parameters=(time_delay,),
            )


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
        for _ in cls._explore_instances():
            value = cls._get_required_input(handler, cls.ACTUAL_VALUE_UID)
            tolerance = cls._get_required_parameter(handler, cls.TOLERANCE_UID)
            yield cls(value=value, tolerance=tolerance, io=(value,), parameters=(tolerance,))


@dataclass()
class SVFunction(SafetyFunction):
    """Safe Velocity Safety Function."""

    ACTUAL_VALUE_UID = "FSOE_SAFE_VELOCITY"

    value: FSoEDictionaryItemInput

    @classmethod
    @override
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SVFunction"]:
        for _ in cls._explore_instances():
            value = cls._get_required_input(handler, cls.ACTUAL_VALUE_UID)
            yield cls(value=value, io=(value,), parameters=())


@dataclass()
class SAFunction(SafetyFunction):
    """Safe Acceleration Safety Function."""

    ACTUAL_VALUE_UID = "FSOE_SAFE_ACCELERATION"

    value: FSoEDictionaryItemInput

    @classmethod
    @override
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SAFunction"]:
        for _ in cls._explore_instances():
            value = cls._get_required_input(handler, cls.ACTUAL_VALUE_UID)
            yield cls(value=value, io=(value,), parameters=())

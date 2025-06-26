from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

from typing_extensions import override

from ingeniamotion.fsoe_handler.fsoe import (
    FSoEDictionaryItem,
    FSoEDictionaryItemInput,
    FSoEDictionaryItemInputOutput,
)
from ingeniamotion.fsoe_handler.parameters import SafetyParameter

if TYPE_CHECKING:
    from ingeniamotion.fsoe_handler.handler import FSoEMasterHandler

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

    COMMAND_UID = "FSOE_SS1_1"

    TIME_TO_STO_UID = "FSOE_SS1_TIME_TO_STO_1"

    command: "FSoEDictionaryItemInputOutput"
    time_to_sto: SafetyParameter

    @override
    @classmethod
    def for_handler(cls, handler: "FSoEMasterHandler") -> Iterator["SS1Function"]:
        ss1_command = cls._get_required_input_output(handler, cls.COMMAND_UID)
        time_to_sto = cls._get_required_parameter(handler, cls.TIME_TO_STO_UID)
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

import threading
from collections.abc import Iterator
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Callable, Optional, TypeVar, Union, overload

import ingenialogger
from ingenialink import RegDtype
from ingenialink.canopen.register import CanopenRegister
from ingenialink.enums.register import RegCyclicType
from ingenialink.ethercat.dictionary import EthercatDictionaryV2
from ingenialink.ethercat.servo import EthercatServo
from typing_extensions import override

try:
    from fsoe_master.fsoe_master import (
        ApplicationParameter as FSoEApplicationParameter,
    )
    from fsoe_master.fsoe_master import (
        DataType as FSoEDataType,
    )
    from fsoe_master.fsoe_master import (
        Dictionary as FSoEDictionary,
    )
    from fsoe_master.fsoe_master import (
        DictionaryItem as FSoEDictionaryItem,
    )
    from fsoe_master.fsoe_master import (
        DictionaryItemInput as FSoEDictionaryItemInput,
    )
    from fsoe_master.fsoe_master import (
        DictionaryItemInputOutput as FSoEDictionaryItemInputOutput,
    )
    from fsoe_master.fsoe_master import (
        DictionaryItemOutput as FSoEDictionaryItemOutput,
    )
    from fsoe_master.fsoe_master import (
        DictionaryMap as FSoEDictionaryMap,
    )
    from fsoe_master.fsoe_master import (
        MasterHandler,
        StateData,
    )

    if TYPE_CHECKING:
        from fsoe_master.fsoe_master import State

except ImportError:
    FSOE_MASTER_INSTALLED = False
else:
    FSOE_MASTER_INSTALLED = True

from ingenialink.dictionary import Dictionary, DictionarySafetyModule, DictionaryV3
from ingenialink.pdo import PDOMap, PDOMapItem, RPDOMap, RPDOMapItem, TPDOMap, TPDOMapItem
from ingenialink.utils._utils import dtype_value

from ingeniamotion._utils import weak_lru
from ingeniamotion.enums import FSoEState
from ingeniamotion.exceptions import IMTimeoutError
from ingeniamotion.metaclass import DEFAULT_SERVO

if TYPE_CHECKING:
    from ingenialink.register import Register

    from ingeniamotion.motion_controller import MotionController


class SafetyParameter:
    """Safety Parameter.

    Represents a parameter that modifies how the safety application works.

    Base class is used for modules that use SRA CRC Check mechanism.
    """

    def __init__(self, register: "Register", servo: "EthercatServo"):
        self.__register = register
        self.__servo = servo

        self.__value = servo.read(register)

    def get(self) -> Union[int, float, str, bytes]:
        """Get the value of the safety parameter."""
        return self.__value

    def set(self, value: Union[int, float, str, bytes]) -> None:
        """Set the value of the safety parameter."""
        self.__servo.write(self.__register, value)
        self.__value = value


class SafetyParameterDirectValidation(SafetyParameter):
    """Safety Parameter with direct validation via FSoE.

    Safety Parameter that is validated directly via FSoE in application
     state instead of SRA CRC Check
    """

    def __init__(self, register: "Register", drive: "EthercatServo"):
        super().__init__(register, drive)

        self.fsoe_application_parameter = FSoEApplicationParameter(
            name=register.identifier,
            initial_value=self.get(),
            # https://novantamotion.atlassian.net/browse/INGK-1104
            n_bytes=dtype_value[register.dtype][0],
        )

    @override
    def set(self, value: Union[int, float, str, bytes]) -> None:
        super().set(value)
        self.fsoe_application_parameter.set(value)


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


SAFE_INSTANCE_TYPE = TypeVar("SAFE_INSTANCE_TYPE", bound="SafetyFunction")


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


@dataclass
class FSoEError:
    """FSoE Error descriptor."""

    servo: str
    transition_name: str
    description: str


class FSoEMasterHandler:
    """FSoE Master Handler.

    Args:
        slave_address: The servo's FSoE address.
        connection_id: The FSoE connection ID.
        watchdog_timeout: The FSoE master watchdog timeout in seconds.

    """

    FSOE_MANUF_SAFETY_ADDRESS = "FSOE_MANUF_SAFETY_ADDRESS"
    FSOE_DICTIONARY_CATEGORY = "FSOE"

    FSOE_RPDO_MAP_1_INDEX = 0x1700
    FSOE_TPDO_MAP_1_INDEX = 0x1B00

    DEFAULT_WATCHDOG_TIMEOUT_S = 1

    def __init__(
        self,
        servo: EthercatServo,
        *,
        safety_module: DictionarySafetyModule,
        slave_address: int,
        connection_id: int,
        watchdog_timeout: float = DEFAULT_WATCHDOG_TIMEOUT_S,
        report_error_callback: Callable[[str, str], None],
    ):
        if not FSOE_MASTER_INSTALLED:
            return
        self.__servo = servo

        # Parameters that are part of the system
        # UID as key
        self.safety_parameters: dict[str, SafetyParameter] = {}

        # Parameters that will be transmitted during the fsoe parameter state
        fsoe_application_parameters: list[FSoEApplicationParameter] = []

        if safety_module.uses_sra:
            raise NotImplementedError("Safety module with SRA is not available.")

        for app_parameter in safety_module.application_parameters:
            register = servo.dictionary.registers(subnode=1)[app_parameter.uid]

            if safety_module.uses_sra:
                sp = SafetyParameter(register, servo)
                # Pending add SRA CRC Parameter
                # https://novantamotion.atlassian.net/browse/INGM-621
            else:
                sp = SafetyParameterDirectValidation(register, servo)
                fsoe_application_parameters.append(sp.fsoe_application_parameter)

            self.safety_parameters[app_parameter.uid] = sp

        self.dictionary = self.create_safe_dictionary(servo)

        self.safety_functions = tuple(SafetyFunction.for_handler(self))

        self._master_handler = MasterHandler(
            dictionary=self.dictionary,
            slave_address=slave_address,
            connection_id=connection_id,
            watchdog_timeout_s=watchdog_timeout,
            application_parameters=fsoe_application_parameters,
            report_error_callback=report_error_callback,
            state_change_callback=self.__state_change_callback,
        )

        self.__map = PDUMaps(
            outputs=self._master_handler.master.dictionary_map,
            inputs=self._master_handler.slave.dictionary_map,
        )
        self._map_default_inputs()
        self._map_default_outputs()
        self.__safety_master_pdu = RPDOMap()
        self.__safety_master_pdu.map_register_index = self.FSOE_RPDO_MAP_1_INDEX
        self.__safety_slave_pdu = TPDOMap()
        self.__safety_slave_pdu.map_register_index = self.FSOE_TPDO_MAP_1_INDEX
        self.configure_pdo_maps()
        self.__running = False
        self.__state_is_data = threading.Event()

        # The saco slave might take a while to answer with a valid command
        # During it's initialization it will respond with 0's, that are ignored
        # To avoid triggering additional errors
        self.__in_initial_reset = False

    def _start(self) -> None:
        """Start the FSoE Master handler."""
        self.__in_initial_reset = True
        self.configure_pdo_maps()
        self.set_pdo_maps_to_slave()
        self._master_handler.start()
        self.__running = True

    def stop(self) -> None:
        """Stop the master handler."""
        self._master_handler.stop()
        self.__in_initial_reset = False
        self.__running = False

    def delete(self) -> None:
        """Delete the master handler."""
        self._master_handler.delete()

    @property
    def map(self) -> "PDUMaps":
        """Get the PDUMap used for the Safety PDUs."""
        return self.__map

    # TODO Set map

    def _map_default_outputs(self) -> None:
        """Configure the FSoE master handler's SafeOutputs."""
        # Phase 1 mapping
        # TODO Read from drive??, move to pdumapper?
        self.__map.append_output(self.get_function_instance(STOFunction).command)
        self.__map.append_output(self.get_function_instance(SS1Function).command)
        self.__map.append_output_padding(bits=6)

    def _map_default_inputs(self) -> None:
        """Configure the FSoE master handler's SafeInputs."""
        # Phase 1 mapping
        # TODO Read from drive??, move to pdumapper?
        self.__map.append_input(self.get_function_instance(STOFunction).command)
        self.__map.append_input(self.get_function_instance(SS1Function).command)
        self.__map.append_input_padding(bits=6)
        self.__map.append_input(self.get_function_instance(SS1Function).command)
        self.__map.append_input(self.get_function_instance(SafeInputsFunction).value)
        self.__map.append_input_padding(bits=6)

    def configure_pdo_maps(self) -> None:
        """Configure the PDOMaps used for the Safety PDUs according to the map."""
        self.__map.fill_rpdo_map(self.safety_master_pdu_map, self.dictionary)
        self.__map.fill_tpdo_map(self.safety_slave_pdu_map, self.dictionary)

    def set_pdo_maps_to_slave(self) -> None:
        """Set the PDOMaps to be used by the Safety PDUs to the slave."""
        self.__servo.set_pdo_map_to_slave(
            rpdo_maps=[self.safety_master_pdu_map], tpdo_maps=[self.safety_slave_pdu_map]
        )

    def remove_pdo_maps_from_slave(self) -> None:
        """Remove the PDOMaps used by the Safety PDUs from the slave."""
        self.__servo.remove_rpdo_map(self.safety_master_pdu_map)
        self.__servo.remove_tpdo_map(self.safety_slave_pdu_map)

    def get_request(self) -> None:
        """Set the FSoE master handler request to the Safety Master PDU PDOMap."""
        if not self.__running:
            self._start()
        self.safety_master_pdu_map.set_item_bytes(self._master_handler.get_request())

    def set_reply(self) -> None:
        """Get the FSoE slave response.

        It is extracted from the Safety Slave PDU PDOMap and set to the FSoE master handler.
        """
        reply = self.safety_slave_pdu_map.get_item_bytes()
        if self.__in_initial_reset:
            if reply[0] == 0:
                # Byte 0 of FSoE frame should always be the command
                # 0 is not a valid command
                return
            else:
                self.__in_initial_reset = False

        self._master_handler.set_reply(reply)

    @weak_lru()
    def safety_functions_by_type(self) -> dict[type[SafetyFunction], list[SafetyFunction]]:
        """Get a dictionary with the safety functions grouped by type."""
        return {
            type(sf): [
                sf_of_type
                for sf_of_type in self.safety_functions
                if isinstance(sf_of_type, type(sf))
            ]
            for sf in self.safety_functions
        }

    @overload  # type: ignore[misc]
    def get_function_instance(self, typ: type[SAFE_INSTANCE_TYPE]) -> SAFE_INSTANCE_TYPE: ...

    @weak_lru()
    def get_function_instance(
        self, typ: type[SAFE_INSTANCE_TYPE], instance: Optional[int] = None
    ) -> SAFE_INSTANCE_TYPE:
        """Get the instance of a safety function.

        Args:
            typ: The type of the safety function to get.
            instance: The index of the instance to get.
                If None, if there's a single instance, it returns it.
        """
        funcs = [func for func in self.safety_functions if isinstance(func, typ)]

        if isinstance(instance, int):
            # First instance is 1
            index = instance - 1
            if index < 0 or index >= len(funcs):
                raise IndexError(f"Master handler does not contain {typ.__name__} instance {instance}")
            return funcs[index]
        else:
            if len(funcs) != 1:
                raise ValueError(
                    f"Multiple {typ.__name__} instances found ({len(funcs)}). "
                    f"Specify the instance number."
                )
            return funcs[0]

    @weak_lru()
    def sto_function(self) -> STOFunction:
        """Get the Safe Torque Off function."""
        return self.get_function_instance(STOFunction)

    @weak_lru()
    def ss1_function(self) -> SS1Function:
        """Get the Safe Stop 1 function."""
        return self.get_function_instance(SS1Function)

    @weak_lru()
    def safe_inputs_function(self) -> SafeInputsFunction:
        """Get the Safe Inputs function."""
        return self.get_function_instance(SafeInputsFunction)

    def sto_deactivate(self) -> None:
        """Set the STO command to deactivate the STO."""
        self._master_handler.set_fail_safe(False)
        self.sto_function().command.set(True)

    def sto_activate(self) -> None:
        """Set the STO command to activate the STO."""
        self.sto_function().command.set(False)

    def ss1_deactivate(self) -> None:
        """Set the SS1 command to deactivate the SS1."""
        self._master_handler.set_fail_safe(False)
        self.ss1_function().command.set(True)

    def ss1_activate(self) -> None:
        """Set the SS1 command to activate the SS1."""
        self.ss1_function().command.set(False)

    def safe_inputs_value(self) -> bool:
        """Get the safe inputs register value."""
        safe_inputs_value = self.safe_inputs_function().value.get()
        if not isinstance(safe_inputs_value, bool):
            raise ValueError(f"Wrong value type. Expected type bool, got {type(safe_inputs_value)}")
        return safe_inputs_value

    def get_safety_address(self) -> int:
        """Get the FSoE slave address configured on the master.

        Returns:
            The FSoE slave address.
        """
        # https://novantamotion.atlassian.net/browse/INGK-1090
        value = self._master_handler.master.session.slave_address.value
        if not isinstance(value, int):
            raise TypeError("Unexpected type for slave address")
        return value

    def set_safety_address(self, address: int) -> None:
        """Set the drive's FSoE slave address to the master and the slave.

        Args:
            address: The address to be set.
        """
        self.__servo.write(self.FSOE_MANUF_SAFETY_ADDRESS, address)
        self._master_handler.set_slave_address(address)

    def is_sto_active(self) -> bool:
        """Check the STO state.

        Returns:
            True if the STO is active. False otherwise.

        """
        sto_command = self.sto_function().command.get()
        if not isinstance(sto_command, bool):
            raise ValueError(f"Wrong value type. Expected type bool, got {type(sto_command)}")
        return sto_command

    def __state_change_callback(self, state: "State") -> None:
        if state == StateData:
            self.__state_is_data.set()
        else:
            self.__state_is_data.clear()

    def wait_for_data_state(self, timeout: Optional[float] = None) -> None:
        """Wait the FSoE master handler to reach the Data state.

        Args:
            timeout : how many seconds to wait for the FSoE master to reach the
                Data state, if ``None`` it will wait forever.
                ``None`` by default.

        Raises:
            IMTimeoutError: If the Data state is not reached within the timeout.

        """
        if self.__state_is_data.wait(timeout=timeout) is False:
            raise IMTimeoutError("The FSoE Master did not reach the Data state")

    @classmethod
    def create_safe_dictionary(cls, servo: "EthercatServo") -> "FSoEDictionary":
        """Create a dictionary with the safe inputs and outputs.

        Returns:
            A Dictionary instance with the safe inputs and outputs.

        """
        dictionary = servo.dictionary
        if isinstance(dictionary, EthercatDictionaryV2):
            # Dictionary V2 only supports SaCo phase 1
            return cls._saco_phase_1_dictionary()
        if isinstance(dictionary, DictionaryV3):
            return cls._create_safe_dictionary_from_v3(dictionary)
        else:
            raise NotImplementedError

    @classmethod
    def _saco_phase_1_dictionary(cls) -> "FSoEDictionary":
        """Get the SaCo phase 1 dictionary instance."""
        sto_command_dict_item = FSoEDictionaryItemInputOutput(
            # Arbitrary key, could be removed
            # https://novantamotion.atlassian.net/browse/INGK-1112
            key=1,
            name=STOFunction.COMMAND_UID,
            data_type=FSoEDictionaryItem.DataTypes.BOOL,
            fail_safe_input_value=True,
        )
        ss1_command_dict_item = FSoEDictionaryItemInputOutput(
            key=2,
            name=SS1Function.COMMAND_UID,
            data_type=FSoEDictionaryItem.DataTypes.BOOL,
            fail_safe_input_value=True,
        )
        safe_input_dict_item = FSoEDictionaryItemInput(
            key=3,
            name=SafeInputsFunction.SAFE_INPUTS_UID,
            data_type=FSoEDictionaryItem.DataTypes.BOOL,
            fail_safe_value=False,
        )
        return FSoEDictionary(
            [
                sto_command_dict_item,
                ss1_command_dict_item,
                safe_input_dict_item,
            ]
        )

    @classmethod
    def _create_safe_dictionary_from_v3(cls, dictionary: "DictionaryV3") -> "FSoEDictionary":
        """Create a dictionary with the safe inputs and outputs from a DictionaryV3 instance.

        Args:
            dictionary: The DictionaryV3 instance.

        Returns:
            A FSOE Dictionary instance with the safe inputs and outputs.

        """
        items = []
        for register in dictionary.registers(subnode=1).values():
            if register.cat_id != cls.FSOE_DICTIONARY_CATEGORY:
                continue

            if not isinstance(register, CanopenRegister):
                # Type could be narrowed to EthercatRegister
                # After this bugfix:
                # https://novantamotion.atlassian.net/browse/INGK-1111
                raise TypeError

            identifier = register.identifier
            if identifier is None:
                continue

            if identifier.startswith(("FSOE_SLAVE_FRAME", "FSOE_MASTER_FRAME")):
                # Elements of the standard FSoE frame are not added to the safe data dictionary
                continue

            if register.pdo_access in (
                RegCyclicType.SAFETY_OUTPUT,
                RegCyclicType.SAFETY_INPUT_OUTPUT,
                RegCyclicType.SAFETY_INPUT,
            ):
                items.append(cls._create_fsoe_dict_item_from_reg(register))

        return FSoEDictionary(items)

    @classmethod
    def _create_fsoe_dict_item_from_reg(cls, reg: "CanopenRegister") -> "FSoEDictionaryItem":
        # Create an arbitrary unique numeric key for the item
        # https://novantamotion.atlassian.net/browse/INGK-1112
        key = reg.idx * 1000 + reg.subidx

        data_typ = cls._reg_dtype_to_fsoe_data_type(reg.dtype)

        if reg.pdo_access == RegCyclicType.SAFETY_INPUT:
            return FSoEDictionaryItemInput(
                key,
                name=reg.identifier,
                data_type=data_typ,
                fail_safe_value=cls.__fsoe_input_data_type_default(
                    data_typ, FSoEDictionaryItemInput
                ),
            )
        elif reg.pdo_access == RegCyclicType.SAFETY_INPUT_OUTPUT:
            return FSoEDictionaryItemInputOutput(
                key,
                name=reg.identifier,
                data_type=data_typ,
                fail_safe_input_value=cls.__fsoe_input_data_type_default(
                    data_typ, FSoEDictionaryItemInputOutput
                ),
            )
        elif reg.pdo_access == RegCyclicType.SAFETY_OUTPUT:
            return FSoEDictionaryItemOutput(
                key,
                name=reg.identifier,
                data_type=data_typ,
            )

        raise NotImplementedError

    @classmethod
    def _reg_dtype_to_fsoe_data_type(cls, typ: "RegDtype") -> "FSoEDataType":
        if typ == RegDtype.U8:
            return FSoEDataType.UINT8
        if typ == RegDtype.U16:
            return FSoEDataType.UINT16
        if typ == RegDtype.U32:
            return FSoEDataType.UINT32
        if typ == RegDtype.S8:
            return FSoEDataType.INT8
        if typ == RegDtype.S16:
            return FSoEDataType.INT16
        if typ == RegDtype.S32:
            return FSoEDataType.INT32
        if typ == RegDtype.FLOAT:
            return FSoEDataType.FLOAT
        if typ == RegDtype.BOOL:
            return FSoEDataType.BOOL

        raise NotImplementedError(f"Unsupported register data type for FSoE: {typ}")

    @classmethod
    def __fsoe_input_data_type_default(
        cls, data_typ: "FSoEDataType", item_type: type["FSoEDictionaryItem"]
    ) -> Union[int, float, str, bytes]:
        if data_typ == FSoEDataType.BOOL:
            if item_type == FSoEDictionaryItemInput:
                # Inputs are assumed to be Low on safe-state
                return False
            if item_type == FSoEDictionaryItemInputOutput:
                # Input-Outputs are typically safe commands,
                # whose safe-state is being active
                return True

        if data_typ in (
            FSoEDataType.UINT8,
            FSoEDataType.UINT16,
            FSoEDataType.UINT32,
            FSoEDataType.INT8,
            FSoEDataType.INT16,
            FSoEDataType.INT32,
            FSoEDataType.FLOAT,
        ):
            return 0

        raise NotImplementedError(f"Unsupported data type for FSoE: {data_typ}")

    @property
    def safety_master_pdu_map(self) -> RPDOMap:
        """The PDOMap used for the Safety Master PDU.

        The PDOMap might not be up to date, call configure_pdo_maps first
        """
        return self.__safety_master_pdu

    @property
    def safety_slave_pdu_map(self) -> TPDOMap:
        """The PDOMap used for the Safety Slave PDU.

        The PDOMap might not be up to date, call configure_pdo_maps first
        """
        return self.__safety_slave_pdu

    @property
    def state(self) -> FSoEState:
        """Get the FSoE master state."""
        return FSoEState(self._master_handler.state.id)

    @property
    def running(self) -> bool:
        """True if FSoE Master is started, else False."""
        return self.__running


@dataclass()
class FSoEFrameElements:
    command_uid: str
    _crcs_uid: str
    connection_id_uid: str

    def get_crc_uid(self, data_slot_i: int) -> str:
        """Get the CRC element name for the given data slot index."""
        # TODO: Handle case where data_slot_i is not in the dictionary
        return self._crcs_uid.format(i=data_slot_i)


MASTER_FRAME_ELEMENTS = FSoEFrameElements(
    command_uid="FSOE_MASTER_FRAME_ELEM_CMD",
    _crcs_uid="FSOE_MASTER_FRAME_ELEM_CRC{i}",
    connection_id_uid="FSOE_MASTER_FRAME_ELEM_CONNID",
)


SLAVE_FRAME_ELEMENTS = FSoEFrameElements(
    command_uid="FSOE_SLAVE_FRAME_ELEM_CMD",
    _crcs_uid="FSOE_SLAVE_FRAME_ELEM_CRC{i}",
    connection_id_uid="FSOE_SLAVE_FRAME_ELEM_CONNID",
)


class PDUMaps:
    """Helper class to configure the Safety PDU PDOMaps."""

    def __init__(
        self,
        outputs: "FSoEDictionaryMap",
        inputs: "FSoEDictionaryMap",
    ) -> None:
        self.outputs = outputs
        self.inputs = inputs

    @classmethod
    def empty(cls, dictionary: "FSoEDictionary") -> "PDUMaps":
        """Create an empty PDUMaps instance with the given dictionary."""
        return cls(
            outputs=FSoEDictionaryMap(
                dictionary,
                item_types_accepted={FSoEDictionaryItemOutput, FSoEDictionaryItemInputOutput},
            ),
            inputs=FSoEDictionaryMap(
                dictionary,
                item_types_accepted={FSoEDictionaryItemInput, FSoEDictionaryItemInputOutput},
            ),
        )

    @staticmethod
    def __get_safety_bytes_range_from_pdo_length(pdo_byte_lenght: int) -> tuple[int, ...]:
        """Get the range of bytes that belong to the safe data in a PDO map according to its length."""
        if pdo_byte_lenght < 6:
            raise ValueError("pdo_lenght must be at least 6")
        elif pdo_byte_lenght == 6:
            # Shortest PDOMap is 6 bytes, containing only one data byte
            return (1,)
        else:
            # The contains slots of 2 bytes of data

            # The total bytes of data is the Pdo map length
            # minus the 1 byte for the command and 2 bytes for the connection ID
            # divided by 4, since each data slot has 2 bytes of data and 2 bytes of CRC
            total_data_slots = (pdo_byte_lenght - 3) // 4
            return tuple(
                byt
                for slot_i in range(total_data_slots)
                for byt in (1 + slot_i * 4, 2 + slot_i * 4)
            )

    @classmethod
    def __fill_dictionary_map_from_pdo(
        cls, pdo_map: PDOMap, dictionary_map: "FSoEDictionaryMap"
    ) -> None:
        """Fill the dictionary map with items from the given PDOMap."""
        valid_bits = tuple(
            valid_bit
            for valid_byte in cls.__get_safety_bytes_range_from_pdo_length(
                pdo_map.data_length_bytes
            )
            for valid_bit in range(valid_byte * 8, (valid_byte + 1) * 8)
        )
        dictionary: "FSoEDictionary" = dictionary_map.dictionary
        position_bits = 0
        for item in pdo_map.items:
            if position_bits in valid_bits:
                # The item is a safe data item
                if item.register is None:
                    # Padding item
                    dictionary_map.add_padding(item.size_bits)
                else:
                    # Register item
                    register = item.register
                    dictionary_map.add(dictionary.name_map[register.identifier])

            position_bits += item.size_bits

    @classmethod
    def from_rpdo_tpdo(
        cls, rpdo: RPDOMap, tpdo: TPDOMap, dictionary: "FSoEDictionary"
    ) -> "PDUMaps":
        """Create a PDUMaps instance from the given RPDO and TPDO maps."""
        pdu_maps = cls.empty(dictionary)
        cls.__fill_dictionary_map_from_pdo(rpdo, pdu_maps.outputs)
        cls.__fill_dictionary_map_from_pdo(tpdo, pdu_maps.inputs)

    def append_output(
        self, element: Union[FSoEDictionaryItemOutput, FSoEDictionaryItemInputOutput]
    ) -> None:
        """Map an output element to the end of the Safety Master PDU."""
        self.outputs.add(element)

    def append_output_padding(self, bits: int) -> None:
        """Add padding to the end of the Safety Master PDU."""
        self.outputs.add_padding(bits=bits)

    def append_input(
        self, element: Union[FSoEDictionaryItemInput, FSoEDictionaryItemInputOutput]
    ) -> None:
        """Map an input element to the end of the Safety Slave PDU."""
        self.inputs.add(element)

    def append_input_padding(self, bits: int) -> None:
        """Add padding to the end of the Safety Slave PDU."""
        self.inputs.add_padding(bits=bits)

    # TODO create functions to intelligently add inputs and outputs
    #  Or create a PDUMaps from a set of inputs and outputs or complete safety functions
    # TODO Add rule validation to the PDUMaps. STO Must be first element

    def _create_rpdo_item(
        self,
        servo_dictionary: "Dictionary",
        uid: str,
        item_type: type[PDOMapItem],
    ) -> PDOMapItem:
        reg = servo_dictionary.get_register(uid)
        if not isinstance(reg, CanopenRegister):
            # Type could be narrowed to EthercatRegister
            # After this bugfix:
            # https://novantamotion.atlassian.net/browse/INGK-1111
            raise TypeError
        return item_type(reg)

        # TODO PUSH FIX and PR OF I/O and RX/TX on ingenialink

    def __fill_pdo_map(
        self,
        dict_map: "FSoEDictionaryMap",
        servo_dictionary: "Dictionary",
        pdo_map: PDOMap,
        pdo_item_type: type[PDOMapItem],
        frame_elements: FSoEFrameElements,
    ) -> None:
        # Remove any existing items in the PDOMap
        pdo_map.items.clear()

        # Initial FSoE command
        pdo_map.add_item(
            self._create_rpdo_item(servo_dictionary, frame_elements.command_uid, pdo_item_type)
        )

        data_slot_i = 0

        # The minimum bits for the initial data slot is 8 bits
        slot_bit_maximum = 8

        for item in dict_map:
            if slot_bit_maximum == 8 and item.position_bits + item.bits >= slot_bit_maximum:
                # Since there's enough data to fill the initial slot of 8 bits,
                # it will be of 16 bits instead
                slot_bit_maximum = 16

            if item.position_bits >= slot_bit_maximum:
                # This item must go in the next data slot
                # Add a CRC item, and update to the next data slot
                pdo_map.add_item(
                    self._create_rpdo_item(
                        servo_dictionary, frame_elements.get_crc_uid(data_slot_i), pdo_item_type
                    )
                )
                data_slot_i += 1
                slot_bit_maximum += 16

            if item.position_bits + item.bits <= slot_bit_maximum:
                # The item fits in the current slot, add it
                if item.item is None:
                    # Padding item
                    pdo_map.add_item(RPDOMapItem(size_bits=item.bits))
                else:
                    # I/O item
                    pdo_map.add_item(
                        self._create_rpdo_item(servo_dictionary, item.item.name, pdo_item_type)
                    )
            else:
                # The item must go in the current slot, and on the next one
                # Have a virtual padding with the remaining bits
                # As described on ETG5120 Section 5.3.3
                raise NotImplementedError  # TODO

        # Last CRC
        pdo_map.add_item(
            self._create_rpdo_item(
                servo_dictionary, frame_elements.get_crc_uid(data_slot_i), pdo_item_type
            )
        )

        # Connection ID
        pdo_map.add_item(
            self._create_rpdo_item(
                servo_dictionary, frame_elements.connection_id_uid, pdo_item_type
            )
        )

    def fill_rpdo_map(self, rpdo_map: RPDOMap, servo_dictionary: "Dictionary") -> None:
        self.__fill_pdo_map(
            self.outputs,
            servo_dictionary=servo_dictionary,
            pdo_map=rpdo_map,
            pdo_item_type=RPDOMapItem,
            frame_elements=MASTER_FRAME_ELEMENTS,
        )

    def fill_tpdo_map(self, tpdo_map: TPDOMap, servo_dictionary: "Dictionary") -> None:
        """Create the TPDOMap used for the Safety Slave PDU."""
        self.__fill_pdo_map(
            self.inputs,
            servo_dictionary=servo_dictionary,
            pdo_map=tpdo_map,
            pdo_item_type=TPDOMapItem,
            frame_elements=SLAVE_FRAME_ELEMENTS,
        )


class FSoEMaster:
    """FSoE Master.

    Args:
        motion_controller: The MotionController instance.

    """

    __MDP_CONFIGURED_MODULE_1 = "MDP_CONFIGURED_MODULE_1"

    def __init__(self, motion_controller: "MotionController") -> None:
        self.logger = ingenialogger.get_logger(__name__)
        self.__mc = motion_controller
        self._handlers: dict[str, FSoEMasterHandler] = {}
        self.__next_connection_id = 1
        self._error_observers: list[Callable[[FSoEError], None]] = []
        self.__fsoe_configured = False

    def create_fsoe_master_handler(
        self,
        servo: str = DEFAULT_SERVO,
        fsoe_master_watchdog_timeout: float = FSoEMasterHandler.DEFAULT_WATCHDOG_TIMEOUT_S,
    ) -> FSoEMasterHandler:
        """Create an FSoE Master handler linked to a Safe servo drive.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            fsoe_master_watchdog_timeout: The FSoE master watchdog timeout in seconds.

        """
        node = self.__mc.servos[servo]
        if not isinstance(node, EthercatServo):
            raise TypeError("Functional Safety over Ethercat is only available for Ethercat servos")
        slave_address = self._get_safety_address_from_drive(servo)

        master_handler = FSoEMasterHandler(
            node,
            safety_module=self.__get_safety_module(servo=servo),
            slave_address=slave_address,
            connection_id=self.__next_connection_id,
            watchdog_timeout=fsoe_master_watchdog_timeout,
            report_error_callback=partial(self._notify_errors, servo=servo),
        )
        self._handlers[servo] = master_handler
        self.__next_connection_id += 1
        return master_handler

    def _get_safety_address_from_drive(self, servo: str = DEFAULT_SERVO) -> int:
        """Get the drive's FSoE slave address configured in the drive.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            The FSoE slave address.

        """
        value = self.__mc.communication.get_register(
            FSoEMasterHandler.FSOE_MANUF_SAFETY_ADDRESS, servo
        )
        if not isinstance(value, int):
            raise ValueError(f"Wrong safety address value type. Expected int, got {type(value)}")
        return value

    def configure_pdos(self, start_pdos: bool = False) -> None:
        """Configure the PDOs used for the Safety PDUs.

        Args:
            start_pdos: if ``True``, start the PDO exchange, if ``False``
                the PDO exchange should be started after. ``False`` by default.

        """
        self._set_pdo_maps_to_slaves()
        self._subscribe_to_pdo_thread_events()
        if start_pdos:
            self.__mc.capture.pdo.start_pdos()
        self.__fsoe_configured = True

    def stop_master(self, stop_pdos: bool = False) -> None:
        """Stop all the FSoE Master handlers.

        Args:
            stop_pdos: if ``True``, stop the PDO exchange. ``False`` by default.

        """
        for master_handler in self._handlers.values():
            if master_handler.running:
                master_handler.stop()
        if self.__fsoe_configured:
            self._unsubscribe_from_pdo_thread_events()
        else:
            self.logger.warning("FSoE master is already stopped")
        if stop_pdos:
            self.__mc.capture.pdo.stop_pdos()
            if self.__fsoe_configured:
                self._remove_pdo_maps_from_slaves()
        self.__fsoe_configured = False

    def sto_deactivate(self, servo: str = DEFAULT_SERVO) -> None:
        """Deactivate the Safety Torque Off.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.sto_deactivate()

    def sto_activate(self, servo: str = DEFAULT_SERVO) -> None:
        """Activate the Safety Torque Off.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.sto_activate()

    def ss1_deactivate(self, servo: str = DEFAULT_SERVO) -> None:
        """Deactivate the SS1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.ss1_deactivate()

    def ss1_activate(self, servo: str = DEFAULT_SERVO) -> None:
        """Activate the SS1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.ss1_activate()

    def get_safety_inputs_value(self, servo: str = DEFAULT_SERVO) -> bool:
        """Get a drive's safe inputs register value.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
           The safe inputs value.

        """
        master_handler = self._handlers[servo]
        return master_handler.safe_inputs_value()

    def get_safety_address(self, servo: str = DEFAULT_SERVO) -> int:
        """Get the drive's FSoE slave address.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            The FSoE slave address.

        """
        master_handler = self._handlers[servo]
        return master_handler.get_safety_address()

    def set_safety_address(self, address: int, servo: str = DEFAULT_SERVO) -> None:
        """Set the drive's FSoE slave address.

        Args:
            address: The address to be set.
            servo: servo alias to reference it. ``default`` by default.

        """
        master_handler = self._handlers[servo]
        return master_handler.set_safety_address(address)

    def __get_configured_module_ident_1(
        self, servo: str = DEFAULT_SERVO
    ) -> Union[int, float, str, bytes]:
        """Gets the configured Module Ident 1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            Configured Module Ident 1.
        """
        return self.__mc.communication.get_register(
            register=self.__MDP_CONFIGURED_MODULE_1, servo=servo, axis=0
        )

    def __get_safety_module(self, servo: str = DEFAULT_SERVO) -> DictionarySafetyModule:
        """Gets the configured Module Ident 1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            Safety module.

        Raises:
            NotImplementedError: if the safety module uses SRA.
        """
        drive = self.__mc._get_drive(servo)
        module_ident = int(self.__get_configured_module_ident_1(servo=servo))
        safety_module = drive.dictionary.get_safety_module(module_ident=module_ident)
        if safety_module.uses_sra:
            self.logger.warning("Safety module with SRA is not available.")
        return safety_module

    def check_sto_active(self, servo: str = DEFAULT_SERVO) -> bool:
        """Check if the STO is active in a given servo.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            True if the STO is active. False otherwise.

        """
        master_handler = self._handlers[servo]
        return master_handler.is_sto_active()

    def wait_for_state_data(
        self, servo: str = DEFAULT_SERVO, timeout: Optional[float] = None
    ) -> None:
        """Wait for an FSoE master handler to reach the Data state.

        Args:
            servo: servo alias to reference it. ``default`` by default.
            timeout : how many seconds to wait for the FSoE master to reach the
                Data state, if ``None`` it will wait forever.
                ``None`` by default.

        """
        master_handler = self._handlers[servo]
        master_handler.wait_for_data_state(timeout)

    def get_fsoe_master_state(self, servo: str = DEFAULT_SERVO) -> FSoEState:
        """Get the servo's FSoE master handler state.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            The servo's FSoE master handler state.

        """
        master_handler = self._handlers[servo]
        return master_handler.state

    def subscribe_to_errors(self, callback: Callable[[FSoEError], None]) -> None:
        """Subscribe to the FSoE errors.

        Args:
            callback: Subscribed callback function.

        """
        if callback in self._error_observers:
            return
        self._error_observers.append(callback)

    def unsubscribe_from_errors(self, callback: Callable[[FSoEError], None]) -> None:
        """Unsubscribe from the FSoE errors.

        Args:
            callback: Subscribed callback function.

        """
        if callback not in self._error_observers:
            return
        self._error_observers.remove(callback)

    def _notify_errors(self, transition_name: str, error_description: str, servo: str) -> None:
        """Notify subscribers when an FSoE error occurs.

        Args:
            transition_name: FSoE transition name.
            error_description: FSoE error description.
            servo: The servo alias.

        """
        for callback in self._error_observers:
            callback(FSoEError(servo, transition_name, error_description))

    def _delete_master_handler(self, servo: str = DEFAULT_SERVO) -> None:
        """Delete the master handler instance.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        """
        if servo not in self._handlers:
            return
        self._handlers[servo].delete()
        del self._handlers[servo]

    def _subscribe_to_pdo_thread_events(self) -> None:
        """Subscribe to the PDO thread events.

        This allows to send the Safety Master PDU and to retrieve the Safety Slave PDU.

        """
        self.__mc.capture.pdo.subscribe_to_send_process_data(self._get_request)
        self.__mc.capture.pdo.subscribe_to_receive_process_data(self._set_reply)
        self.__mc.capture.pdo.subscribe_to_exceptions(self._pdo_thread_exception_handler)

    def _unsubscribe_from_pdo_thread_events(self) -> None:
        """Unsubscribe from the PDO thread events."""
        self.__mc.capture.pdo.unsubscribe_to_send_process_data(self._get_request)
        self.__mc.capture.pdo.unsubscribe_to_receive_process_data(self._set_reply)
        self.__mc.capture.pdo.unsubscribe_to_exceptions(self._pdo_thread_exception_handler)

    def _set_pdo_maps_to_slaves(self) -> None:
        """Set the PDOMaps to be used by the Safety PDUs to the slaves."""
        for master_handler in self._handlers.values():
            master_handler.set_pdo_maps_to_slave()

    def _remove_pdo_maps_from_slaves(self) -> None:
        """Remove the PDOMaps used by the Safety PDUs from the slaves."""
        for master_handler in self._handlers.values():
            master_handler.remove_pdo_maps_from_slave()

    def _get_request(self) -> None:
        """Get the FSoE master handlers requests.

        Callback method to send the FSoE Master handlers requests to the
        corresponding FSoE slave.
        """
        for master_handler in self._handlers.values():
            master_handler.get_request()

    def _set_reply(self) -> None:
        """Set the FSoE Slaves responses.

        Callback method to provide the FSoE Slaves responses to their
        corresponding FSoE Master handler.
        """
        for master_handler in self._handlers.values():
            master_handler.set_reply()

    def _pdo_thread_exception_handler(self, exc: Exception) -> None:
        """Callback method for the PDO thread exceptions."""
        self.logger.error(
            "The FSoE Master lost connection to the FSoE slaves. "
            f"An exception occurred during the PDO exchange: {exc}"
        )

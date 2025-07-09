import threading
from typing import TYPE_CHECKING, Callable, Optional, TypeVar, Union, cast, overload

import ingenialogger
from ingenialink import RegDtype
from ingenialink.canopen.register import CanopenRegister
from ingenialink.dictionary import DictionarySafetyModule
from ingenialink.enums.register import RegCyclicType
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.pdo import RPDOMap, TPDOMap
from ingenialink.utils._utils import convert_dtype_to_bytes, dtype_value

from ingeniamotion._utils import weak_lru
from ingeniamotion.enums import FSoEState
from ingeniamotion.exceptions import IMTimeoutError
from ingeniamotion.fsoe_master.fsoe import (
    FSOE_MASTER_INSTALLED,
    BaseMasterHandler,
    FSoEApplicationParameter,
    FSoEDataType,
    FSoEDictionary,
    FSoEDictionaryItem,
    FSoEDictionaryItemInput,
    FSoEDictionaryItemInputOutput,
    FSoEDictionaryItemOutput,
    State,
    StateData,
    calculate_sra_crc,
)
from ingeniamotion.fsoe_master.maps import PDUMaps
from ingeniamotion.fsoe_master.parameters import SafetyParameter, SafetyParameterDirectValidation
from ingeniamotion.fsoe_master.safety_functions import (
    SafeInputsFunction,
    SafetyFunction,
    SS1Function,
    STOFunction,
)

if TYPE_CHECKING:
    from ingenialink.ethercat.dictionary import EthercatDictionary

SAFE_INSTANCE_TYPE = TypeVar("SAFE_INSTANCE_TYPE", bound="SafetyFunction")

__all__ = ["FSoEMasterHandler"]


class FSoEMasterHandler:
    """FSoE Master Handler.

    Args:
        slave_address: The servo's FSoE address.
        connection_id: The FSoE connection ID.
        watchdog_timeout: The FSoE master watchdog timeout in seconds.

    """

    FSOE_MANUF_SAFETY_ADDRESS = "FSOE_MANUF_SAFETY_ADDRESS"
    FSOE_DICTIONARY_CATEGORY = "FSOE"
    MDP_CONFIGURED_MODULE_1 = "MDP_CONFIGURED_MODULE_1"

    __FSOE_RPDO_MAP_1 = "ETG_COMMS_RPDO_MAP256_TOTAL"
    __FSOE_TPDO_MAP_1 = "ETG_COMMS_TPDO_MAP256_TOTAL"

    DEFAULT_WATCHDOG_TIMEOUT_S = 1

    def __init__(
        self,
        servo: EthercatServo,
        *,
        use_sra: bool,
        slave_address: int,
        connection_id: int,
        watchdog_timeout: float = DEFAULT_WATCHDOG_TIMEOUT_S,
        report_error_callback: Callable[[str, str], None],
    ):
        if not FSOE_MASTER_INSTALLED:
            return
        self.logger = ingenialogger.get_logger(__name__)

        self.__servo = servo
        self.__running: bool = False
        self.__uses_sra: bool = use_sra

        self.__state_is_data = threading.Event()

        # The saco slave might take a while to answer with a valid command
        # During it's initialization it will respond with 0's, that are ignored
        # To avoid triggering additional errors
        self.__in_initial_reset = False

        # Parameters that are part of the system
        # UID as key
        self.safety_parameters: dict[str, SafetyParameter] = {}

        # Parameters that will be transmitted during the fsoe parameter state
        fsoe_application_parameters: list[FSoEApplicationParameter] = []

        # Set MDP module
        safety_module = self.__set_configured_module_ident_1()

        for app_parameter in safety_module.application_parameters:
            register = servo.dictionary.get_register(app_parameter.uid)

            if safety_module.uses_sra:
                sp = SafetyParameter(register, servo)
                # Pending add SRA CRC Parameter
                # https://novantamotion.atlassian.net/browse/INGM-621
            else:
                sp = SafetyParameterDirectValidation(register, servo)
                fsoe_application_parameters.append(sp.fsoe_application_parameter)

            self.safety_parameters[app_parameter.uid] = sp

        # If SRA is used, use a single application parameter with CRC computation
        self._sra_crc: Optional[int] = None
        if self.__uses_sra:
            self._sra_crc = self._calculate_sra_crc()
            fsoe_application_parameters.append(
                FSoEApplicationParameter(
                    name="SRA_CRC",
                    initial_value=self._sra_crc,  # https://novantamotion.atlassian.net/browse/INGK-1104
                    n_bytes=dtype_value[register.dtype][0],
                )
            )

        self.dictionary = self.create_safe_dictionary(servo.dictionary)

        self.safety_functions = tuple(SafetyFunction.for_handler(self))

        self._master_handler = BaseMasterHandler(
            dictionary=self.dictionary,
            slave_address=slave_address,
            connection_id=connection_id,
            watchdog_timeout_s=watchdog_timeout,
            application_parameters=fsoe_application_parameters,
            report_error_callback=report_error_callback,
            state_change_callback=self.__state_change_callback,
        )

        self.__safety_master_pdu = servo.read_rpdo_map_from_slave(self.__FSOE_RPDO_MAP_1, 1)
        self.__safety_slave_pdu = servo.read_tpdo_map_from_slave(self.__FSOE_TPDO_MAP_1, 1)

        self.__maps = PDUMaps.from_rpdo_tpdo(
            self.__safety_master_pdu, self.__safety_slave_pdu, dictionary=self.dictionary
        )
        self.set_maps(self.__maps)

    def _calculate_sra_crc(self) -> int:
        """Calculates SRA CRC for the application parameters.

        Raises:
            RuntimeError: if SRA calculation is requested without using SRA.
            RuntimeError: if there are no application parameters to calculate the SRA.

        Returns:
            sra crc.
        """
        if not self.__uses_sra:
            raise RuntimeError("Requested SRA CRC calculation when SRA is not being used.")

        parameters_values = [
            int.from_bytes(
                convert_dtype_to_bytes(data=param.get(), dtype=param.register.dtype), "little"
            )
            for param in self.safety_parameters.values()
        ]
        if not len(parameters_values):
            raise RuntimeError("There are no application parameters, SRA CRC can not be computed.")

        return calculate_sra_crc(parameters_values)

    def __set_configured_module_ident_1(self) -> DictionarySafetyModule:
        """Sets the configured Module Ident.

        Returns:
            Module Ident that has been set.

        Raises:
            RuntimeError: if module ident value to write can not be retrieved.
        """
        module_ident = None
        # https://novantamotion.atlassian.net/browse/INGM-657
        for safety_module in self.__servo.dictionary.safety_modules.values():
            if self.__uses_sra and safety_module.uses_sra:
                module_ident = safety_module.module_ident
            if not self.__uses_sra and not safety_module.uses_sra:
                module_ident = safety_module.module_ident
            if module_ident is not None:
                break
        if module_ident is None:
            raise RuntimeError("Module ident value to write could not be retrieved.")

        self.__servo.write(self.MDP_CONFIGURED_MODULE_1, data=module_ident, subnode=0)

        return self.__servo.dictionary.get_safety_module(module_ident=module_ident)

    def __get_configured_module_ident_1(self) -> Union[int, float, str, bytes]:
        """Gets the configured Module Ident 1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            Configured Module Ident 1.
        """
        return self.__servo.read(self.MDP_CONFIGURED_MODULE_1, subnode=0)

    def __get_safety_module(self) -> DictionarySafetyModule:
        """Gets the configured Module Ident 1.

        Args:
            servo: servo alias to reference it. ``default`` by default.

        Returns:
            Safety module.

        Raises:
            NotImplementedError: if the safety module uses SRA.
        """
        module_ident = int(self.__get_configured_module_ident_1())
        safety_module = self.__servo.dictionary.get_safety_module(module_ident=module_ident)
        if safety_module.uses_sra:
            self.logger.warning("Safety module with SRA is not available.")
        return safety_module

    def __start_on_first_request(self) -> None:
        """Start the FSoE Master handler on first request."""
        self.__in_initial_reset = True
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
    def maps(self) -> "PDUMaps":
        """Get the PDUMap used for the Safety PDUs."""
        return self.__maps

    def set_maps(self, maps: "PDUMaps") -> None:
        """Set new PDUMaps for the Safety PDUs."""
        if self.__running:
            raise RuntimeError("Cannot set map while the FSoE Master is running")

        self._master_handler.master.dictionary_map = maps.outputs
        self._master_handler.slave.dictionary_map = maps.inputs

    def configure_pdo_maps(self) -> None:
        """Configure the PDOMaps used for the Safety PDUs according to the map."""
        # Fill the RPDOMap and TPDOMap with the items from the maps
        self.__maps.fill_rpdo_map(self.safety_master_pdu_map, self.__servo.dictionary)
        self.__maps.fill_tpdo_map(self.safety_slave_pdu_map, self.__servo.dictionary)

        # Update the PDO map items that are listed as safety parameters
        for item in self.safety_master_pdu_map.items + self.safety_slave_pdu_map.items:
            uid = item.register.identifier
            if uid in self.safety_parameters:
                self.safety_parameters[uid].set(item.register_mapping)

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
            self.__start_on_first_request()
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
                raise IndexError(
                    f"Master handler does not contain {typ.__name__} instance {instance}"
                )
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
        return cast("int", self._master_handler.get_slave_address())

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
    def create_safe_dictionary(cls, dictionary: "EthercatDictionary") -> "FSoEDictionary":
        """Create a FSoEdictionary with the safe inputs and outputs.

        Creates the FSoE dictionary from the servo's dictionary.

        Returns:
            A Dictionary instance with the safe inputs and outputs.

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

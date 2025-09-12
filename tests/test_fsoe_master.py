import logging
import random
import time
from typing import TYPE_CHECKING, Any, Callable, Union

import pytest
from ingenialink import RegAccess, RegDtype, Servo
from ingenialink.dictionary import CanOpenObject, DictionarySafetyModule, Interface
from ingenialink.enums.register import RegCyclicType
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.ethercat.servo import EthercatServo
from ingenialink.pdo import RPDOMap, TPDOMap
from ingenialink.pdo_network_manager import PDONetworkManager as ILPDONetworkManager
from ingenialink.register import Register
from ingenialink.servo import DictionaryFactory
from ingenialink.utils._utils import convert_dtype_to_bytes

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEError, FSoEMaster
from ingeniamotion.motion_controller import MotionController
from tests.conftest import add_fixture_error_checker, timeout_loop
from tests.dictionaries import (
    SAMPLE_SAFE_PH1_XDFV3_DICTIONARY,
    SAMPLE_SAFE_PH2_MODULE_IDENT_NO_SRA_MODULE_IDENT,
    SAMPLE_SAFE_PH2_XDFV3_DICTIONARY,
)

if FSOE_MASTER_INSTALLED:
    from fsoe_master import fsoe_master

    from ingeniamotion.fsoe_master import (
        FSoEMasterHandler,
        PDUMaps,
        SafeHomingFunction,
        SafeInputsFunction,
        SafetyFunction,
        SafetyParameter,
        SDIFunction,
        SLIFunction,
        SLPFunction,
        SLSFunction,
        SOSFunction,
        SOutFunction,
        SPFunction,
        SS1Function,
        SS2Function,
        SSRFunction,
        STOFunction,
        SVFunction,
    )
    from ingeniamotion.fsoe_master.frame import FSoEFrame
    from ingeniamotion.fsoe_master.fsoe import (
        FSoEApplicationParameter,
        FSoEDictionaryItemInput,
        FSoEDictionaryItemInputOutput,
    )
    from ingeniamotion.fsoe_master.maps_validator import (
        FSoEFrameRules,
        InvalidFSoEFrameRule,
    )

from ingenialink.ethercat.network import EthercatNetwork
from ingenialink.network import Network

if TYPE_CHECKING:
    from ingenialink.emcy import EmergencyMessage


def test_fsoe_master_not_installed():
    try:
        import fsoe_master  # noqa: F401
    except ModuleNotFoundError:
        pass
    else:
        pytest.skip("fsoe_master is installed")

    mc = MotionController()
    with pytest.raises(NotImplementedError):
        mc.fsoe


def emergency_handler(servo_alias: str, message: "EmergencyMessage"):
    if message.error_code == 0xFF43:
        # Cyclic timeout Ethercat PDO lifeguard
        # is a typical error code when the pdos are stopped
        # Ignore
        return

    if message.error_code == 0:
        # When drive goes to Operational again
        # No error is thrown
        # https://novantamotion.atlassian.net/browse/INGM-627
        return

    raise RuntimeError(f"Emergency message received from {servo_alias}: {message}")


@pytest.fixture(scope="function")
def fsoe_error_monitor(
    request: pytest.FixtureRequest,
) -> Callable[[FSoEError], None]:
    errors = []

    def error_handler(error: FSoEError) -> None:
        errors.append(error)

    def my_fsoe_error_reproter_callback() -> tuple[bool, str]:
        if len(errors) > 0:
            error_messages = "\n".join(str(error) for error in errors)
            return False, f"FSoE errors occurred:\n{error_messages}"
        return True, ""

    add_fixture_error_checker(request.node, my_fsoe_error_reproter_callback)

    return error_handler


@pytest.fixture()
def fsoe_states():
    states = []
    return states


def __set_default_phase2_mapping(handler: "FSoEMasterHandler") -> None:
    sto = handler.get_function_instance(STOFunction)
    safe_inputs = handler.get_function_instance(SafeInputsFunction)
    ss1 = handler.get_function_instance(SS1Function)

    handler.maps.inputs.clear()
    handler.maps.inputs.add(sto.command)
    handler.maps.inputs.add(ss1.command)
    handler.maps.inputs.add_padding(6)
    handler.maps.inputs.add(safe_inputs.value)
    handler.maps.inputs.add_padding(7)

    handler.maps.outputs.clear()
    handler.maps.outputs.add(sto.command)
    handler.maps.outputs.add(ss1.command)
    handler.maps.outputs.add_padding(6 + 8)


@pytest.fixture()
def mc_with_fsoe(mc, fsoe_states, fsoe_error_monitor: Callable[[FSoEError], None]):
    def add_state(state: FSoEState):
        fsoe_states.append(state)

    # Subscribe to emergency messages
    mc.communication.subscribe_emergency_message(emergency_handler)
    # Configure error channel
    mc.fsoe.subscribe_to_errors(fsoe_error_monitor)
    # Create and start the FSoE master handler
    handler = mc.fsoe.create_fsoe_master_handler(use_sra=False, state_change_callback=add_state)
    # If phase II, initialize the handler with the default mapping
    if handler.maps.editable:
        __set_default_phase2_mapping(handler)

    if handler.sout_function() is not None:
        handler.sout_disable()

    yield mc, handler
    # Delete the master handler
    mc.fsoe._delete_master_handler()


@pytest.fixture()
def mc_with_fsoe_with_sra(mc, fsoe_states, fsoe_error_monitor: Callable[[FSoEError], None]):
    def add_state(state: FSoEState):
        fsoe_states.append(state)

    # Subscribe to emergency messages
    mc.communication.subscribe_emergency_message(emergency_handler)
    # Configure error channel
    mc.fsoe.subscribe_to_errors(fsoe_error_monitor)
    # Create and start the FSoE master handler
    handler = mc.fsoe.create_fsoe_master_handler(use_sra=True, state_change_callback=add_state)
    # If phase II, initialize the handler with the default mapping
    if handler.maps.editable:
        __set_default_phase2_mapping(handler)
    if handler.sout_function() is not None:
        handler.sout_disable()
    yield mc, handler
    # Delete the master handler
    mc.fsoe._delete_master_handler()


@pytest.mark.fsoe
@pytest.mark.parametrize("use_sra", [False, True])
def test_create_fsoe_master_handler_use_sra(mc, use_sra):
    master = FSoEMaster(mc)
    handler = master.create_fsoe_master_handler(use_sra=use_sra)
    safety_module = handler._FSoEMasterHandler__get_safety_module()

    assert safety_module.uses_sra is use_sra
    if not use_sra:
        assert handler._sra_fsoe_application_parameter is None
    else:
        assert isinstance(handler._sra_fsoe_application_parameter, FSoEApplicationParameter)

    assert len(safety_module.application_parameters) > 1
    assert len(handler.safety_parameters) == len(safety_module.application_parameters)

    # If SRA is not used, all safety parameters are passed
    if not use_sra:
        assert len(handler._master_handler.master.application_parameters) == len(
            safety_module.application_parameters
        )
    # If SRA is used, a single parameter with the CRC value of all application parameters is passed
    else:
        assert len(handler._master_handler.master.application_parameters) == 1

    master._delete_master_handler()


@pytest.mark.fsoe
def test_create_fsoe_handler_from_invalid_pdo_maps(
    caplog, fsoe_error_monitor: Callable[[FSoEError], None]
):
    mock_servo = MockServo(SAMPLE_SAFE_PH2_XDFV3_DICTIONARY)
    mock_servo.write("ETG_COMMS_RPDO_MAP256_6", 0x123456)  # Invalid pdo map value

    caplog.set_level(logging.ERROR)
    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            report_error_callback=fsoe_error_monitor,
        )

        # An error has been logged
        logger_error = caplog.records[-1]
        assert logger_error.levelno == logging.ERROR
        assert (
            logger_error.message == "Error creating FSoE PDUMaps from RPDO and TPDO on the drive. "
            "Falling back to a default map."
        )

        # And the default minimal map is used
        assert len(handler.maps.inputs) == 0
        assert len(handler.maps.outputs) == 1
        assert handler.maps.outputs[0].item.name == "FSOE_STO"
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_set_configured_module_ident_1(mocker, mc_with_fsoe_with_sra, caplog):
    _, handler = mc_with_fsoe_with_sra

    def create_mock_safety_module(module_ident, uses_sra=True, has_project_crc=False):
        if has_project_crc:
            params = [
                DictionarySafetyModule.ApplicationParameter(
                    uid=handler._FSoEMasterHandler__FSOE_SAFETY_PROJECT_CRC
                )
            ]
        else:
            params = [DictionarySafetyModule.ApplicationParameter(uid="DUMMY_PARAM")]

        return DictionarySafetyModule(
            module_ident=module_ident,
            uses_sra=uses_sra,
            application_parameters=params,
        )

    # Do not write mocked values to the servo
    mocker.patch.object(handler._FSoEMasterHandler__servo, "write")
    mock_safety_modules = {
        1: create_mock_safety_module(module_ident=1, uses_sra=True, has_project_crc=True)
    }
    mocker.patch.object(
        handler._FSoEMasterHandler__servo.dictionary,
        "safety_modules",
        mock_safety_modules,
    )

    caplog.set_level(logging.WARNING)
    with pytest.raises(
        RuntimeError,
        match="Module ident value to write could not be retrieved.",
    ):
        handler._FSoEMasterHandler__set_configured_module_ident_1()
    expected_warning = (
        f"Safety module has the application parameter "
        f"{handler._FSoEMasterHandler__FSOE_SAFETY_PROJECT_CRC}, skipping it."
    )
    assert expected_warning in caplog.text

    # Use a proper safety module
    mock_safety_modules = {
        2: create_mock_safety_module(module_ident=2, uses_sra=True, has_project_crc=False)
    }
    mocker.patch.object(
        handler._FSoEMasterHandler__servo.dictionary,
        "safety_modules",
        mock_safety_modules,
    )
    result = handler._FSoEMasterHandler__set_configured_module_ident_1()
    assert result == mock_safety_modules[2]


@pytest.mark.fsoe
def test_fsoe_master_get_safety_parameters(mc_with_fsoe):
    _mc, handler = mc_with_fsoe

    assert len(handler.safety_parameters) != 0


class MockSafetyParameter(SafetyParameter):
    def __init__(self, register: "EthercatRegister", servo: "EthercatServo"):
        self.__register = register
        self.__servo = servo

        self.__value = 0

    @property
    def register(self) -> "EthercatRegister":
        """Get the register associated with the safety parameter."""
        return self.__register


class MockNetwork(EthercatNetwork):
    def __init__(self):
        Network.__init__(self)

        self._pdo_manager = ILPDONetworkManager(self)


class MockServo(Servo):
    interface = Interface.ECAT

    def __init__(self, dictionary_path: str):
        super().__init__(target=1, dictionary_path=dictionary_path)

        self.current_values = {
            register: convert_dtype_to_bytes(register.default, register.dtype)
            for register in self.dictionary.all_registers()
        }

    def _write_raw(self, register: Register, data: bytes, **kwargs: Any):
        self.current_values[register] = data

    def _read_raw(self, reg: Register, **kwargs: Any) -> bytes:
        return self.current_values[reg]

    def read_complete_access(
        self, reg: Union[str, Register, CanOpenObject], *args, **kwargs
    ) -> bytes:
        if not isinstance(reg, CanOpenObject):
            raise NotImplementedError

        value = bytearray()

        for register in reg:
            value += self.current_values[register]
            if register.subidx == 0:
                value += b"\00"  # Padding after first u8 element

        return bytes(value)

    read_rpdo_map_from_slave = EthercatServo.read_rpdo_map_from_slave
    read_tpdo_map_from_slave = EthercatServo.read_tpdo_map_from_slave


class MockHandler(FSoEMasterHandler):
    def __init__(self, dictionary: str, module_uid: int):
        xdf = DictionaryFactory.create_dictionary(dictionary, interface=Interface.ECAT)
        self.dictionary = FSoEMasterHandler.create_safe_dictionary(xdf)
        self.__servo = MockServo(dictionary)
        self.safety_parameters = {
            app_parameter.uid: MockSafetyParameter(
                xdf.get_register(app_parameter.uid), self.__servo
            )
            for app_parameter in xdf.get_safety_module(module_uid).application_parameters
        }

        self.safety_functions = tuple(SafetyFunction.for_handler(self))


@pytest.mark.fsoe
def test_constructor_set_slave_address(fsoe_error_monitor: Callable[[FSoEError], None]):
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            slave_address=0x7412,
            report_error_callback=fsoe_error_monitor,
        )

        assert mock_servo.read(FSoEMasterHandler.FSOE_MANUF_SAFETY_ADDRESS) == 0x7412
        assert handler._master_handler.get_slave_address() == 0x7412
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_constructor_inherit_slave_address(fsoe_error_monitor: Callable[[FSoEError], None]):
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    try:
        # Set the slave address in the servo
        mock_servo.write(FSoEMasterHandler.FSOE_MANUF_SAFETY_ADDRESS, 0x4986)

        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            report_error_callback=fsoe_error_monitor,
        )

        assert mock_servo.read(FSoEMasterHandler.FSOE_MANUF_SAFETY_ADDRESS) == 0x4986
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_constructor_set_connection_id(fsoe_error_monitor: Callable[[FSoEError], None]):
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            connection_id=0x3742,
            report_error_callback=fsoe_error_monitor,
        )
        assert handler._master_handler.master.session.connection_id.value == 0x3742
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_constructor_random_connection_id(fsoe_error_monitor: Callable[[FSoEError], None]):
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)

    random.seed(0x1234)
    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            report_error_callback=fsoe_error_monitor,
        )
        assert handler._master_handler.master.session.connection_id.value == 0xED9A
    finally:
        handler.delete()


@pytest.mark.fsoe
def test_detect_safety_functions_ph1():
    handler = MockHandler(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY, 0x3800000)

    sf = list(SafetyFunction.for_handler(handler))
    sf_types = [type(sf) for sf in sf]

    assert sf_types == [STOFunction, SS1Function, SafeInputsFunction]

    # STO
    sto = sf[0]
    assert isinstance(sto, STOFunction)
    assert sto.n_instance is None
    assert sto.name == "Safe Torque Off"
    assert isinstance(sto.command, FSoEDictionaryItemInputOutput)
    assert sto.parameters == {}
    assert len(sto.ios) == 1
    for metadata, io in sto.ios.items():
        assert io == sto.command
        assert metadata.display_name == "Command"
        assert metadata.uid == "FSOE_STO"

    # SS1
    ss1 = sf[1]
    assert isinstance(ss1, SS1Function)
    assert ss1.n_instance == 1
    assert ss1.name == "Safe Stop 1"
    assert isinstance(ss1.command, FSoEDictionaryItemInputOutput)
    assert len(ss1.parameters) == 1
    for metadata, parameter in ss1.parameters.items():
        assert parameter == ss1.time_to_sto
        assert metadata.display_name == "Time to STO"
        assert metadata.uid == "FSOE_SS1_TIME_TO_STO_1"
    assert len(ss1.ios) == 1
    for metadata, io in ss1.ios.items():
        assert io == ss1.command
        assert metadata.display_name == "Command"
        assert metadata.uid == "FSOE_SS1_1"

    # Safe inputs
    si = sf[2]
    assert isinstance(si, SafeInputsFunction)
    assert si.n_instance is None
    assert si.name == "Safe Inputs"
    assert isinstance(si.value, FSoEDictionaryItemInput)
    assert len(si.parameters) == 1
    for metadata, parameter in si.parameters.items():
        assert parameter == si.map
        assert metadata.display_name == "Map"
        assert metadata.uid == "FSOE_SAFE_INPUTS_MAP"
    assert len(si.ios) == 1
    for metadata, io in si.ios.items():
        assert io == si.value
        assert metadata.display_name == "Value"
        assert metadata.uid == "FSOE_SAFE_INPUTS_VALUE"


@pytest.mark.fsoe
def test_detect_safety_functions_ph2():
    handler = MockHandler(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, SAMPLE_SAFE_PH2_MODULE_IDENT_NO_SRA_MODULE_IDENT
    )

    sf_types = [type(sf) for sf in SafetyFunction.for_handler(handler)]

    assert sf_types == [
        STOFunction,
        SS1Function,
        SafeInputsFunction,
        SOSFunction,
        SS2Function,
        SOutFunction,
        SPFunction,
        SVFunction,
        SafeHomingFunction,
        # SLS
        SLSFunction,
        SLSFunction,
        SLSFunction,
        SLSFunction,
        SLSFunction,
        SLSFunction,
        SLSFunction,
        SLSFunction,
        # SSR
        SSRFunction,
        SSRFunction,
        SSRFunction,
        SSRFunction,
        SSRFunction,
        SSRFunction,
        SSRFunction,
        SSRFunction,
        # SLP
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SLPFunction,
        SDIFunction,
        SLIFunction,
    ]


@pytest.mark.fsoe
def test_optional_parameter_not_present():
    handler = MockHandler(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY, 0x3800000)

    sto: STOFunction = next(STOFunction.for_handler(handler))

    assert sto.activate_sout is None
    assert sto.parameters == {}


@pytest.mark.fsoe
def test_optional_parameter_present():
    handler = MockHandler(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, SAMPLE_SAFE_PH2_MODULE_IDENT_NO_SRA_MODULE_IDENT
    )

    sto: STOFunction = next(STOFunction.for_handler(handler))

    assert sto.activate_sout is not None
    assert len(sto.parameters) == 1
    metadata, parameter = next(iter(sto.parameters.items()))
    assert metadata.uid == "FSOE_STO_ACTIVATE_SOUT"
    assert metadata.display_name == "Activate SOUT"
    assert parameter is not None


def test_get_parameters_not_related_to_safety_functions():
    handler = MockHandler(
        SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, SAMPLE_SAFE_PH2_MODULE_IDENT_NO_SRA_MODULE_IDENT
    )
    unrelated_parameters = handler.get_parameters_not_related_to_safety_functions()
    assert {param.register.identifier for param in unrelated_parameters} == {
        *(f"ETG_COMMS_RPDO_MAP256_{i}" for i in range(1, 46)),
        "ETG_COMMS_RPDO_MAP256_TOTAL",
        *(f"ETG_COMMS_TPDO_MAP256_{i}" for i in range(1, 46)),
        "ETG_COMMS_TPDO_MAP256_TOTAL",
        "FSOE_ABS_SSI_PRIM1_BAUD",
        "FSOE_ABS_SSI_PRIM1_FSIZE",
        "FSOE_ABS_SSI_PRIM1_POL",
        "FSOE_ABS_SSI_PRIM1_POSBITS",
        "FSOE_ABS_SSI_PRIM1_STURN",
        "FSOE_ABS_SSI_PRIM1_TOUT",
        "FSOE_ABS_SSI_SECOND1_BAUD",
        "FSOE_ABS_SSI_SECOND1_FSIZE",
        "FSOE_ABS_SSI_SECOND1_PBITS",
        "FSOE_ABS_SSI_SECOND1_POL",
        "FSOE_ABS_SSI_SECOND1_STURN",
        "FSOE_ABS_SSI_SECOND1_TOUT",
        "FSOE_FEEDBACK_RATIO_MAIN_TURNS",
        "FSOE_FEEDBACK_RATIO_REDUNDANT_TURNS",
        "FSOE_FEEDBACK_SCENARIO",
        "FSOE_HALL_POLARITY",
        "FSOE_HALL_POLEPAIRS",
        "FSOE_INCREMENTAL_ENC_POLARITY",
        "FSOE_INCREMENTAL_ENC_RESOLUTION",
        "FSOE_USER_OVER_TEMPERATURE",
    }


@pytest.mark.fsoe
def test_mandatory_safety_functions(mc_with_fsoe):
    _mc, handler = mc_with_fsoe

    safety_functions_by_types = handler.safety_functions_by_type()

    sto_instances = safety_functions_by_types[STOFunction]
    assert len(sto_instances) == 1

    ss1_instances = safety_functions_by_types[SS1Function]
    assert len(ss1_instances) >= 1

    si_instances = safety_functions_by_types[SafeInputsFunction]
    assert len(si_instances) == 1


@pytest.mark.fsoe
def test_getter_of_safety_functions(mc_with_fsoe):
    _mc, handler = mc_with_fsoe

    sto_function = STOFunction(
        n_instance=None, name="Dummy", command=None, activate_sout=None, ios=None, parameters=None
    )
    ss1_function_1 = SS1Function(
        n_instance=None,
        name="Dummy",
        ios=None,
        parameters=None,
        command=None,
        time_to_sto=None,
        velocity_zero_window=None,
        time_for_velocity_zero=None,
        time_delay_for_deceleration=None,
        deceleration_limit=None,
        activate_sout=None,
    )
    ss1_function_2 = SS1Function(
        n_instance=None,
        name="Dummy",
        ios=None,
        parameters=None,
        command=None,
        time_to_sto=None,
        time_for_velocity_zero=None,
        time_to_sos=None,
        deceleration_limit=None,
        time_delay_for_deceleration=None,
        error_reaction=None,
    )

    handler.safety_functions = (sto_function, ss1_function_1, ss1_function_2)
    handler.get_function_instance.cache_clear()

    # Single instance of STOFunction
    assert handler.get_function_instance(STOFunction) is sto_function
    assert handler.get_function_instance(STOFunction, instance=1) is sto_function

    # Multiple instances of SS1Function
    with pytest.raises(ValueError) as error:
        # Must specify the instance
        handler.get_function_instance(SS1Function)
    assert (
        error.value.args[0]
        == "Multiple SS1Function instances found (2). Specify the instance number."
    )

    with pytest.raises(IndexError) as error:
        # Instance 0 does not exist
        handler.get_function_instance(SS1Function, instance=0)
    assert error.value.args[0] == "Master handler does not contain SS1Function instance 0"
    assert handler.get_function_instance(SS1Function, instance=1) is ss1_function_1
    assert handler.get_function_instance(SS1Function, instance=2) is ss1_function_2
    with pytest.raises(IndexError) as error:
        # Instance 3 does not exist
        handler.get_function_instance(SS1Function, instance=3)
    assert error.value.args[0] == "Master handler does not contain SS1Function instance 3"


@pytest.mark.fsoe
def test_modify_safe_parameters(fsoe_error_monitor: Callable[[FSoEError], None]):
    mock_servo = MockServo(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY)
    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            report_error_callback=fsoe_error_monitor,
        )

        input_map = handler.get_function_instance(SafeInputsFunction).map
        map_uid = "FSOE_SAFE_INPUTS_MAP"

        input_map.set(1)
        assert mock_servo.read(map_uid) == 1

        input_map.set_without_updating(1234)
        assert mock_servo.read(map_uid) == 1

        handler.write_safe_parameters()
        assert mock_servo.read(map_uid) == 1234

    finally:
        handler.delete()


@pytest.mark.fsoe_phase2
def test_write_safe_parameters(mc_with_fsoe):
    mc, handler = mc_with_fsoe
    expected_value = {}
    for key, param in handler.safety_parameters.items():
        old_val = mc.communication.get_register(key)

        # Remove if when SACOAPP-299 is completed
        if key == "FSOE_SSR_ERROR_REACTION_8":
            param.register._enums = {"STO": 0x66400001, "SS1": 0x66500101, "No reaction": 0x0}
        # Remove if when SACOAPP-300 is completed
        if key == "FSOE_SS2_ERROR_REACTION_1":
            param.register._enums = {"STO": 0x66400001, "No reaction": 0x0}
        if param.register.enums:
            enum_values = list(param.register.enums.values())
            enum_values.remove(old_val)
            new_val = enum_values[0]
        else:
            new_val = old_val - 1 if old_val == param.register.range[1] else old_val + 1
        param.set_without_updating(new_val)
        # Ignore RxPDO and TxPDO FSoE Map registers in write_safe_parameters
        if param.register.idx in [0x1700, 0x1B00]:
            expected_value[key] = old_val
        else:
            expected_value[key] = new_val
    handler.write_safe_parameters()
    for key, param in handler.safety_parameters.items():
        test_val = mc.communication.get_register(key)
        assert test_val == expected_value[key], f"Parameter {key} not written correctly"


@pytest.mark.fsoe
@pytest.mark.parametrize(
    "dictionary, editable",
    [(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY, False), (SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, True)],
)
def test_mapping_locked(dictionary, editable, fsoe_error_monitor: Callable[[FSoEError], None]):
    mock_servo = MockServo(dictionary)

    if not editable:
        # First xdf v3 and esi files of phase 1 had the PDOs set to RW as a mistake
        # for XDF V2, the hard-coded pdo maps are created with RO access
        for obj in [
            mock_servo.dictionary.get_object("ETG_COMMS_RPDO_MAP256", 1),
            mock_servo.dictionary.get_object("ETG_COMMS_TPDO_MAP256", 1),
        ]:
            for reg in obj.registers:
                reg._access = RegAccess.RO

    try:
        handler = FSoEMasterHandler(
            servo=mock_servo,
            net=MockNetwork(),
            use_sra=True,
            report_error_callback=fsoe_error_monitor,
        )
        assert handler.maps.editable is editable

        if editable:
            handler.maps.inputs.clear()
        else:
            with pytest.raises(fsoe_master.FSOEMasterMappingLockedException):
                handler.maps.inputs.clear()

        new_maps = handler.maps.copy()
        assert new_maps.editable is editable

        if editable:
            new_maps.outputs.clear()
        else:
            with pytest.raises(fsoe_master.FSOEMasterMappingLockedException):
                new_maps.outputs.clear()

    finally:
        handler.delete()


TIMEOUT_FOR_DATA_SRA = 3
TIMEOUT_FOR_DATA = 30


@pytest.fixture()
def mc_state_data_with_sra(mc_with_fsoe_with_sra):
    mc, _handler = mc_with_fsoe_with_sra

    mc.fsoe.configure_pdos(start_pdos=True)
    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=TIMEOUT_FOR_DATA_SRA)

    # Remove fail-safe state
    mc.fsoe.set_fail_safe(False)

    yield mc

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.fixture()
def mc_state_data(mc_with_fsoe):
    mc, _handler = mc_with_fsoe

    mc.fsoe.configure_pdos(start_pdos=True)
    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=TIMEOUT_FOR_DATA)

    # Remove fail-safe state
    mc.fsoe.set_fail_safe(False)

    yield mc

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
def test_pass_through_states(mc_state_data, fsoe_states):  # noqa: ARG001
    assert fsoe_states == [
        FSoEState.SESSION,
        FSoEState.CONNECTION,
        FSoEState.PARAMETER,
        FSoEState.DATA,
    ]


@pytest.mark.fsoe
def test_pass_through_states_sra(mc_state_data_with_sra, fsoe_states):  # noqa: ARG001
    assert fsoe_states == [
        FSoEState.SESSION,
        FSoEState.CONNECTION,
        FSoEState.PARAMETER,
        FSoEState.DATA,
    ]


@pytest.mark.fsoe_phase2
def test_maps_different_length(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"], alias: str
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    sto = handler.get_function_instance(STOFunction)
    safe_inputs = handler.get_function_instance(SafeInputsFunction)
    ss1 = handler.get_function_instance(SS1Function)

    handler.maps.inputs.clear()
    handler.maps.inputs.add(sto.command)
    handler.maps.inputs.add(ss1.command)
    handler.maps.inputs.add_padding(6)
    handler.maps.inputs.add(safe_inputs.value)
    handler.maps.inputs.add_padding(7)

    handler.maps.outputs.clear()
    handler.maps.outputs.add(sto.command)
    handler.maps.outputs.add(ss1.command)
    handler.maps.outputs.add_padding(6)

    assert handler.maps.inputs.safety_bits == 16
    assert handler.maps.outputs.safety_bits == 8

    # Configure the FSoE master handler
    mc.fsoe.configure_pdos(start_pdos=False)

    # Inputs: 1 byte command + 2 bytes safety data + 2 bytes CRC + 2 bytes connection ID
    # 7 bytes -> 56 bits
    assert handler.safety_slave_pdu_map.data_length_bits == 56
    # Outputs: 1 byte command + 1 bytes safety data + 2 bytes CRC + 2 bytes connection ID
    # 6 bytes -> 48 bits
    assert handler.safety_master_pdu_map.data_length_bits == 48

    mc.capture.pdo.start_pdos(servo=alias)
    mc.fsoe.wait_for_state_data(timeout=TIMEOUT_FOR_DATA)
    assert handler.state == FSoEState.DATA
    # Check that it stays in Data state
    for i in range(2):
        time.sleep(1)
    assert handler.state == FSoEState.DATA

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
def test_start_and_stop_multiple_times(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
) -> None:
    mc, handler = mc_with_fsoe_with_sra

    # Any fsoe error during the start/stop process
    # will fail the test because of error_handler

    for i in range(4):
        mc.fsoe.configure_pdos(start_pdos=True)
        mc.fsoe.wait_for_state_data(timeout=TIMEOUT_FOR_DATA)
        assert handler.state == FSoEState.DATA
        time.sleep(1)
        assert handler.state == FSoEState.DATA
        mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
@pytest.mark.parametrize("mc_instance", ["mc_state_data", "mc_state_data_with_sra"])
def test_safe_inputs_value(request, mc_instance):
    mc = request.getfixturevalue(mc_instance)
    value = mc.fsoe.get_safety_inputs_value()

    # Assume safe inputs are disconnected on the setup
    assert value == 0


@pytest.mark.fsoe
def test_safety_address(mc_with_fsoe, alias):
    mc, _handler = mc_with_fsoe

    master_handler = mc.fsoe._handlers[alias]

    mc.fsoe.set_safety_address(0x7453)
    # Setting the safety address has effects on the master
    assert master_handler._master_handler.master.session.slave_address.value == 0x7453

    # And on the slave
    assert mc.communication.get_register("FSOE_MANUF_SAFETY_ADDRESS") == 0x7453

    # The getter also works
    assert mc.fsoe.get_safety_address() == 0x7453


def mc_state_to_fsoe_master_state(state: FSoEState):
    return {
        FSoEState.RESET: fsoe_master.StateReset,
        FSoEState.SESSION: fsoe_master.StateSession,
        FSoEState.CONNECTION: fsoe_master.StateConnection,
        FSoEState.PARAMETER: fsoe_master.StateParameter,
        FSoEState.DATA: fsoe_master.StateData,
    }[state]


@pytest.mark.fsoe
@pytest.mark.parametrize(
    "state_enum",
    [
        FSoEState.RESET,
        FSoEState.SESSION,
        FSoEState.CONNECTION,
        FSoEState.PARAMETER,
        FSoEState.DATA,
    ],
)
def test_get_master_state(mocker, mc_with_fsoe, state_enum):
    mc, _handler = mc_with_fsoe

    # Master state is obtained as function
    # and not on the parametrize
    # to avoid depending on the optionally installed module
    # on pytest collection
    fsoe_master_state = mc_state_to_fsoe_master_state(state_enum)

    mocker.patch("fsoe_master.fsoe_master.MasterHandler.state", fsoe_master_state)

    assert mc.fsoe.get_fsoe_master_state() == state_enum


@pytest.mark.fsoe
def test_motor_enable(mc_state_data_with_sra):
    mc = mc_state_data_with_sra

    # Deactivate the SS1
    mc.fsoe.ss1_deactivate()
    # Deactivate the STO
    mc.fsoe.sto_deactivate()
    # Wait for the STO to be deactivated
    for _ in timeout_loop(
        timeout_sec=5, other=RuntimeError("Timeout waiting for STO deactivation")
    ):
        if not mc.fsoe.check_sto_active():
            break
    # Enable the motor
    mc.motion.motor_enable()
    # Disable the motor
    mc.motion.motor_disable()
    # Activate the SS1
    mc.fsoe.ss1_activate()
    # Activate the STO
    mc.fsoe.sto_activate()


@pytest.mark.fsoe
def test_copy_modify_and_set_map(mc_with_fsoe):
    _mc, handler = mc_with_fsoe

    # Obtain one safety input
    si = handler.safe_inputs_function().value

    # Create a copy of the map
    new_maps = handler.maps.copy()

    # The new map can be modified
    new_maps.inputs.remove(si)
    assert new_maps.inputs.get_text_representation() == (
        "Item                                     | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                                 | 0..0                 | 0..1                \n"
        "FSOE_SS1_1                               | 0..1                 | 0..1                \n"
        "Padding                                  | 0..2                 | 0..6                \n"
        "Padding                                  | 1..0                 | 0..7                "
    )

    # Without affecting the original map of the handler
    assert handler.maps.inputs.get_text_representation() == (
        "Item                                     | Position bytes..bits | Size bytes..bits    \n"
        "FSOE_STO                                 | 0..0                 | 0..1                \n"
        "FSOE_SS1_1                               | 0..1                 | 0..1                \n"
        "Padding                                  | 0..2                 | 0..6                \n"
        "FSOE_SAFE_INPUTS_VALUE                   | 1..0                 | 0..1                \n"
        "Padding                                  | 1..1                 | 0..7                "
    )

    # The new map can be set to the handler
    handler.set_maps(new_maps)

    # And is set to the backend of the real master
    assert handler._master_handler.master.dictionary_map == new_maps.outputs
    assert handler._master_handler.slave.dictionary_map == new_maps.inputs


class TestPduMapper:
    AXIS_1 = 1
    TEST_SI_U16_UID = "TEST_SI_U16"
    TEST_SI_U8_UID = "TEST_SI_U8"

    @pytest.fixture()
    def sample_safe_dictionary(self):
        safe_dict = DictionaryFactory.create_dictionary(
            SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, interface=Interface.ECAT
        )

        # Add sample registers
        safe_dict._registers[self.AXIS_1][self.TEST_SI_U16_UID] = EthercatRegister(
            idx=0xF000,
            subidx=0,
            dtype=RegDtype.U16,
            access=RegAccess.RO,
            identifier=self.TEST_SI_U16_UID,
            pdo_access=RegCyclicType.SAFETY_INPUT,
            cat_id="FSOE",
        )
        safe_dict._registers[self.AXIS_1][self.TEST_SI_U8_UID] = EthercatRegister(
            idx=0xF001,
            subidx=0,
            dtype=RegDtype.U8,
            access=RegAccess.RO,
            identifier=self.TEST_SI_U8_UID,
            pdo_access=RegCyclicType.SAFETY_INPUT,
            cat_id="FSOE",
        )

        # Add more CRC registers
        safe_dict._registers[self.AXIS_1]["FSOE_SLAVE_FRAME_ELEM_CRC2"] = EthercatRegister(
            idx=0xF002,
            subidx=0,
            dtype=RegDtype.U16,
            access=RegAccess.RO,
            identifier="FSOE_SLAVE_FRAME_ELEM_CRC2",
            pdo_access=RegCyclicType.SAFETY_INPUT,
            cat_id="FSOE",
        )
        safe_dict._registers[self.AXIS_1]["FSOE_SLAVE_FRAME_ELEM_CRC3"] = EthercatRegister(
            idx=0xF003,
            subidx=0,
            dtype=RegDtype.U16,
            access=RegAccess.RO,
            identifier="FSOE_SLAVE_FRAME_ELEM_CRC3",
            pdo_access=RegCyclicType.SAFETY_INPUT,
            cat_id="FSOE",
        )

        fsoe_dict = FSoEMasterHandler.create_safe_dictionary(safe_dict)

        return safe_dict, fsoe_dict

    @pytest.mark.fsoe
    def test_map_phase_1(self, sample_safe_dictionary):
        safe_dict, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        maps.outputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        maps.outputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
        maps.outputs.add_padding(bits=6 + 8)

        maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        maps.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
        maps.inputs.add_padding(bits=6)
        maps.inputs.add(fsoe_dict.name_map[SafeInputsFunction.SAFE_INPUTS_UID])
        maps.inputs.add_padding(bits=7)

        rpdo = RPDOMap()
        # Registers that are present in the map,
        # are cleared when the map is filled
        rpdo.add_registers(safe_dict.get_register("DRV_OP_CMD"))
        maps.fill_rpdo_map(rpdo, safe_dict)

        assert rpdo.items[0].register.identifier == "FSOE_MASTER_FRAME_ELEM_CMD"
        assert rpdo.items[0].register.idx == 0x6770
        assert rpdo.items[0].register.subidx == 0x01
        assert rpdo.items[0].size_bits == 8

        assert rpdo.items[1].register.identifier == "FSOE_STO"
        assert rpdo.items[1].register.idx == 0x6640
        assert rpdo.items[1].register.subidx == 0x0
        assert rpdo.items[1].size_bits == 1

        assert rpdo.items[2].register.identifier == "FSOE_SS1_1"
        assert rpdo.items[2].register.idx == 0x6650
        assert rpdo.items[2].register.subidx == 0x1
        assert rpdo.items[2].size_bits == 1

        assert rpdo.items[3].register.identifier == "PADDING"
        assert rpdo.items[3].register.idx == 0
        assert rpdo.items[3].register.subidx == 0
        assert rpdo.items[3].size_bits == 14

        assert rpdo.items[4].register.identifier == "FSOE_MASTER_FRAME_ELEM_CRC0"
        assert rpdo.items[4].register.idx == 0x6770
        assert rpdo.items[4].register.subidx == 0x03
        assert rpdo.items[4].size_bits == 16

        assert rpdo.items[5].register.identifier == "FSOE_MASTER_FRAME_ELEM_CONNID"
        assert rpdo.items[5].register.idx == 0x6770
        assert rpdo.items[5].register.subidx == 0x02
        assert rpdo.items[5].size_bits == 16

        assert len(rpdo.items) == 6

        tpdo = TPDOMap()
        maps.fill_tpdo_map(tpdo, safe_dict)

        assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
        assert tpdo.items[0].register.idx == 0x6760
        assert tpdo.items[0].register.subidx == 0x01
        assert tpdo.items[0].size_bits == 8

        assert tpdo.items[1].register.identifier == "FSOE_STO"
        assert tpdo.items[1].register.idx == 0x6640
        assert tpdo.items[1].register.subidx == 0x0
        assert tpdo.items[1].size_bits == 1

        assert tpdo.items[2].register.identifier == "FSOE_SS1_1"
        assert tpdo.items[2].register.idx == 0x6650
        assert tpdo.items[2].register.subidx == 0x1
        assert tpdo.items[2].size_bits == 1

        assert tpdo.items[3].register.identifier == "PADDING"
        assert tpdo.items[3].register.idx == 0
        assert tpdo.items[3].register.subidx == 0
        assert tpdo.items[3].size_bits == 6

        assert tpdo.items[4].register.identifier == "FSOE_SAFE_INPUTS_VALUE"
        assert tpdo.items[4].register.idx == 0x46D1
        assert tpdo.items[4].register.subidx == 0x0
        assert tpdo.items[4].size_bits == 1

        assert tpdo.items[5].register.identifier == "PADDING"
        assert tpdo.items[5].register.idx == 0
        assert tpdo.items[5].register.subidx == 0
        assert tpdo.items[5].size_bits == 7

        assert tpdo.items[6].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
        assert tpdo.items[6].register.idx == 0x6760
        assert tpdo.items[6].register.subidx == 0x03
        assert tpdo.items[6].size_bits == 16

        assert tpdo.items[7].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
        assert tpdo.items[7].register.idx == 0x6760
        assert tpdo.items[7].register.subidx == 0x02
        assert tpdo.items[7].size_bits == 16

        assert len(tpdo.items) == 8

        recreated_pdu_maps = PDUMaps.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
        assert (
            recreated_pdu_maps.outputs.get_text_representation()
            == maps.outputs.get_text_representation()
        )
        assert (
            recreated_pdu_maps.inputs.get_text_representation()
            == maps.inputs.get_text_representation()
        )

    @pytest.mark.fsoe
    def test_map_8_safe_bits(self, sample_safe_dictionary):
        safe_dict, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U8_UID])

        # Create the rpdo map
        tpdo = TPDOMap()
        maps.fill_tpdo_map(tpdo, safe_dict)

        assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
        assert tpdo.items[0].size_bits == 8

        assert tpdo.items[1].register.identifier == "TEST_SI_U8"
        assert tpdo.items[1].size_bits == 8

        assert tpdo.items[2].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
        assert tpdo.items[2].size_bits == 16

        assert tpdo.items[3].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
        assert tpdo.items[3].size_bits == 16

        assert len(tpdo.items) == 4

        rpdo = RPDOMap()
        maps.fill_rpdo_map(rpdo, safe_dict)

        recreated_pdu_maps = PDUMaps.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
        assert (
            recreated_pdu_maps.outputs.get_text_representation()
            == maps.outputs.get_text_representation()
        )
        assert (
            recreated_pdu_maps.inputs.get_text_representation()
            == maps.inputs.get_text_representation()
        )

    @pytest.mark.fsoe
    def test_empty_map_8_bits(self, sample_safe_dictionary):
        safe_dict, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)
        tpdo = TPDOMap()
        maps.fill_tpdo_map(tpdo, safe_dict)

        assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
        assert tpdo.items[0].size_bits == 8

        assert tpdo.items[1].register.identifier == "PADDING"
        assert tpdo.items[1].size_bits == 8

        assert tpdo.items[2].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
        assert tpdo.items[2].size_bits == 16

        assert tpdo.items[3].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
        assert tpdo.items[3].size_bits == 16

        assert len(tpdo.items) == 4

    @pytest.mark.fsoe
    def test_map_with_32_bit_vars(self, sample_safe_dictionary):
        safe_dict, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        # Append a 32-bit variable
        maps.inputs.add(fsoe_dict.name_map["FSOE_SAFE_POSITION"])

        # Create the rpdo map
        tpdo = TPDOMap()
        maps.fill_tpdo_map(tpdo, safe_dict)

        assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
        assert tpdo.items[0].size_bits == 8

        assert tpdo.items[1].register.identifier == "FSOE_SAFE_POSITION"
        assert tpdo.items[1].size_bits == 16

        assert tpdo.items[2].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
        assert tpdo.items[2].size_bits == 16

        # On this padding, the 32-bit variable will continue to be transmitted
        assert tpdo.items[3].register.identifier == "PADDING"
        assert tpdo.items[3].size_bits == 16

        assert tpdo.items[4].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC1"
        assert tpdo.items[4].size_bits == 16

        assert tpdo.items[5].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
        assert tpdo.items[5].size_bits == 16

        assert len(tpdo.items) == 6

        rpdo = RPDOMap()
        maps.fill_rpdo_map(rpdo, safe_dict)

        recreated_pdu_maps = PDUMaps.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
        assert (
            recreated_pdu_maps.outputs.get_text_representation()
            == maps.outputs.get_text_representation()
        )
        assert (
            recreated_pdu_maps.inputs.get_text_representation()
            == maps.inputs.get_text_representation()
        )

    @pytest.mark.fsoe
    def test_map_with_32_bit_vars_offset_8(self, sample_safe_dictionary):
        safe_dict, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        # Add a first 8-bit variable that will shift the 32-bit variable
        maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U8_UID])
        # Append a 32-bit variable
        maps.inputs.add(fsoe_dict.name_map["FSOE_SAFE_POSITION"])
        maps.inputs.add_padding(bits=8)

        # Create the rpdo map
        tpdo = TPDOMap()
        maps.fill_tpdo_map(tpdo, safe_dict)

        assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
        assert tpdo.items[0].size_bits == 8

        assert tpdo.items[1].register.identifier == "TEST_SI_U8"
        assert tpdo.items[1].size_bits == 8

        # Variable cut to what fills on the slot (8 bits of 32 bits, 24 remaining)
        assert tpdo.items[2].register.identifier == "FSOE_SAFE_POSITION"
        assert tpdo.items[2].size_bits == 8

        assert tpdo.items[3].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
        assert tpdo.items[3].size_bits == 16

        # On this padding, the 32-bit variable will continue to be transmitted
        # (16 bits of 32 bits, 8 remaining)
        assert tpdo.items[4].register.identifier == "PADDING"
        assert tpdo.items[4].size_bits == 16

        assert tpdo.items[5].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC1"
        assert tpdo.items[5].size_bits == 16

        # On this padding, the 32-bit variable will continue to be transmitted
        # (8 bits of 32 bits, 0 remaining)
        assert tpdo.items[6].register.identifier == "PADDING"
        assert tpdo.items[6].size_bits == 8

        # 8 bits of regular padding to fill the 16 bits of the data last slot.
        assert tpdo.items[7].register.identifier == "PADDING"
        assert tpdo.items[7].size_bits == 8

        assert tpdo.items[8].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC2"
        assert tpdo.items[8].size_bits == 16

        assert tpdo.items[9].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
        assert tpdo.items[9].size_bits == 16

        assert len(tpdo.items) == 10

        rpdo = RPDOMap()
        maps.fill_rpdo_map(rpdo, safe_dict)

        recreated_pdu_maps = PDUMaps.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
        assert (
            recreated_pdu_maps.outputs.get_text_representation()
            == maps.outputs.get_text_representation()
        )
        assert (
            recreated_pdu_maps.inputs.get_text_representation()
            == maps.inputs.get_text_representation()
        )

    @pytest.mark.fsoe
    def test_map_with_32_bit_vars_offset_16(self, sample_safe_dictionary):
        safe_dict, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        # Add a first 16-bit variable that will shift the 32-bit variable
        maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U16_UID])
        # Append a 32-bit variable
        maps.inputs.add(fsoe_dict.name_map["FSOE_SAFE_POSITION"])

        # Create the rpdo map
        tpdo = TPDOMap()
        maps.fill_tpdo_map(tpdo, safe_dict)

        assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
        assert tpdo.items[0].size_bits == 8

        assert tpdo.items[1].register.identifier == "TEST_SI_U16"
        assert tpdo.items[1].size_bits == 16

        assert tpdo.items[2].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
        assert tpdo.items[2].size_bits == 16

        # Variable cut to what fills on the slot (16 bits of 32 bits, 16 remaining)
        assert tpdo.items[3].register.identifier == "FSOE_SAFE_POSITION"
        assert tpdo.items[3].size_bits == 16

        assert tpdo.items[4].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC1"
        assert tpdo.items[4].size_bits == 16

        # On this padding, the 32-bit variable will continue to be transmitted
        # (16 bits of 32 bits, 16 remaining)
        assert tpdo.items[5].register.identifier == "PADDING"
        assert tpdo.items[5].size_bits == 16

        assert tpdo.items[6].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC2"
        assert tpdo.items[6].size_bits == 16

        assert tpdo.items[7].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
        assert tpdo.items[7].size_bits == 16

        assert len(tpdo.items) == 8

        rpdo = RPDOMap()
        maps.fill_rpdo_map(rpdo, safe_dict)

        recreated_pdu_maps = PDUMaps.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
        assert (
            recreated_pdu_maps.outputs.get_text_representation()
            == maps.outputs.get_text_representation()
        )
        assert (
            recreated_pdu_maps.inputs.get_text_representation()
            == maps.inputs.get_text_representation()
        )

    @pytest.mark.fsoe
    @pytest.mark.parametrize("unify_pdo_mapping", [True, False])
    def test_map_with_16_bit_vars_offset_8(self, sample_safe_dictionary, unify_pdo_mapping: bool):
        safe_dict, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        # Add a first 8-bit variable that will shift the 16-bit variable
        maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U8_UID])
        # Append a 32-bit variable
        maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U16_UID])

        # Create the rpdo map
        tpdo = TPDOMap()
        maps.fill_tpdo_map(tpdo, safe_dict)

        assert tpdo.items[0].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CMD"
        assert tpdo.items[0].size_bits == 8

        assert tpdo.items[1].register.identifier == "TEST_SI_U8"
        assert tpdo.items[1].size_bits == 8

        # Variable cut to what fills on the slot (8 bits of 16 bits, 8 remaining)
        assert tpdo.items[2].register.identifier == "TEST_SI_U16"
        assert tpdo.items[2].size_bits == 8

        assert tpdo.items[3].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC0"
        assert tpdo.items[3].size_bits == 16

        # On this padding, the 32-bit variable will continue to be transmitted
        # (8 bits of 16 bits, 0 remaining)
        assert tpdo.items[4].register.identifier == "PADDING"
        assert tpdo.items[4].size_bits == 8

        # Additional padding added automatically, not explicitly on the map
        assert tpdo.items[5].register.identifier == "PADDING"
        assert tpdo.items[5].size_bits == 8

        assert tpdo.items[6].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CRC1"
        assert tpdo.items[6].size_bits == 16

        assert tpdo.items[7].register.identifier == "FSOE_SLAVE_FRAME_ELEM_CONNID"
        assert tpdo.items[7].size_bits == 16

        assert len(tpdo.items) == 8

        # The 2 8-bit padding, virtual and non-virtual may come unified
        # It should produce the same result
        if unify_pdo_mapping:
            tpdo.items[4].size_bits = 16  # Expand previous
            del tpdo.items[5]  # Remove the other padding

        rpdo = RPDOMap()
        maps.fill_rpdo_map(rpdo, safe_dict)

        recreated_pdu_maps = PDUMaps.from_rpdo_tpdo(rpdo, tpdo, fsoe_dict)
        assert (
            recreated_pdu_maps.outputs.get_text_representation()
            == maps.outputs.get_text_representation()
        )
        assert (
            recreated_pdu_maps.inputs.get_text_representation()
            == maps.inputs.get_text_representation()
        )

    @pytest.mark.fsoe
    @pytest.mark.parametrize(
        "pdo_length, frame_data_bytes",
        [
            (6, (1,)),
            (7, (1, 2)),
            (11, (1, 2, 5, 6)),
            (15, (1, 2, 5, 6, 9, 10)),
            (19, (1, 2, 5, 6, 9, 10, 13, 14)),
        ],
    )
    def test_get_safety_bytes_range_from_pdo_length(self, pdo_length, frame_data_bytes):
        assert frame_data_bytes == PDUMaps._PDUMaps__get_safety_bytes_range_from_pdo_length(
            pdo_length
        )

    @pytest.mark.fsoe
    def test_insert_in_best_position(self, sample_safe_dictionary):
        _safe_dict, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        si = fsoe_dict.name_map[SafeInputsFunction.SAFE_INPUTS_UID]
        sp = fsoe_dict.name_map["FSOE_SAFE_POSITION"]
        sto = fsoe_dict.name_map[STOFunction.COMMAND_UID]

        maps.insert_in_best_position(sto)
        maps.insert_in_best_position(sp)
        maps.insert_in_best_position(si)

        assert maps.inputs.get_text_representation(item_space=30) == (
            "Item                           | Position bytes..bits | Size bytes..bits    \n"
            "FSOE_STO                       | 0..0                 | 0..1                \n"
            "FSOE_SAFE_INPUTS_VALUE         | 0..1                 | 0..1                \n"
            "Padding                        | 0..2                 | 1..6                \n"
            "FSOE_SAFE_POSITION             | 2..0                 | 4..0                "
        )

        assert maps.outputs.get_text_representation(item_space=30) == (
            "Item                           | Position bytes..bits | Size bytes..bits    \n"
            "FSOE_STO                       | 0..0                 | 0..1                "
        )

    @pytest.mark.fsoe
    def test_validate_safe_data_blocks_invalid_size(self, mocker, sample_safe_dictionary):
        """Test that SafeDataBlocksValidator fails when safe data blocks are not 16 bits."""
        _, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        # Create a map with safe data blocks that are not 16 bits
        test_st_u8_item = maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U8_UID])  # 8 bits

        # Use a dummy slot width to simulate that the safe data block is wrongly sized
        dummy_slot_width = 2
        mocker.patch(
            "ingeniamotion.fsoe_master.maps.FSoEFrame._FSoEFrame__SLOT_WIDTH", dummy_slot_width
        )
        # Only validate the safe data blocks rule
        output = maps.are_inputs_valid(rules=[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID])
        assert len(output.exceptions) == 1
        assert FSoEFrameRules.SAFE_DATA_BLOCKS_VALID in output.exceptions
        exception = output.exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID]
        assert isinstance(exception, InvalidFSoEFrameRule)
        assert f"Safe data block 0 must be 16 bits. Found {dummy_slot_width}" in exception.exception
        assert exception.items == [test_st_u8_item]
        assert output.is_rule_valid(FSoEFrameRules.SAFE_DATA_BLOCKS_VALID) is False

    @pytest.mark.fsoe
    def test_validate_safe_data_blocks_pdu_empty(self, sample_safe_dictionary):
        """Test that SafeDataBlocksValidator passes when no safe data blocks are present."""
        _, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)
        output = maps.are_inputs_valid(rules=[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID])
        assert len(output.exceptions) == 0
        assert output.is_rule_valid(FSoEFrameRules.SAFE_DATA_BLOCKS_VALID) is True

    @pytest.mark.fsoe
    def test_validate_safe_data_blocks_too_many_blocks(self):
        """Test that SafeDataBlocksValidator fails when there are more than 8 safe data blocks."""
        # Add 9 different 16-bit safe inputs -> 9 blocks
        safe_dict = DictionaryFactory.create_dictionary(
            SAMPLE_SAFE_PH2_XDFV3_DICTIONARY, interface=Interface.ECAT
        )
        for idx in range(9):
            test_uid = f"TEST_SI_U16_{idx}"
            safe_dict._registers[self.AXIS_1][test_uid] = EthercatRegister(
                idx=0xF010 + idx,
                subidx=0,
                dtype=RegDtype.U16,
                access=RegAccess.RO,
                identifier=test_uid,
                pdo_access=RegCyclicType.SAFETY_INPUT,
                cat_id="FSOE",
            )
        # Check the CRCs that are already present in the sample dictionary and add the missing ones
        existing_crcs = [
            key
            for key in safe_dict._registers[self.AXIS_1]
            if key.startswith("FSOE_SLAVE_FRAME_ELEM_CRC")
        ]
        added_crc = 0
        for idx in range(9):
            crc_uid = f"FSOE_SLAVE_FRAME_ELEM_CRC{idx}"
            if crc_uid in existing_crcs:
                continue
            safe_dict._registers[self.AXIS_1][crc_uid] = EthercatRegister(
                idx=0x6760,
                subidx=len(existing_crcs) + added_crc,
                dtype=RegDtype.U16,
                access=RegAccess.RO,
                identifier=crc_uid,
                pdo_access=RegCyclicType.SAFETY_INPUT,
                cat_id="FSOE",
            )
            added_crc += 1
        # Create safe dictionary
        fsoe_dict = FSoEMasterHandler.create_safe_dictionary(safe_dict)

        maps = PDUMaps.empty(fsoe_dict)

        test_si_u16_items = []
        for idx in range(9):
            test_uid = f"TEST_SI_U16_{idx}"
            item = maps.inputs.add(fsoe_dict.name_map[test_uid])
            test_si_u16_items.append(item)

        output = maps.are_inputs_valid(rules=[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID])
        assert len(output.exceptions) == 1
        assert FSoEFrameRules.SAFE_DATA_BLOCKS_VALID in output.exceptions
        exception = output.exceptions[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID]
        assert isinstance(exception, InvalidFSoEFrameRule)
        assert "Expected 1-8 safe data blocks, found 9" in exception.exception
        assert exception.items == test_si_u16_items
        assert output.is_rule_valid(FSoEFrameRules.SAFE_DATA_BLOCKS_VALID) is False

    @pytest.mark.fsoe
    def test_validate_safe_data_blocks_objects_split_across_blocks(self, sample_safe_dictionary):
        """Test that SafeDataBlocksValidator fails when <= 16 bits objects are split."""
        _, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        maps.inputs.add_padding(bits=6)
        maps.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
        maps.inputs.add(fsoe_dict.name_map["FSOE_SS2_1"])
        test_si_u8_item = maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U8_UID])

        # Test that rule fails because the 8-bit object is split across blocks
        output = maps.are_inputs_valid(rules=[FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED])
        assert len(output.exceptions) == 1
        assert FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED in output.exceptions
        exception = output.exceptions[FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED]
        assert isinstance(exception, InvalidFSoEFrameRule)
        assert exception.exception == (
            "Make sure that 8 bit objects belong to the same data block. "
            f"Data slot 0 contains split object {test_si_u8_item.item.name}."
        )
        assert exception.items == [test_si_u8_item]  # Split item
        assert output.is_rule_valid(FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED) is False

        # Test that rule passes when the object is not split
        maps.inputs.clear()
        maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        maps.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
        maps.inputs.add(fsoe_dict.name_map["FSOE_SS2_1"])
        maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U8_UID])
        output = maps.are_inputs_valid(rules=[FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED])
        assert not output.exceptions
        assert output.is_rule_valid(FSoEFrameRules.OBJECTS_SPLIT_RESTRICTED) is True

    @pytest.mark.fsoe
    def test_validate_safe_data_blocks_valid_cases(self, sample_safe_dictionary):
        """Test that SafeDataBlocksValidator passes for valid safe data block configurations."""
        _, fsoe_dict = sample_safe_dictionary

        for items_to_add in [
            [self.TEST_SI_U8_UID],  # single 8-bit block
            [self.TEST_SI_U16_UID],  # single 16-bit block
            [self.TEST_SI_U16_UID, "FSOE_SAFE_POSITION"],  # multiple 16-bit blocks
        ]:
            maps = PDUMaps.empty(fsoe_dict)
            for item_uid in items_to_add:
                maps.inputs.add(fsoe_dict.name_map[item_uid])

            output = maps.are_inputs_valid(rules=[FSoEFrameRules.SAFE_DATA_BLOCKS_VALID])
            assert FSoEFrameRules.SAFE_DATA_BLOCKS_VALID not in output.exceptions
            assert output.is_rule_valid(FSoEFrameRules.SAFE_DATA_BLOCKS_VALID) is True

    @pytest.mark.fsoe
    def test_validate_number_of_objects_in_frame(self, sample_safe_dictionary):
        """Test that SafeDataBlocksValidator fails if the number of objects is exceeded."""
        safe_dict, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        for idx in range(45):
            test_uid = f"TEST_SI_BOOL_{idx}"
            safe_dict._registers[self.AXIS_1][test_uid] = EthercatRegister(
                idx=0xF010 + idx,
                subidx=0,
                dtype=RegDtype.BOOL,
                access=RegAccess.RO,
                identifier=test_uid,
                pdo_access=RegCyclicType.SAFETY_INPUT,
                cat_id="FSOE",
            )
        # Check the CRCs that are already present in the sample dictionary and add the missing ones
        existing_crcs = [
            key
            for key in safe_dict._registers[self.AXIS_1]
            if key.startswith("FSOE_SLAVE_FRAME_ELEM_CRC")
        ]
        added_crc = 0
        for idx in range(45):
            crc_uid = f"FSOE_SLAVE_FRAME_ELEM_CRC{idx}"
            if crc_uid in existing_crcs:
                continue
            safe_dict._registers[self.AXIS_1][crc_uid] = EthercatRegister(
                idx=0x6760,
                subidx=len(existing_crcs) + added_crc,
                dtype=RegDtype.U16,
                access=RegAccess.RO,
                identifier=crc_uid,
                pdo_access=RegCyclicType.SAFETY_INPUT,
                cat_id="FSOE",
            )
            added_crc += 1
        # Create safe dictionary
        fsoe_dict = FSoEMasterHandler.create_safe_dictionary(safe_dict)

        maps = PDUMaps.empty(fsoe_dict)

        test_si_bool_items = []
        for idx in range(45):
            test_uid = f"TEST_SI_BOOL_{idx}"
            item = maps.inputs.add(fsoe_dict.name_map[test_uid])
            test_si_bool_items.append(item)

        # Expected data blocks
        # CMD + DATA BLOCKS + CRC + CONNID
        data_blocks = FSoEFrame.generate_slot_structure(
            dict_map=maps.inputs, slot_width=FSoEFrame._FSoEFrame__SLOT_WIDTH
        )
        expected_crcs = len(list(data_blocks))
        n_objects = 1 + len(maps.inputs) + expected_crcs + 1

        output = maps.are_inputs_valid(
            rules=[FSoEFrameRules.OBJECTS_IN_FRAME, FSoEFrameRules.SAFE_DATA_BLOCKS_VALID]
        )
        assert len(output.exceptions) == 1
        assert FSoEFrameRules.SAFE_DATA_BLOCKS_VALID not in output.exceptions
        assert FSoEFrameRules.OBJECTS_IN_FRAME in output.exceptions
        exception = output.exceptions[FSoEFrameRules.OBJECTS_IN_FRAME]
        assert isinstance(exception, InvalidFSoEFrameRule)
        assert exception.exception == (f"Total objects in frame exceeds limit: {n_objects} > 45")
        assert exception.items == test_si_bool_items
        assert output.is_rule_valid(FSoEFrameRules.OBJECTS_IN_FRAME) is False

    @pytest.mark.fsoe
    def test_validate_safe_data_objects_word_aligned(self, sample_safe_dictionary):
        """Test that validation fails when safe data objects >= 16 bits are not word aligned."""
        _, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)

        maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U8_UID])
        test_si_u16_item = maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U16_UID])

        output = maps.are_inputs_valid(rules=[FSoEFrameRules.OBJECTS_ALIGNED])
        assert len(output.exceptions) == 1
        assert FSoEFrameRules.OBJECTS_ALIGNED in output.exceptions
        exception = output.exceptions[FSoEFrameRules.OBJECTS_ALIGNED]
        assert isinstance(exception, InvalidFSoEFrameRule)
        assert exception.exception == (
            "Objects larger than 16-bit must be word-aligned. "
            f"Object '{test_si_u16_item.item.name}' found at position 8, "
            f"next alignment is at 16."
        )
        assert exception.items == [test_si_u16_item]
        assert output.is_rule_valid(FSoEFrameRules.OBJECTS_ALIGNED) is False

        # Check that the rule passes when the object is word-aligned
        maps.inputs.clear()
        maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U8_UID])
        maps.inputs.add_padding(bits=8)
        maps.inputs.add(fsoe_dict.name_map[self.TEST_SI_U16_UID])
        output = maps.are_inputs_valid(rules=[FSoEFrameRules.OBJECTS_ALIGNED])
        assert not output.exceptions
        assert output.is_rule_valid(FSoEFrameRules.OBJECTS_ALIGNED) is True

    @pytest.mark.fsoe
    def test_validate_sto_command_first_in_outputs(self, sample_safe_dictionary):
        """Test that STO command is the first item in the maps."""
        _, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)
        ss1_item_outputs = maps.outputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
        maps.outputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        # STO command can be anywhere in the inputs map
        ss1_item_inputs = maps.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
        maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])

        output = maps.are_outputs_valid(rules=[FSoEFrameRules.STO_COMMAND_FIRST])
        assert len(output.exceptions) == 1
        assert FSoEFrameRules.STO_COMMAND_FIRST in output.exceptions
        exception = output.exceptions[FSoEFrameRules.STO_COMMAND_FIRST]
        assert isinstance(exception, InvalidFSoEFrameRule)
        assert "STO command must be mapped to the first position" in exception.exception
        assert exception.items == [ss1_item_outputs]
        assert output.is_rule_valid(FSoEFrameRules.STO_COMMAND_FIRST) is False

        output = maps.are_inputs_valid(rules=[FSoEFrameRules.STO_COMMAND_FIRST])
        assert len(output.exceptions) == 1
        assert FSoEFrameRules.STO_COMMAND_FIRST in output.exceptions
        exception = output.exceptions[FSoEFrameRules.STO_COMMAND_FIRST]
        assert isinstance(exception, InvalidFSoEFrameRule)
        assert "STO command must be mapped to the first position" in exception.exception
        assert exception.items == [ss1_item_inputs]
        assert output.is_rule_valid(FSoEFrameRules.STO_COMMAND_FIRST) is False

        maps.outputs.clear()
        maps.outputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        maps.outputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
        output = maps.are_outputs_valid(rules=[FSoEFrameRules.STO_COMMAND_FIRST])
        assert not output.exceptions
        assert output.is_rule_valid(FSoEFrameRules.STO_COMMAND_FIRST) is True

        maps.inputs.clear()
        maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        maps.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID.format(i=1)])
        output = maps.are_inputs_valid(rules=[FSoEFrameRules.STO_COMMAND_FIRST])
        assert not output.exceptions
        assert output.is_rule_valid(FSoEFrameRules.STO_COMMAND_FIRST) is True

    @pytest.mark.fsoe
    def test_validate_empty_map(self, sample_safe_dictionary):
        """Test that an empty FSoE map is invalid."""
        _, fsoe_dict = sample_safe_dictionary
        maps = PDUMaps.empty(fsoe_dict)
        output = maps.are_outputs_valid()
        assert FSoEFrameRules.STO_COMMAND_FIRST in output.exceptions
        output = maps.are_inputs_valid()
        assert FSoEFrameRules.STO_COMMAND_FIRST in output.exceptions

    @pytest.mark.fsoe
    def test_validate_dictionary_map_fsoe_frame_rules(self, sample_safe_dictionary):
        """Test that FSoE frames pass all validation rules."""
        _, fsoe_dict = sample_safe_dictionary

        maps = PDUMaps.empty(fsoe_dict)
        maps.outputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        maps.outputs.add_padding(7)
        maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        maps.inputs.add_padding(7)

        is_valid = maps.validate()
        assert is_valid is True

    @pytest.mark.fsoe
    def test_insert_safety_function(self):
        handler = MockHandler(SAMPLE_SAFE_PH1_XDFV3_DICTIONARY, 0x3800000)

        sto_func = None
        for sf in SafetyFunction.for_handler(handler):
            if isinstance(sf, STOFunction):
                sto_func = sf
        if not sto_func:
            raise ValueError("STO not found")

        maps = PDUMaps.empty(handler.dictionary)
        maps.insert_safety_function(sto_func)
        assert maps.inputs.get_text_representation(item_space=30) == (
            "Item                           | Position bytes..bits | Size bytes..bits    \n"
            "FSOE_STO                       | 0..0                 | 0..1                "
        )
        assert maps.outputs.get_text_representation(item_space=30) == (
            "Item                           | Position bytes..bits | Size bytes..bits    \n"
            "FSOE_STO                       | 0..0                 | 0..1                "
        )

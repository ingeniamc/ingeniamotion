import time
from typing import TYPE_CHECKING

import pytest
from ingenialink import RegAccess, RegDtype
from ingenialink.dictionary import DictionaryV3, Interface
from ingenialink.enums.register import RegCyclicType
from ingenialink.ethercat.register import EthercatRegister
from ingenialink.pdo import RPDOMap, TPDOMap

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEError, FSoEMaster
from ingeniamotion.motion_controller import MotionController
from tests.conftest import timeout_loop
from tests.dictionaries import SAMPLE_SAFE_DICTIONARY

if FSOE_MASTER_INSTALLED:
    from fsoe_master import fsoe_master

    from ingeniamotion.fsoe_master import (
        FSoEMasterHandler,
        PDUMaps,
        SafeInputsFunction,
        SS1Function,
        STOFunction,
    )


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


def error_handler(error: FSoEError):
    raise RuntimeError(f"FSoE error received: {error}")


@pytest.fixture()
def mc_with_fsoe(mc):
    # Subscribe to emergency messages
    mc.communication.subscribe_emergency_message(emergency_handler)
    # Configure error channel
    mc.fsoe.subscribe_to_errors(error_handler)
    # Create and start the FSoE master handler
    handler = mc.fsoe.create_fsoe_master_handler(use_sra=False)
    yield mc, handler
    # IM should be notified and clear references when a servo is disconnected from ingenialink
    # https://novantamotion.atlassian.net/browse/INGM-624
    mc.fsoe._delete_master_handler()


@pytest.mark.fsoe
def test_creste_fsoe_master_handler(mc, alias):
    master = FSoEMaster(mc)

    safety_module = master._FSoEMaster__get_safety_module(servo=alias)

    if safety_module.uses_sra:
        master.create_fsoe_master_handler(use_sra=False)
        new_safety_module = master._FSoEMaster__get_safety_module(servo=alias)
        assert new_safety_module.uses_sra is False

    else:
        # https://novantamotion.atlassian.net/browse/INGM-621
        with pytest.raises(NotImplementedError, match="Safety module with SRA is not available."):
            master.create_fsoe_master_handler(use_sra=True)
        new_safety_module = master._FSoEMaster__get_safety_module(servo=alias)
        assert new_safety_module.uses_sra is True


@pytest.mark.fsoe
def test_fsoe_master_get_safety_parameters(mc_with_fsoe):
    mc, handler = mc_with_fsoe

    assert len(handler.safety_parameters) != 0


@pytest.mark.fsoe
def test_mandatory_safety_functions(mc_with_fsoe):
    mc, handler = mc_with_fsoe

    safety_functions_by_types = handler.safety_functions_by_type()

    sto_instances = safety_functions_by_types[STOFunction]
    assert len(sto_instances) == 1

    ss1_instances = safety_functions_by_types[SS1Function]
    assert len(ss1_instances) >= 1

    si_instances = safety_functions_by_types[SafeInputsFunction]
    assert len(si_instances) == 1


@pytest.mark.fsoe
def test_getter_of_safety_functions(mc_with_fsoe):
    mc, handler = mc_with_fsoe

    sto_function = STOFunction(command=None, io=None, parameters=None)
    ss1_function_1 = SS1Function(command=None, time_to_sto=None, io=None, parameters=None)
    ss1_function_2 = SS1Function(command=None, time_to_sto=None, io=None, parameters=None)

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


@pytest.fixture()
def mc_state_data(mc_with_fsoe):
    mc, handler = mc_with_fsoe

    mc.fsoe.configure_pdos(start_pdos=True)
    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=10)

    yield mc

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
def test_start_and_stop_multiple_times(mc_with_fsoe):
    mc, handler = mc_with_fsoe

    # Any fsoe error during the start/stop process
    # will fail the test because of error_handler

    for i in range(4):
        mc.fsoe.configure_pdos(start_pdos=True)
        mc.fsoe.wait_for_state_data(timeout=10)
        assert handler.state == FSoEState.DATA
        time.sleep(1)
        assert handler.state == FSoEState.DATA
        mc.fsoe.stop_master(stop_pdos=True)


@pytest.mark.fsoe
def test_safe_inputs_value(mc_state_data):
    mc = mc_state_data

    value = mc.fsoe.get_safety_inputs_value()

    # Assume safe inputs are disconnected on the setup
    assert value == 0


@pytest.mark.fsoe
def test_safety_address(mc_with_fsoe, alias):
    mc, handler = mc_with_fsoe

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
    mc, handler = mc_with_fsoe

    # Master state is obtained as function
    # and not on the parametrize
    # to avoid depending on the optionally installed module
    # on pytest collection
    fsoe_master_state = mc_state_to_fsoe_master_state(state_enum)

    mocker.patch("fsoe_master.fsoe_master.MasterHandler.state", fsoe_master_state)

    assert mc.fsoe.get_fsoe_master_state() == state_enum


@pytest.mark.fsoe
def test_motor_enable(mc_state_data):
    mc = mc_state_data

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
    mc.fsoe.sto_activate()
    # Activate the STO
    mc.fsoe.sto_activate()


@pytest.mark.fsoe
def test_copy_modify_and_set_map(mc_with_fsoe):
    mc, handler = mc_with_fsoe

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
        safe_dict = DictionaryV3(SAMPLE_SAFE_DICTIONARY, interface=Interface.ECAT)

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
        maps.outputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID])
        maps.outputs.add_padding(bits=6 + 8)

        maps.inputs.add(fsoe_dict.name_map[STOFunction.COMMAND_UID])
        maps.inputs.add(fsoe_dict.name_map[SS1Function.COMMAND_UID])
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
        safe_dict, fsoe_dict = sample_safe_dictionary
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
            "Padding                        | 0..2                 | 0..6                \n"
            "FSOE_SAFE_POSITION             | 1..0                 | 4..0                "
        )

        assert maps.outputs.get_text_representation(item_space=30) == (
            "Item                           | Position bytes..bits | Size bytes..bits    \n"
            "FSOE_STO                       | 0..0                 | 0..1                "
        )

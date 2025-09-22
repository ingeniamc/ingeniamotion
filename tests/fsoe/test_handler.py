import logging
import random
import time
from typing import TYPE_CHECKING, Callable

import pytest
from ingenialink.dictionary import DictionarySafetyModule
from ingenialink.ethercat.network import EthercatNetwork

from ingeniamotion.enums import FSoEState
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED, FSoEError, FSoEMaster
from tests.dictionaries import SAMPLE_SAFE_PH1_XDFV3_DICTIONARY, SAMPLE_SAFE_PH2_XDFV3_DICTIONARY
from tests.fsoe.conftest import MockNetwork, MockServo

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master.fsoe import FSoEApplicationParameter
    from ingeniamotion.fsoe_master.handler import FSoEMasterHandler

if TYPE_CHECKING:
    from ingenialink.ethercat.servo import EthercatServo

    from ingeniamotion.motion_controller import MotionController


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
            logger_error.message
            == "Error creating FSoE Process Image from RPDO and TPDO on the drive. "
            "Falling back to a default map."
        )

        # And the default minimal map is used
        assert len(handler.process_image.inputs) == 1
        assert len(handler.process_image.outputs) == 1
        assert handler.process_image.outputs[0].item.name == "FSOE_STO"
    finally:
        handler.delete()


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


@pytest.mark.fsoe
def test_handler_is_stopped_if_error_in_pdo_thread(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    fsoe_states: list["FSoEState"],
    mocker,
):
    def mock_send_receive_processdata(*args, **kwargs):
        raise RuntimeError("Test error in PDO thread")

    mc, handler = mc_with_fsoe_with_sra

    mc.fsoe.configure_pdos(start_pdos=True, start_master=True)

    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)
    assert fsoe_states[-1] == FSoEState.DATA
    assert handler.running is True

    # Force an error in data state and verify that the handler is stopped
    mocker.patch.object(
        EthercatNetwork,
        "send_receive_processdata",
        side_effect=mock_send_receive_processdata,
    )
    time.sleep(1.0)
    assert handler.running is False
    assert fsoe_states[-1] == FSoEState.RESET


@pytest.mark.fsoe
def test_safety_pdo_map_subscription(
    mc_with_fsoe_with_sra: tuple["MotionController", "FSoEMasterHandler"],
    timeout_for_data_sra: float,
    servo: "EthercatServo",
):
    mc, handler = mc_with_fsoe_with_sra

    # Handler not subscribed if PDO maps are not set and no PDO map is mapped
    assert not handler._FSoEMasterHandler__is_subscribed_to_process_data_events
    assert servo._rpdo_maps == {}
    assert servo._tpdo_maps == {}

    # Handler is subscribed after configuring the PDO maps
    # PDO maps are set but not yet started
    mc.fsoe.configure_pdos(start_pdos=False)
    assert handler._FSoEMasterHandler__is_subscribed_to_process_data_events
    assert servo._rpdo_maps == {
        handler.safety_master_pdu_map.map_register_index: handler.safety_master_pdu_map
    }
    assert servo._tpdo_maps == {
        handler.safety_slave_pdu_map.map_register_index: handler.safety_slave_pdu_map
    }

    mc.fsoe.start_master()
    mc.capture.pdo.start_pdos()
    mc.fsoe.wait_for_state_data(timeout=timeout_for_data_sra)

    # Handler remains subscribed while in Data state
    assert handler._FSoEMasterHandler__is_subscribed_to_process_data_events

    # Stop the master, handler unsubscribes but the PDO maps remain
    mc.fsoe.stop_master(stop_pdos=False)
    assert not handler._FSoEMasterHandler__is_subscribed_to_process_data_events
    assert servo._rpdo_maps == {
        handler.safety_master_pdu_map.map_register_index: handler.safety_master_pdu_map
    }
    assert servo._tpdo_maps == {
        handler.safety_slave_pdu_map.map_register_index: handler.safety_slave_pdu_map
    }

    mc.capture.pdo.stop_pdos()

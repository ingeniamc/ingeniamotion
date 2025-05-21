from typing import TYPE_CHECKING

import pytest

from ingeniamotion.fsoe import FSoEError, FSoEMaster
from ingeniamotion.motion_controller import MotionController

if TYPE_CHECKING:
    from ingenialink.emcy import EmergencyMessage


@pytest.mark.virtual
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


@pytest.mark.fsoe
@pytest.mark.smoke
def test_fsoe_master_get_application_parameters(setup_descriptor):
    mc = MotionController()
    assert isinstance(mc.fsoe, FSoEMaster)
    servo = setup_descriptor.identifier
    mc.communication.connect_servo_ethercat(
        interface_name=setup_descriptor.ifname,
        slave_id=setup_descriptor.slave,
        dict_path=setup_descriptor.dictionary,
        alias=servo,
    )
    application_parameters = mc.fsoe._get_application_parameters(servo=servo)
    assert len(application_parameters)


def emergency_handler(servo_alias: str, message: "EmergencyMessage"):
    if message.error_code == 0xFF43:
        # Cyclic timeout Ethercat PDO lifeguard
        # is a typical error code when the pdos are stopped
        # Ignore
        return
    raise RuntimeError(f"Emergency message received from {servo_alias}: {message}")


def error_handler(error: FSoEError):
    raise RuntimeError(f"FSoE error received: {error}")


@pytest.mark.fsoe
@pytest.mark.smoke
def test_deactivate_sto(mc):
    mc.communication.subscribe_emergency_message(emergency_handler)

    # Configure error channel
    mc.fsoe.subscribe_to_errors(error_handler)
    # Connect to the servo drive
    # Create and start the FSoE master handler
    mc.fsoe.create_fsoe_master_handler()
    mc.fsoe.configure_pdos(start_pdos=True)
    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=10)
    # Deactivate the SS1
    mc.fsoe.ss1_deactivate()
    # Deactivate the STO
    mc.fsoe.sto_deactivate()
    # Wait for the STO to be deactivated
    while mc.fsoe.check_sto_active():
        pass
    # Enable the motor
    mc.motion.motor_enable()
    # Disable the motor
    mc.motion.motor_disable()
    # Activate the SS1
    mc.fsoe.sto_activate()
    # Activate the STO
    mc.fsoe.sto_activate()
    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)

    # https://novantamotion.atlassian.net/browse/INGM-624
    mc.fsoe._delete_master_handler()

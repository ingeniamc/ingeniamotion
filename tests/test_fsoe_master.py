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


@pytest.mark.fsoe
@pytest.mark.smoke
def test_fsoe_master_get_application_parameters(mc, alias):
    assert isinstance(mc.fsoe, FSoEMaster)

    application_parameters = mc.fsoe._get_application_parameters(servo=alias)
    assert len(application_parameters)


@pytest.fixture()
def mc_with_fsoe(mc):
    # Subscribe to emergency messages
    mc.communication.subscribe_emergency_message(emergency_handler)
    # Configure error channel
    mc.fsoe.subscribe_to_errors(error_handler)
    # Create and start the FSoE master handler
    mc.fsoe.create_fsoe_master_handler()
    yield mc
    # IM should be notified and clear references when a servo is disconnected from ingenialink
    # https://novantamotion.atlassian.net/browse/INGM-624
    mc.fsoe._delete_master_handler()


@pytest.mark.fsoe
@pytest.mark.smoke
def test_deactivate_sto(mc_with_fsoe):
    mc = mc_with_fsoe

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

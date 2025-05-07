import pytest

from ingeniamotion.fsoe import FSoEMaster
from ingeniamotion.motion_controller import MotionController


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

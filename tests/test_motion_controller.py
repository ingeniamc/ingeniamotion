import pytest

from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode
from ingeniamotion.capture import Capture
from ingeniamotion.configuration import Configuration
from ingeniamotion.motion import Motion
from ingeniamotion.communication import Communication
from ingeniamotion.drive_tests import DriveTests
from ingeniamotion.errors import Errors
from ingeniamotion.information import Information


@pytest.mark.smoke
def test_motion_controller():
    mc = MotionController()
    assert isinstance(mc.configuration, Configuration)
    assert isinstance(mc.motion, Motion)
    assert isinstance(mc.capture, Capture)
    assert isinstance(mc.communication, Communication)
    assert isinstance(mc.tests, DriveTests)
    assert isinstance(mc.errors, Errors)
    assert isinstance(mc.info, Information)


@pytest.mark.smoke
def test_servo_name(motion_controller):
    mc, alias = motion_controller
    prod_code = mc.servos[alias].info["product_code"]
    servo_arg = () if alias == "default" else (alias,)
    name = mc.servo_name(*servo_arg)
    assert name == "{} ({})".format(prod_code, alias)


@pytest.mark.smoke
def test_get_register_enum(motion_controller):
    mc, alias = motion_controller
    servo_arg = () if alias == "default" else (alias,)
    operation_mode_enum = mc.get_register_enum("DRV_OP_VALUE", *servo_arg)
    operation_mode_values = [op.value for op in operation_mode_enum]
    checked_ops = 0
    for element in OperationMode:
        if element.value in operation_mode_values:
            test_name = operation_mode_enum(element.value).name.replace("-", " ")
            name = element.name.replace("_", " ")
            assert test_name.upper() == name
            checked_ops += 1

    assert checked_ops > 0


@pytest.mark.smoke
def test_is_alive(motion_controller):
    mc, alias = motion_controller
    assert mc.is_alive(alias)

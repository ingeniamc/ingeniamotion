import pytest

from ingeniamotion.exceptions import IMStatusWordError
from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode
from ingeniamotion.capture import Capture
from ingeniamotion.configuration import Configuration
from ingeniamotion.motion import Motion
from ingeniamotion.communication import Communication
from ingeniamotion.drive_tests import DriveTests
from ingeniamotion.errors import Errors
from ingeniamotion.information import Information
from ingeniamotion.metaclass import MCMetaClass


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


@pytest.mark.no_connection
class TestMetaclass:
    class DummyClass(metaclass=MCMetaClass):
        mc = MotionController()

        def is_motor_enabled(self, servo: str, axis: int):
            return servo == "a" and axis == 1

        def __init__(self):
            self.mc.servos = ["a", "b"]
            self.mc.configuration.is_motor_enabled = self.is_motor_enabled

        @MCMetaClass.check_motor_disabled
        def dummy_func(self, servo: str, axis: int):
            pass

    @pytest.mark.no_connection
    @pytest.mark.parametrize(
        "servo, axis, error",
        [
            ("a", 1, IMStatusWordError),
            ("b", 1, None),
            ("c", 1, KeyError),
            ("a", 2, None),
        ],
    )
    def test_check_motor_disabled_keyword_parameters(self, servo, axis, error):
        dummy_class = self.DummyClass()
        if error is None:
            dummy_class.dummy_func(servo=servo, axis=axis)
        else:
            with pytest.raises(error):
                dummy_class.dummy_func(servo=servo, axis=axis)

    @pytest.mark.no_connection
    @pytest.mark.parametrize(
        "servo, axis, error",
        [
            ("a", 1, IMStatusWordError),
            ("b", 1, None),
            ("c", 1, KeyError),
            ("a", 2, None),
        ],
    )
    def test_check_motor_disabled_positional_parameters(self, servo, axis, error):
        dummy_class = self.DummyClass()
        if error is None:
            dummy_class.dummy_func(servo, axis)
        else:
            with pytest.raises(error):
                dummy_class.dummy_func(servo, axis)

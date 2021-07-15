from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode


def test_motion_controller():
    MotionController()


def test_servo_name(servo_default):
    mc = servo_default
    prod_code = mc.servos["default"].info["prod_code"]
    name = mc.servo_name()
    assert name == "{} (default)".format(prod_code)


def test_get_register_enum(servo_default):
    mc = servo_default
    operation_mode_enum = mc.get_register_enum("DRV_OP_VALUE")
    for element in OperationMode:
        test_name = operation_mode_enum(element.value).name.replace("-", " ")
        name = element.name.replace("_", " ")
        assert test_name.upper() == name

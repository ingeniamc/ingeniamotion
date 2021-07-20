import pytest
from pytest_lazyfixture import lazy_fixture

from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode


def test_motion_controller():
    MotionController()


@pytest.mark.parametrize("mc, alias", [
    (lazy_fixture("servo_default"), "default"),
    (lazy_fixture("servo_test_name"), "test"),
])
def test_servo_name(mc, alias):
    prod_code = mc.servos[alias].info["prod_code"]
    servo_arg = () if alias == "default" else (alias,)
    name = mc.servo_name(*servo_arg)
    assert name == "{} ({})".format(prod_code, alias)


@pytest.mark.parametrize("mc, alias", [
    (lazy_fixture("servo_default"), "default"),
    (lazy_fixture("servo_test_name"), "test"),
])
def test_get_register_enum(mc, alias):
    servo_arg = () if alias == "default" else (alias,)
    operation_mode_enum = mc.get_register_enum("DRV_OP_VALUE", *servo_arg)
    for element in OperationMode:
        test_name = operation_mode_enum(element.value).name.replace("-", " ")
        name = element.name.replace("_", " ")
        assert test_name.upper() == name

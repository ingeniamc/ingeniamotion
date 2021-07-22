import pytest

from ingeniamotion import MotionController
from ingenialink.registers import REG_DTYPE


@pytest.mark.smoke
@pytest.mark.eoe
def test_connect_servo_eoe(read_config):
    mc = MotionController()
    eoe_config = read_config["eoe"]
    assert "eoe_test" not in mc.servos
    assert "eoe_test" not in mc.net
    mc.communication.connect_servo_eoe(
        eoe_config["ip"], eoe_config["dictionary"], alias="eoe_test")
    assert "eoe_test" in mc.servos and mc.servos["eoe_test"] is not None
    assert "eoe_test" in mc.net and mc.net["eoe_test"] is not None


@pytest.mark.develop
@pytest.mark.smoke
@pytest.mark.eoe
def test_connect_servo_eoe_no_dictionary_error(read_config):
    mc = MotionController()
    eoe_config = read_config["eoe"]
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_eoe(
            eoe_config["ip"], "no_dictionary", alias="eoe_test")


@pytest.mark.smoke
@pytest.mark.eoe
def test_connect_servo_ethernet(read_config):
    mc = MotionController()
    eoe_config = read_config["eoe"]
    assert "eoe_test" not in mc.servos
    assert "eoe_test" not in mc.net
    mc.communication.connect_servo_ethernet(
        eoe_config["ip"], eoe_config["dictionary"], alias="eoe_test")
    assert "eoe_test" in mc.servos and mc.servos["eoe_test"] is not None
    assert "eoe_test" in mc.net and mc.net["eoe_test"] is not None


@pytest.mark.develop
@pytest.mark.smoke
@pytest.mark.eoe
def test_connect_servo_ethernet_no_dictionary_error(read_config):
    mc = MotionController()
    eoe_config = read_config["eoe"]
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_ethernet(
            eoe_config["ip"], "no_dictionary", alias="eoe_test")


@pytest.mark.smoke
@pytest.mark.soem
def test_connect_servo_ecat(read_config):
    mc = MotionController()
    soem_config = read_config["soem"]
    assert "soem_test" not in mc.servos
    assert "soem_test" not in mc.net
    ifname = mc.communication.get_ifname_by_index(soem_config["index"])
    mc.communication.connect_servo_ecat(
        ifname, soem_config["dictionary"],
        slave=soem_config["slave"], alias="soem_test")
    assert "soem_test" in mc.servos and mc.servos["soem_test"] is not None
    assert "soem_test" in mc.net and mc.net["soem_test"] is not None


@pytest.mark.develop
@pytest.mark.smoke
@pytest.mark.soem
def test_connect_servo_ecat_no_dictionary_error(read_config):
    mc = MotionController()
    soem_config = read_config["soem"]
    ifname = mc.communication.get_ifname_by_index(soem_config["index"])
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_ecat(
            ifname, "no_dictionary",
            slave=soem_config["slave"], alias="soem_test")


@pytest.mark.smoke
@pytest.mark.soem
def test_connect_servo_ecat_interface_index(read_config):
    mc = MotionController()
    soem_config = read_config["soem"]
    assert "soem_test" not in mc.servos
    assert "soem_test" not in mc.net
    mc.communication.connect_servo_ecat_interface_index(
        soem_config["index"], soem_config["dictionary"],
        slave=soem_config["slave"], alias="soem_test")
    assert "soem_test" in mc.servos and mc.servos["soem_test"] is not None
    assert "soem_test" in mc.net and mc.net["soem_test"] is not None


@pytest.mark.develop
@pytest.mark.smoke
@pytest.mark.soem
def test_connect_servo_ecat_interface_index_no_dictionary_error(read_config):
    mc = MotionController()
    soem_config = read_config["soem"]
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_ecat_interface_index(
            soem_config["index"], "no_dictionary",
            slave=soem_config["slave"], alias="soem_test")


@pytest.mark.smoke
@pytest.mark.parametrize("uid, value", [
    ("CL_VOL_Q_SET_POINT", 0.34),
    ("CL_POS_SET_POINT_VALUE", -923),
    ("PROF_POS_OPTION_CODE", 1),
])
def test_get_register(motion_controller, uid, value):
    mc, alias = motion_controller
    drive = mc.servos[alias]
    drive.write(uid, value)
    test_value = mc.communication.get_register(uid, servo=alias)
    assert pytest.approx(test_value) == value


@pytest.mark.smoke
@pytest.mark.parametrize("uid, value", [
    ("CL_VOL_Q_SET_POINT", -234),
    ("CL_POS_SET_POINT_VALUE", 23),
    ("PROF_POS_OPTION_CODE", 54),
])
def test_set_register(motion_controller, uid, value):
    mc, alias = motion_controller
    drive = mc.servos[alias]
    mc.communication.set_register(uid, value, servo=alias)
    test_value = drive.read(uid)
    assert pytest.approx(test_value) == value


@pytest.mark.smoke
@pytest.mark.soem
@pytest.mark.parametrize("uid, index, subindex, dtype, value", [
    ("CL_VOL_Q_SET_POINT", 0x2018, 0, REG_DTYPE.FLOAT, -234),
    ("CL_POS_SET_POINT_VALUE", 0x2020, 0, REG_DTYPE.S32, 1245),
    ("PROF_POS_OPTION_CODE",  0x2024, 0, REG_DTYPE.U16, 54),
])
def test_get_sdo_register(motion_controller, uid, index, subindex, dtype, value):
    mc, alias = motion_controller
    mc.communication.set_register(uid, value, servo=alias)
    test_value = mc.communication.get_sdo_register(
        index, subindex, dtype, servo=alias)
    assert test_value == value


@pytest.mark.smoke
@pytest.mark.soem
@pytest.mark.parametrize("uid, index, subindex, dtype, value", [
    ("CL_VOL_Q_SET_POINT", 0x2018, 0, REG_DTYPE.FLOAT, -234),
    ("CL_POS_SET_POINT_VALUE", 0x2020, 0, REG_DTYPE.S32, 1245),
    ("PROF_POS_OPTION_CODE",  0x2024, 0, REG_DTYPE.U16, 54),
])
def test_set_sdo_register(motion_controller, uid, index, subindex, dtype, value):
    mc, alias = motion_controller
    mc.communication.set_sdo_register(
        index, subindex, dtype, value, servo=alias)
    test_value = mc.communication.get_register(
        uid, servo=alias)
    assert test_value == value

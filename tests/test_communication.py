import time
import pytest

from ingenialink.servo import SERVO_STATE
from ingenialink.exceptions import ILError

from ingeniamotion import MotionController
from ingeniamotion.exceptions import IMRegisterNotExist, IMRegisterWrongAccess
from ingeniamotion.enums import CAN_BAUDRATE, CAN_DEVICE, REG_DTYPE


@pytest.mark.smoke
@pytest.mark.eoe
def test_connect_servo_eoe(read_config):
    mc = MotionController()
    eoe_config = read_config["eoe"]
    assert "eoe_test" not in mc.servos
    assert "ethernet" not in mc.net
    mc.communication.connect_servo_eoe(
        eoe_config["ip"], eoe_config["dictionary"], alias="eoe_test")
    assert "eoe_test" in mc.servos and mc.servos["eoe_test"] is not None
    assert "ethernet" in mc.net and mc.net["ethernet"] is not None


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
    assert "ethernet" not in mc.net
    mc.communication.connect_servo_ethernet(
        eoe_config["ip"], eoe_config["dictionary"], alias="eoe_test")
    assert "eoe_test" in mc.servos and mc.servos["eoe_test"] is not None
    assert "ethernet" in mc.net and mc.net["ethernet"] is not None


@pytest.mark.smoke
@pytest.mark.eoe
def test_connect_servo_ethernet_no_dictionary_error(read_config):
    mc = MotionController()
    eoe_config = read_config["eoe"]
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_ethernet(
            eoe_config["ip"], "no_dictionary", alias="eoe_test")


@pytest.mark.skip(reason='This test enters in conflict with "motion_controller"')
@pytest.mark.smoke
@pytest.mark.soem
def test_connect_servo_ecat(read_config):
    mc = MotionController()
    soem_config = read_config["soem"]
    ifname = mc.communication.get_ifname_by_index(soem_config["index"])
    assert "soem_test" not in mc.servos
    assert ifname not in mc.net
    mc.communication.connect_servo_ecat(
        ifname, soem_config["dictionary"],
        slave=soem_config["slave"], alias="soem_test")
    assert "soem_test" in mc.servos and mc.servos["soem_test"] is not None
    assert ifname in mc.net and mc.net[ifname] is not None


@pytest.mark.smoke
@pytest.mark.soem
def test_get_ifname_from_interface_ip(mocker, read_config):
    ip = type('IP', (object,), {
        'ip': '192.168.2.1',
        'is_IPv4': True
    })
    adapter = type('Adapter', (object, ), {
        'ips': [ip],
        'name': b'{192D1D2F-C684-467D-A637-EC07BD434A63}'
    })
    mocker.patch('ifaddr.get_adapters', return_value=[adapter])
    mc = MotionController()
    soem_config = read_config["soem"]
    ifname = mc.communication.get_ifname_from_interface_ip(
        soem_config['interface_ip']
    )
    assert ifname == "\\Device\\NPF_{192D1D2F-C684-467D-A637-EC07BD434A63}"


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


@pytest.mark.skip(reason='This test enters in conflict with "motion_controller"')
@pytest.mark.smoke
@pytest.mark.soem
def test_connect_servo_ecat_interface_index(read_config):
    mc = MotionController()
    soem_config = read_config["soem"]
    ifname = mc.communication.get_ifname_by_index(soem_config["index"])
    assert "soem_test" not in mc.servos
    assert ifname not in mc.net
    mc.communication.connect_servo_ecat_interface_index(
        soem_config["index"], soem_config["dictionary"],
        slave=soem_config["slave"], alias="soem_test")
    assert "soem_test" in mc.servos and mc.servos["soem_test"] is not None
    assert ifname in mc.net and mc.net[ifname] is not None


@pytest.mark.smoke
@pytest.mark.soem
def test_connect_servo_ecat_interface_index_no_dictionary_error(read_config):
    mc = MotionController()
    soem_config = read_config["soem"]
    with pytest.raises(FileNotFoundError):
        mc.communication.connect_servo_ecat_interface_index(
            soem_config["index"], "no_dictionary",
            slave=soem_config["slave"], alias="soem_test")


@pytest.mark.skip(reason='This test enters in conflict with "disable_motor_fixture"')
@pytest.mark.smoke
@pytest.mark.canopen
def test_connect_servo_canopen(read_config):
    mc = MotionController()
    canopen_config = read_config["canopen"]
    assert "canopen_test" not in mc.servos
    assert "canopen_test" not in mc.net
    device = CAN_DEVICE(canopen_config["device"])
    baudrate = CAN_BAUDRATE(canopen_config["baudrate"])
    mc.communication.connect_servo_canopen(
        device, canopen_config["dictionary"], canopen_config["eds"],
        canopen_config["node_id"], baudrate, canopen_config["channel"],
        alias="canopen_test")
    assert "canopen_test" in mc.servos and mc.servos["canopen_test"] is not None
    assert "canopen_test" in mc.net and mc.net["canopen_test"] is not None
    mc.net["canopen_test"].disconnect()


@pytest.mark.smoke
@pytest.mark.canopen
@pytest.mark.skip
def test_connect_servo_canopen_busy_drive_error(motion_controller, read_config):
    mc, alias = motion_controller
    canopen_config = read_config["canopen"]
    assert "canopen_test" not in mc.servos
    assert "canopen_test" not in mc.servo_net
    assert alias in mc.servos
    assert alias in mc.servo_net
    assert mc.servo_net[alias] in mc.net
    device = CAN_DEVICE(canopen_config["device"])
    baudrate = CAN_BAUDRATE(canopen_config["baudrate"])
    with pytest.raises(ILError):
        mc.communication.connect_servo_canopen(
            device, canopen_config["dictionary"], canopen_config["eds"],
            canopen_config["node_id"], baudrate, canopen_config["channel"],
            alias="canopen_test")


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
def test_get_register_wrong_uid(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(IMRegisterNotExist):
        mc.communication.get_register("WRONG_UID", servo=alias)


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
def test_set_register_wrong_uid(motion_controller):
    mc, alias = motion_controller
    with pytest.raises(IMRegisterNotExist):
        mc.communication.set_register("WRONG_UID", 2, servo=alias)


@pytest.mark.smoke
@pytest.mark.parametrize("uid, value, fail", [
    ("CL_VOL_Q_SET_POINT", -234, False),
    ("CL_VOL_Q_SET_POINT", "I'm not a number", True),
    ("CL_VOL_Q_SET_POINT", 234.4, False),
    ("CL_POS_SET_POINT_VALUE", 1245, False),
    ("CL_POS_SET_POINT_VALUE", -1245, False),
    ("CL_POS_SET_POINT_VALUE", 1245.5421, True),
    ("PROF_POS_OPTION_CODE", -54, True),
    ("PROF_POS_OPTION_CODE", 54, False),
    ("PROF_POS_OPTION_CODE", "54", True),
])
def test_set_register_wrong_value_type(motion_controller, uid, value, fail):
    mc, alias = motion_controller
    if fail:
        with pytest.raises(TypeError):
            mc.communication.set_register(uid, value, servo=alias)
    else:
        mc.communication.set_register(uid, value, servo=alias)


@pytest.mark.smoke
def test_set_register_wrong_access(motion_controller):
    mc, alias = motion_controller
    uid = "DRV_STATE_STATUS"
    value = 0
    with pytest.raises(IMRegisterWrongAccess):
        mc.communication.set_register(uid, value, servo=alias)


@pytest.mark.smoke
@pytest.mark.soem
@pytest.mark.parametrize("uid, index, subindex, dtype, value", [
    ("CL_VOL_Q_SET_POINT", 0x2018, 0, REG_DTYPE.FLOAT, -234),
    ("CL_POS_SET_POINT_VALUE", 0x2020, 0, REG_DTYPE.S32, 1245),
    ("PROF_POS_OPTION_CODE", 0x2024, 0, REG_DTYPE.U16, 54),
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
    ("PROF_POS_OPTION_CODE", 0x2024, 0, REG_DTYPE.U16, 54),
])
def test_set_sdo_register(motion_controller, uid, index, subindex, dtype, value):
    mc, alias = motion_controller
    mc.communication.set_sdo_register(
        index, subindex, dtype, value, servo=alias)
    test_value = mc.communication.get_register(
        uid, servo=alias)
    assert test_value == value


def dummy_callback(status, _, axis):
    pass


def test_subscribe_servo_status(mocker, motion_controller):
    mc, alias = motion_controller
    axis = 1
    patch_callback = mocker.patch('tests.test_communication.dummy_callback')
    mc.communication.subscribe_servo_status(patch_callback, alias)
    time.sleep(0.5)
    mc.motion.motor_enable(alias, axis)
    time.sleep(0.5)
    mc.motion.motor_disable(alias, axis)
    time.sleep(0.5)
    expected_status = [
        SERVO_STATE.RDY,
        SERVO_STATE.ENABLED,
        SERVO_STATE.DISABLED
    ]
    for index, call in enumerate(patch_callback.call_args_list):
        assert call[0][0] == expected_status[index]
        assert call[0][2] == axis

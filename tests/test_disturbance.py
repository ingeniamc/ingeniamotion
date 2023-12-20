import pytest

from ingeniamotion.disturbance import Disturbance
from ingeniamotion.exceptions import IMDisturbanceError


@pytest.fixture
def disturbance_map_registers(disturbance, skip_if_monitoring_not_available):
    disturbance.map_registers([{"axis": 1, "name": "CL_TOR_SET_POINT_VALUE"}])


@pytest.fixture
def disturbance(motion_controller, skip_if_monitoring_not_available):
    mc, alias = motion_controller
    return Disturbance(mc, alias)


@pytest.mark.virtual
@pytest.mark.smoke
def test_disturbance_max_sample_size(motion_controller, disturbance):
    mc, alias = motion_controller
    max_sample_size = disturbance.max_sample_number
    value = mc.communication.get_register(
        disturbance.DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER, servo=alias, axis=0
    )
    assert max_sample_size == value


@pytest.mark.smoke
@pytest.mark.parametrize("prescaler", list(range(2, 11, 2)))
def test_set_frequency_divider(motion_controller, disturbance, prescaler):
    mc, alias = motion_controller
    disturbance.set_frequency_divider(prescaler)
    value = mc.communication.get_register(
        disturbance.DISTURBANCE_FREQUENCY_DIVIDER_REGISTER, servo=alias, axis=0
    )
    assert value == prescaler


@pytest.mark.smoke
def test_set_frequency_divider_exception(disturbance):
    prescaler = -1
    with pytest.raises(ValueError):
        disturbance.set_frequency_divider(prescaler)


@pytest.mark.smoke
@pytest.mark.parametrize(
    "axis, name, expected_value",
    [
        (1, "CL_POS_SET_POINT_VALUE", 270533892),
        (1, "CL_VEL_SET_POINT_VALUE", 270600196),
        (1, "CL_TOR_SET_POINT_VALUE", 270665732),
    ],
)
def test_disturbance_map_registers(motion_controller, disturbance, axis, name, expected_value):
    mc, alias = motion_controller
    registers = [{"axis": axis, "name": name}]
    disturbance.map_registers(registers)
    value = mc.communication.get_register("DIST_CFG_REG0_MAP", servo=alias, axis=0)
    assert value == expected_value
    value = mc.communication.get_register("DIST_CFG_MAP_REGS", servo=alias, axis=0)
    assert value == 1


@pytest.mark.smoke
@pytest.mark.parametrize("number_registers", list(range(1, 17)))
def test_disturbance_number_map_registers(motion_controller, disturbance, number_registers):
    mc, alias = motion_controller
    reg_dict = {"axis": 1, "name": "CL_POS_SET_POINT_VALUE"}
    registers = [reg_dict for _ in range(number_registers)]
    disturbance.map_registers(registers)
    value = mc.communication.get_register("DIST_CFG_MAP_REGS", servo=alias, axis=0)
    assert value == number_registers


@pytest.mark.smoke
def test_disturbance_map_registers_sample_number(disturbance):
    registers = [{"axis": 1, "name": "CL_POS_SET_POINT_VALUE"}]
    value = disturbance.map_registers(registers)
    assert value == disturbance.max_sample_number / 4


@pytest.mark.virtual
@pytest.mark.smoke
def test_disturbance_map_registers_exception(disturbance):
    registers = [{"axis": 0, "name": "DRV_AXIS_NUMBER"}]
    with pytest.raises(IMDisturbanceError):
        disturbance.map_registers(registers)


@pytest.mark.virtual
@pytest.mark.smoke
def test_disturbance_map_registers_empty(disturbance):
    registers = []
    with pytest.raises(IMDisturbanceError):
        disturbance.map_registers(registers)


@pytest.mark.smoke
@pytest.mark.usefixtures("disturbance_map_registers")
def test_write_disturbance_data_buffer_exception(disturbance):
    with pytest.raises(IMDisturbanceError):
        disturbance.write_disturbance_data([0] * disturbance.max_sample_number)


@pytest.mark.virtual
@pytest.mark.smoke
def test_write_disturbance_data_not_configured(disturbance):
    with pytest.raises(IMDisturbanceError):
        disturbance.write_disturbance_data([0] * 100)


@pytest.mark.smoke
def test_write_disturbance_data_enabled(
    motion_controller, disturbance, disable_monitoring_disturbance
):
    mc, alias = motion_controller
    mc.capture.enable_monitoring_disturbance(alias)
    with pytest.raises(IMDisturbanceError):
        disturbance.write_disturbance_data([0] * 100)


@pytest.mark.virtual
@pytest.mark.smoke
def test_disturbance_map_registers_invalid_subnode(mocker, motion_controller, disturbance):
    registers = [{"axis": "1", "name": "DRV_AXIS_NUMBER"}]
    mc, alias = motion_controller
    mocker.patch.object(mc.capture, "is_disturbance_enabled", return_value=False)
    with pytest.raises(TypeError):
        disturbance.map_registers(registers)


@pytest.mark.virtual
@pytest.mark.smoke
def test_disturbance_map_registers_invalid_register(mocker, motion_controller, disturbance):
    registers = [{"axis": 1, "name": 1}]
    mc, alias = motion_controller
    mocker.patch.object(mc.capture, "is_disturbance_enabled", return_value=False)
    with pytest.raises(TypeError):
        disturbance.map_registers(registers)


@pytest.mark.virtual
@pytest.mark.smoke
def test_write_disturbance_data_wrong_data_type(mocker, motion_controller, disturbance):
    mc, alias = motion_controller
    mocker.patch.object(mc.capture, "is_disturbance_enabled", return_value=False)
    registers = [{"axis": 1, "name": "CL_POS_SET_POINT_VALUE"}]
    disturbance.map_registers(registers)
    mocker.patch.object(disturbance, "sampling_freq", return_value=1000)
    with pytest.raises(TypeError):
        disturbance.write_disturbance_data(["wrong", "input", "value"])

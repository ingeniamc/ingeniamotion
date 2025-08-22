import pytest

from ingeniamotion.disturbance import Disturbance
from ingeniamotion.exceptions import IMDisturbanceError


@pytest.fixture
def disturbance_map_registers(disturbance, skip_if_monitoring_not_available):  # noqa: ARG001
    disturbance.map_registers([{"axis": 1, "name": "CL_TOR_SET_POINT_VALUE"}])


@pytest.fixture
def disturbance(mc, alias, skip_if_monitoring_not_available):  # noqa: ARG001
    return Disturbance(mc, alias)


@pytest.mark.virtual
def test_disturbance_max_sample_size(mc, alias, disturbance):
    max_sample_size = disturbance.max_sample_number
    value = mc.communication.get_register(
        disturbance.DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER, servo=alias, axis=0
    )
    assert max_sample_size == value


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.parametrize("prescaler", list(range(2, 11, 2)))
def test_set_frequency_divider(mc, alias, disturbance, prescaler):
    disturbance.set_frequency_divider(prescaler)
    value = mc.communication.get_register(
        disturbance.DISTURBANCE_FREQUENCY_DIVIDER_REGISTER, servo=alias, axis=0
    )
    assert value == prescaler


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_set_frequency_divider_exception(disturbance):
    prescaler = -1
    with pytest.raises(ValueError):
        disturbance.set_frequency_divider(prescaler)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.parametrize(
    "axis, name, expected_value",
    [
        (1, "CL_POS_SET_POINT_VALUE", 270533892),
        (1, "CL_VEL_SET_POINT_VALUE", 270600196),
        (1, "CL_TOR_SET_POINT_VALUE", 270665732),
    ],
)
def test_disturbance_map_registers(mc, alias, disturbance, axis, name, expected_value):
    registers = [{"axis": axis, "name": name}]
    disturbance.map_registers(registers)
    value = mc.communication.get_register("DIST_CFG_REG0_MAP", servo=alias, axis=0)
    assert value == expected_value
    value = mc.communication.get_register("DIST_CFG_MAP_REGS", servo=alias, axis=0)
    assert value == 1


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.parametrize("number_registers", list(range(1, 17)))
def test_disturbance_number_map_registers(mc, alias, disturbance, number_registers):
    reg_dict = {"axis": 1, "name": "CL_POS_SET_POINT_VALUE"}
    registers = [reg_dict for _ in range(number_registers)]
    disturbance.map_registers(registers)
    value = mc.communication.get_register("DIST_CFG_MAP_REGS", servo=alias, axis=0)
    assert value == number_registers


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
def test_disturbance_map_registers_sample_number(disturbance):
    registers = [{"axis": 1, "name": "CL_POS_SET_POINT_VALUE"}]
    value = disturbance.map_registers(registers)
    assert value == disturbance.max_sample_number / 4


@pytest.mark.virtual
def test_disturbance_map_registers_exception(disturbance):
    registers = [{"axis": 0, "name": "DRV_AXIS_NUMBER"}]
    with pytest.raises(IMDisturbanceError):
        disturbance.map_registers(registers)


@pytest.mark.virtual
def test_disturbance_map_registers_empty(disturbance):
    registers = []
    with pytest.raises(IMDisturbanceError):
        disturbance.map_registers(registers)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("disturbance_map_registers")
def test_write_disturbance_data_buffer_exception(disturbance):
    with pytest.raises(IMDisturbanceError):
        disturbance.write_disturbance_data([0] * disturbance.max_sample_number)


@pytest.mark.virtual
def test_write_disturbance_data_not_configured(disturbance):
    with pytest.raises(IMDisturbanceError):
        disturbance.write_disturbance_data([0] * 100)


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.usefixtures("disable_monitoring_disturbance")
def test_write_disturbance_data_enabled(mc, alias, disturbance):
    mc.capture.enable_disturbance(alias)
    with pytest.raises(IMDisturbanceError):
        disturbance.write_disturbance_data([0] * 100)


@pytest.mark.virtual
def test_disturbance_map_registers_invalid_subnode(mocker, mc, disturbance):
    registers = [{"axis": "1", "name": "DRV_AXIS_NUMBER"}]
    mocker.patch.object(mc.capture, "is_disturbance_enabled", return_value=False)
    with pytest.raises(TypeError):
        disturbance.map_registers(registers)


@pytest.mark.virtual
def test_disturbance_map_registers_invalid_register(mocker, mc, disturbance):
    registers = [{"axis": 1, "name": 1}]
    mocker.patch.object(mc.capture, "is_disturbance_enabled", return_value=False)
    with pytest.raises(TypeError):
        disturbance.map_registers(registers)


@pytest.mark.virtual
def test_write_disturbance_data_wrong_data_type(mocker, mc, disturbance):
    mocker.patch.object(mc.capture, "is_disturbance_enabled", return_value=False)
    registers = [{"axis": 1, "name": "CL_POS_SET_POINT_VALUE"}]
    disturbance.map_registers(registers)
    mocker.patch.object(disturbance, "sampling_freq", return_value=1000)
    with pytest.raises(TypeError):
        disturbance.write_disturbance_data(["wrong", "input", "value"])

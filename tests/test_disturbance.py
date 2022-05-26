import pytest

from ingeniamotion.disturbance import Disturbance
from ingeniamotion.exceptions import IMDisturbanceError


@pytest.mark.soem
@pytest.mark.eoe
@pytest.fixture
def disturbance_map_registers(disturbance):
    disturbance.map_registers([{"axis": 1, "name": "CL_POS_SET_POINT_VALUE"}])


@pytest.mark.smoke
def test_disturbance_max_sample_size(motion_controller, disturbance):
    mc, alias = motion_controller
    max_sample_size = disturbance.max_sample_number
    value = mc.communication.get_register(
        disturbance.DISTURBANCE_MAXIMUM_SAMPLE_SIZE_REGISTER,
        servo=alias,
        axis=0
    )
    assert max_sample_size == value

@pytest.mark.soem
@pytest.mark.eoe
@pytest.fixture
def disturbance(motion_controller):
    mc, alias = motion_controller
    return Disturbance(mc, alias)


@pytest.mark.soem
@pytest.mark.eoe
@pytest.mark.parametrize("prescaler", list(range(2, 11, 2)))
def test_set_frequency_divider(motion_controller, disturbance, prescaler):
    mc, alias = motion_controller
    disturbance.set_frequency_divider(prescaler)
    value = mc.communication.get_register(
        disturbance.DISTURBANCE_FREQUENCY_DIVIDER_REGISTER,
        servo=alias,
        axis=0
    )
    assert value == prescaler


@pytest.mark.soem
@pytest.mark.eoe
def test_set_frequency_divider_exception(disturbance):
    prescaler = 0.5
    with pytest.raises(ValueError):
        disturbance.set_frequency_divider(prescaler)


@pytest.mark.soem
@pytest.mark.eoe
def test_disturbance_map_registers(disturbance):
    registers = [{"axis": 1, "name": "CL_POS_SET_POINT_VALUE"}]
    value = disturbance.map_registers(registers)
    assert value == disturbance.max_sample_number / 4


@pytest.mark.soem
@pytest.mark.eoe
def test_disturbance_map_registers_exception(disturbance):
    registers = [{"axis": 0, "name": "DRV_AXIS_NUMBER"}]
    with pytest.raises(IMDisturbanceError):
        disturbance.map_registers(registers)


@pytest.mark.soem
@pytest.mark.eoe
@pytest.mark.usefixtures("disturbance_map_registers")
def test_write_disturbance_data_exception(disturbance):
    with pytest.raises(IMDisturbanceError):
        disturbance.write_disturbance_data([0] * disturbance.max_sample_number)


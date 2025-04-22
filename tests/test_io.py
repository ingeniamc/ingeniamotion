import pytest

from ingeniamotion.enums import GPI, GPO, DigitalVoltageLevel, GPIOPolarity
from ingeniamotion.exceptions import IMError
from tests.setups.rack_specifiers import CAN_CAP_SETUP, ECAT_CAP_SETUP, ETH_CAP_SETUP


@pytest.mark.virtual
@pytest.mark.smoke
def test_get_gpio_bit_value(motion_controller):
    mc, _, _ = motion_controller
    base_value = 0xA3  # 1010 0011
    bits = [True, True, False, False, False, True, False, True]

    for bit, bit_value in enumerate(bits):
        gpio_id = bit + 1
        assert mc.io._InputsOutputs__get_gpio_bit_value(base_value, gpio_id) == bit_value


@pytest.mark.virtual
@pytest.mark.smoke
def test_set_gpio_bit_value(motion_controller):
    mc, _, _ = motion_controller
    base_value = 0xA3  # 1010 0011

    assert mc.io._InputsOutputs__set_gpio_bit_value(base_value, 1, 0) == 0xA2
    assert mc.io._InputsOutputs__set_gpio_bit_value(base_value, 2, 0) == 0xA1
    assert mc.io._InputsOutputs__set_gpio_bit_value(base_value, 3, 1) == 0xA7
    assert mc.io._InputsOutputs__set_gpio_bit_value(base_value, 4, 1) == 0xAB
    assert mc.io._InputsOutputs__set_gpio_bit_value(base_value, 5, 1) == 0xB3
    assert mc.io._InputsOutputs__set_gpio_bit_value(base_value, 6, 0) == 0x83
    assert mc.io._InputsOutputs__set_gpio_bit_value(base_value, 7, 1) == 0xE3
    assert mc.io._InputsOutputs__set_gpio_bit_value(base_value, 8, 0) == 0x23


@pytest.mark.parametrize("gpi_id", [GPI.GPI1, GPI.GPI2, GPI.GPI3, GPI.GPI4])
@pytest.mark.parametrize("polarity", [GPIOPolarity.NORMAL, GPIOPolarity.REVERSED])
@pytest.mark.virtual
@pytest.mark.smoke
def test_set_get_gpi_polarity(motion_controller, gpi_id, polarity):
    mc, alias, environment = motion_controller
    mc.io.set_gpi_polarity(gpi_id, polarity, servo=alias)
    assert mc.io.get_gpi_polarity(gpi_id, servo=alias) == polarity


@pytest.mark.ethernet
@pytest.mark.soem
@pytest.mark.canopen
@pytest.mark.virtual
@pytest.mark.smoke
def test_get_gpi_voltage_level(motion_controller, setup_specifier):
    mc, alias, environment = motion_controller

    if setup_specifier in [ETH_CAP_SETUP, ECAT_CAP_SETUP, CAN_CAP_SETUP]:
        pytest.skip("Capitan rack setups do not have gpio control")

    environment.set_gpi(number=1, value=False)
    environment.set_gpi(number=2, value=True)
    environment.set_gpi(number=3, value=False)
    environment.set_gpi(number=4, value=True)
    mc.communication.set_register("IO_IN_POLARITY", 0, servo=alias)

    assert mc.communication.get_register("IO_IN_VALUE", servo=alias) == 0b1010

    assert mc.io.get_gpi_voltage_level(GPI.GPI1, servo=alias) == DigitalVoltageLevel.LOW
    mc.io.set_gpi_polarity(GPI.GPI1, GPIOPolarity.REVERSED, servo=alias)
    assert mc.io.get_gpi_voltage_level(GPI.GPI1, servo=alias) == DigitalVoltageLevel.HIGH

    assert mc.io.get_gpi_voltage_level(GPI.GPI2, servo=alias) == DigitalVoltageLevel.HIGH
    mc.io.set_gpi_polarity(GPI.GPI2, GPIOPolarity.REVERSED, servo=alias)
    assert mc.io.get_gpi_voltage_level(GPI.GPI2, servo=alias) == DigitalVoltageLevel.LOW

    assert mc.io.get_gpi_voltage_level(GPI.GPI3, servo=alias) == DigitalVoltageLevel.LOW
    mc.io.set_gpi_polarity(GPI.GPI3, GPIOPolarity.REVERSED, servo=alias)
    assert mc.io.get_gpi_voltage_level(GPI.GPI3, servo=alias) == DigitalVoltageLevel.HIGH

    assert mc.io.get_gpi_voltage_level(GPI.GPI4, servo=alias) == DigitalVoltageLevel.HIGH
    mc.io.set_gpi_polarity(GPI.GPI4, GPIOPolarity.REVERSED, servo=alias)
    assert mc.io.get_gpi_voltage_level(GPI.GPI4, servo=alias) == DigitalVoltageLevel.LOW


@pytest.mark.parametrize("gpo_id", [GPO.GPO1, GPO.GPO2, GPO.GPO3, GPO.GPO4])
@pytest.mark.parametrize("polarity", [GPIOPolarity.NORMAL, GPIOPolarity.REVERSED])
@pytest.mark.virtual
@pytest.mark.smoke
def test_set_get_gpo_polarity(motion_controller, gpo_id, polarity):
    mc, alias, environment = motion_controller
    mc.io.set_gpo_polarity(gpo_id, polarity, servo=alias)
    assert mc.io.get_gpo_polarity(gpo_id, servo=alias) == polarity


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.smoke
@pytest.mark.parametrize(
    "gpo_id,reg_value",
    [
        (GPO.GPO1, 1),
        (GPO.GPO2, 2),
        (GPO.GPO3, 4),
        (GPO.GPO4, 8),
    ],
)
def test_set_gpo_voltage_level(motion_controller, gpo_id, reg_value):
    mc, alias, environment = motion_controller

    for map_reg in ["IO_OUT_MAP_1", "IO_OUT_MAP_2", "IO_OUT_MAP_3", "IO_OUT_MAP_4"]:
        mc.communication.set_register(map_reg, 0, servo=alias)

    mc.communication.set_register("IO_OUT_POLARITY", 0, servo=alias)
    mc.communication.set_register("IO_OUT_SET_POINT", 0, servo=alias)

    mc.io.set_gpo_voltage_level(gpo_id, DigitalVoltageLevel.HIGH, servo=alias)
    assert mc.communication.get_register("IO_OUT_VALUE", servo=alias) == reg_value
    mc.io.set_gpo_voltage_level(gpo_id, DigitalVoltageLevel.LOW, servo=alias)
    assert mc.communication.get_register("IO_OUT_VALUE", servo=alias) == 0
    mc.io.set_gpo_polarity(gpo_id, GPIOPolarity.REVERSED, servo=alias)
    mc.io.set_gpo_voltage_level(gpo_id, DigitalVoltageLevel.HIGH, servo=alias)
    assert mc.communication.get_register("IO_OUT_VALUE", servo=alias) == reg_value
    mc.io.set_gpo_voltage_level(gpo_id, DigitalVoltageLevel.LOW, servo=alias)
    assert mc.communication.get_register("IO_OUT_VALUE", servo=alias) == 0


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.smoke
@pytest.mark.parametrize(
    "gpo_id",
    [
        GPO.GPO1,
        GPO.GPO2,
        GPO.GPO3,
        GPO.GPO4,
    ],
)
def test_set_gpo_voltage_level_fail(motion_controller, gpo_id):
    mc, alias, environment = motion_controller

    mc.communication.set_register("IO_OUT_POLARITY", 0, servo=alias)
    for map_reg in ["IO_OUT_MAP_1", "IO_OUT_MAP_2", "IO_OUT_MAP_3", "IO_OUT_MAP_4"]:
        mc.communication.set_register(map_reg, 3, servo=alias)

    with pytest.raises(IMError):
        mc.io.set_gpo_voltage_level(gpo_id, DigitalVoltageLevel.LOW, servo=alias)

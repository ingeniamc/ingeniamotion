from typing import TYPE_CHECKING, Union

import ingenialogger

from ingeniamotion.enums import GPI, GPO, DigitalVoltageLevel, GPIOPolarity
from ingeniamotion.exceptions import IMException
from ingeniamotion.metaclass import DEFAULT_AXIS, DEFAULT_SERVO, MCMetaClass

if TYPE_CHECKING:
    from ingeniamotion.motion_controller import MotionController


class InputsOutputs(metaclass=MCMetaClass):
    GPIO_IN_VALUE_REGISTER = "IO_IN_VALUE"
    GPIO_IN_POLARITY_REGISTER = "IO_IN_POLARITY"

    GPIO_OUT_VALUE_REGISTER = "IO_OUT_VALUE"
    GPIO_OUT_SET_POINT_REGISTER = "IO_OUT_SET_POINT"
    GPIO_OUT_POLARITY_REGISTER = "IO_OUT_POLARITY"

    def __init__(self, motion_controller: "MotionController") -> None:
        self.mc = motion_controller
        self.logger = ingenialogger.get_logger(__name__)

    @staticmethod
    def __get_gpio_bit_value(io_register_value: int, gpio_id: Union[GPI, GPO]) -> bool:
        """Get the bit value of a specific GPIO.

        Args:
            io_register_value: Register value including the bits of all GPIOs.
            gpio_id: The GPIO identifier.

        Returns:
            GPIO bit value.
        """
        gpio_bit_mask = 1 << (gpio_id - 1)
        return bool(io_register_value & gpio_bit_mask)

    @staticmethod
    def __set_gpio_bit_value(
        io_register_value: int, gpio_id: Union[GPI, GPO], bit_value: bool
    ) -> int:
        """Set the bit value of a specific GPIO.

        Args:
            io_register_value: Register value including the bits of all GPIOs.
            gpio_id: The GPIO identifier.
            bit_value: Bit value to be set.

        Returns:
            The register value with the corresponding bit set accordingly.
        """
        gpio_bit_mask = 1 << (gpio_id - 1)
        if bit_value:
            new_register_value = io_register_value | gpio_bit_mask
        else:
            new_register_value = io_register_value & ~gpio_bit_mask

        return new_register_value

    def get_gpi_polarity(
        self, gpi_id: GPI, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> GPIOPolarity:
        """Get the polarity of a single GPI.

        Args:
            gpi_id: the GPI to get the polarity.
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. 1 by default.

        Returns:
            Polarity of the specified GPI.

        """
        gpi_polarity = int(
            self.mc.communication.get_register(
                self.GPIO_IN_POLARITY_REGISTER, servo=servo, axis=axis
            )
        )
        gpi_bit_polarity = self.__get_gpio_bit_value(gpi_polarity, gpi_id)
        return GPIOPolarity(int(gpi_bit_polarity))

    def set_gpi_polarity(
        self,
        gpi_id: GPI,
        polarity: GPIOPolarity,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Set the polarity of a single GPI.

        Args:
            gpi_id: the GPI polarity to be set.
            polarity: polarity to be set.
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. 1 by default.

        """
        gpis_actual_polarity = int(
            self.mc.communication.get_register(
                self.GPIO_IN_POLARITY_REGISTER, servo=servo, axis=axis
            )
        )
        gpis_new_polarity = self.__set_gpio_bit_value(
            gpis_actual_polarity, gpi_id, bool(polarity.value)
        )
        self.mc.communication.set_register(
            self.GPIO_IN_POLARITY_REGISTER, gpis_new_polarity, servo=servo, axis=axis
        )

    def get_gpi_voltage_level(
        self, gpi_id: GPI, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> DigitalVoltageLevel:
        """Get the board voltage level (not the logic level at the uC) of a single GPI.

        Args:
            gpi_id: the gpi to get the voltage level
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. 1 by default.

        Returns:
            LOW if the voltage level is 0, HIGH if the voltage level is 1.

        """
        gpi_value = int(
            self.mc.communication.get_register(self.GPIO_IN_VALUE_REGISTER, servo=servo, axis=axis)
        )
        gpi_bit_value = self.__get_gpio_bit_value(gpi_value, gpi_id)

        return DigitalVoltageLevel(gpi_bit_value)

    def get_gpo_polarity(
        self, gpo_id: GPO, servo: str = DEFAULT_SERVO, axis: int = DEFAULT_AXIS
    ) -> GPIOPolarity:
        """Get the polarity of a single GPO.

        Args:
            gpo_id: the GPO to get the polarity.
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. 1 by default.

        Returns:
            Polarity of the specified GPI.

        """
        gpo_polarity = int(
            self.mc.communication.get_register(
                self.GPIO_OUT_POLARITY_REGISTER, servo=servo, axis=axis
            )
        )
        gpo_bit_polarity = self.__get_gpio_bit_value(gpo_polarity, gpo_id)
        return GPIOPolarity(int(gpo_bit_polarity))

    def set_gpo_polarity(
        self,
        gpo_id: GPO,
        polarity: GPIOPolarity,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """Set the polarity of a single GPO.

        Args:
            gpo_id: the GPO polarity to be set.
            polarity: polarity to be set.
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. 1 by default.

        """
        gpos_actual_polarity = int(
            self.mc.communication.get_register(
                self.GPIO_OUT_POLARITY_REGISTER, servo=servo, axis=axis
            )
        )
        gpos_new_polarity = self.__set_gpio_bit_value(
            gpos_actual_polarity, gpo_id, bool(polarity.value)
        )
        self.mc.communication.set_register(
            self.GPIO_OUT_POLARITY_REGISTER, gpos_new_polarity, servo=servo, axis=axis
        )

    def set_gpo_voltage_level(
        self,
        gpo_id: GPO,
        voltage_level: DigitalVoltageLevel,
        servo: str = DEFAULT_SERVO,
        axis: int = DEFAULT_AXIS,
    ) -> None:
        """
        Description:
            Set the board voltage level (not the logic level at the uC) of a single GPO.

            This function generates the GPO set point from the actual GPO value and modifies
            the corresponding bit of the desired GPO.

            Finally, it checks that GPOs final value matches with the desired GPOs set point

        Args:
            gpo_id: the GPO to be set.
            voltage_level: For each bit, 0 if voltage level is LOW, 1 if voltage level is HIGH
            servo : servo alias to reference it. ``default`` by default.
            axis : axis that will run the test. 1 by default.

        Raise:
            IMException: if the GPOs final value does not match with the desired GPOs set point.
        """
        new_target_value = bool(voltage_level.value)

        gpos_previous_value = int(
            self.mc.communication.get_register(self.GPIO_OUT_VALUE_REGISTER, servo=servo, axis=axis)
        )

        gpos_new_set_point = self.__set_gpio_bit_value(
            gpos_previous_value, gpo_id, new_target_value
        )
        self.mc.communication.set_register(
            self.GPIO_OUT_SET_POINT_REGISTER, gpos_new_set_point, servo=servo, axis=axis
        )
        gpos_final_value = int(
            self.mc.communication.get_register(self.GPIO_OUT_VALUE_REGISTER, servo=servo, axis=axis)
        )

        gpo_final_value = self.__get_gpio_bit_value(gpos_final_value, gpo_id)

        if gpo_final_value != new_target_value:
            raise IMException("Unable to set the GPOs set point value.")

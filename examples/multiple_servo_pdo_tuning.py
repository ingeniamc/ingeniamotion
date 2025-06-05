import time
from dataclasses import dataclass
from typing import Union

import matplotlib.pyplot as plt
from ingenialink.pdo import RPDOMapItem, TPDOMapItem
from ingeniamotion.enums import FilterType, OperationMode
from ingeniamotion.motion_controller import MotionController

SRV_1: str = "1"
SRV_2: str = "2"

PDO_REFRESH_RATE: float = 0.001  # seconds
CAPTURE_TIME: int = 10  # seconds

SQUARE_WAVE_AMPLITUDE_A: float = 5
SQUARE_WAVE_AMPLITUDE_B: float = -5
SQUARE_WAVE_FREQUENCY: float = 0.1
SQUARE_WAVE_DUTY_CYCLE: float = 0.5

TORQUE_SET_POINT_REGISTER: str = "CL_TOR_SET_POINT_VALUE"
POSITION_SET_POINT_REGISTER: str = "CL_POS_SET_POINT_VALUE"
VELOCITY_SET_POINT_REGISTER: str = "CL_VEL_SET_POINT_VALUE"

VELOCITY_ACTUAL_REGISTER = "CL_VEL_FBK_VALUE"
POSITION_ACTUAL_REGISTER = "CL_POS_FBK_VALUE"
TORQUE_ACTUAL_REGISTER = "CL_TOR_FBK_VALUE"


def configure_servo(operation_mode: OperationMode, mc: MotionController, servo: str) -> None:
    """Configure the servo with the initial configuration."""

    mc.motion.set_operation_mode(operation_mode, servo)
    mc.communication.set_register(VELOCITY_SET_POINT_REGISTER, 0, servo)
    mc.communication.set_register(TORQUE_SET_POINT_REGISTER, 0, servo)


class SquareWave:
    """Class to create a square wave signal."""

    def __init__(
        self,
        amplitude_a: float,
        amplitude_b: float,
        frequency: float,
        duty_cycle: float,
        phy: float = 0,
    ) -> None:
        self.amplitude_a: float = amplitude_a
        self.amplitude_b: float = amplitude_b
        self.frequency: float = frequency
        self.time_period: float = 1 / frequency
        self.current_time: float = 0
        self.duty_cycle: float = duty_cycle
        self.phy: float = phy

    def get_value(self, current_time: float) -> float:
        """Get the current value of the square wave.

        Args:
            current_time (float): The current time.

        Returns:
            float: The current value of the square wave.
        """
        if ((current_time + self.phy) % self.time_period) < (self.time_period * self.duty_cycle):
            return self.amplitude_a
        else:
            return self.amplitude_b


class PlotPoints:
    """Class to store the points of the plot."""

    def __init__(self) -> None:
        self.xs: list[float] = []
        self.ys: list[float] = []

    def add_point(self, x: float, y: float) -> None:
        """Add a point to the plot."""
        self.xs.append(x)
        self.ys.append(y)

    def get_points(self) -> tuple[list[float], list[float]]:
        """Get the points of the plot.

        Returns:
            tuple: The x and y points of the plot.
        """
        return self.xs, self.ys


class PDOCallbacks:
    """Class to handle the PDO callbacks."""

    def __init__(
        self,
        output_1: TPDOMapItem,
        output_2: TPDOMapItem,
        output_3: TPDOMapItem,
        input_1: RPDOMapItem,
        servo: str,
    ) -> None:
        self.output_1: TPDOMapItem = output_1
        self.output_2: TPDOMapItem = output_2
        self.output_3: TPDOMapItem = output_3
        self.input_1: RPDOMapItem = input_1
        self.servo: str = servo
        self.wave: SquareWave = SquareWave(
            amplitude_a=SQUARE_WAVE_AMPLITUDE_A,
            amplitude_b=SQUARE_WAVE_AMPLITUDE_B,
            frequency=SQUARE_WAVE_FREQUENCY,
            duty_cycle=SQUARE_WAVE_DUTY_CYCLE,
        )
        self.init_t: Union[float, None] = None
        self.data_output_1: PlotPoints = PlotPoints()
        self.data_output_2: PlotPoints = PlotPoints()
        self.data_output_3: PlotPoints = PlotPoints()
        self.data_input_1: PlotPoints = PlotPoints()

    def update_wave(
        self,
        amplitude_a: Union[float, None] = None,
        amplitude_b: Union[float, None] = None,
        frequency: Union[float, None] = None,
        duty_cycle: Union[float, None] = None,
        phy: Union[float, None] = None,
    ) -> None:
        """Update the square wave parameters."""
        if amplitude_a is None:
            amplitude_a = SQUARE_WAVE_AMPLITUDE_A
        if amplitude_b is None:
            amplitude_b = SQUARE_WAVE_AMPLITUDE_B
        if frequency is None:
            frequency = SQUARE_WAVE_FREQUENCY
        if duty_cycle is None:
            duty_cycle = SQUARE_WAVE_DUTY_CYCLE
        self.wave = SquareWave(
            amplitude_a=amplitude_a,
            amplitude_b=amplitude_b,
            frequency=frequency,
            duty_cycle=duty_cycle,
            phy=phy or 0,
        )

    def notify_output_value(self) -> None:
        """Callback that is subscribed to get the actual position for cycle."""
        if self.init_t is None:
            self.init_t = time.time()
        current_time: float = time.time() - self.init_t

        self.data_output_1.add_point(current_time, self.output_1.value)
        self.data_output_2.add_point(current_time, self.output_2.value)
        self.data_output_3.add_point(current_time, self.output_3.value)

    def update_input_values(self) -> None:
        """Callback to update the position set point value for each cycle."""
        if self.init_t is None:
            return
        current_time: float = time.time() - self.init_t
        vel_value: float = self.wave.get_value(time.time())
        self.data_input_1.add_point(current_time, vel_value)
        self.input_1.value = vel_value


@dataclass
class PDOConfig:
    """Configuration for the PDOs."""

    INPUT_REGISTER: str
    OUTPUT_1_REGISTER: str
    OUTPUT_2_REGISTER: str
    OUTPUT_3_REGISTER: str


def configure_pdos(pdo_config: PDOConfig, mc: MotionController, servo: str) -> PDOCallbacks:
    """Updates the position of a motor using PDOs.

    Args:
        pdo_config: PDOs registers.
        mc: Controller with all the functions needed to perform a PDO exchange.
        servo: The servo identifier.

    Returns:
        PDOCallbacks: The callbacks for the PDO exchange.
    """
    init_value = mc.communication.get_register(pdo_config.INPUT_REGISTER, servo)
    input_1: RPDOMapItem = mc.capture.pdo.create_pdo_item(
        pdo_config.INPUT_REGISTER, value=init_value, servo=servo
    )
    output_1: TPDOMapItem = mc.capture.pdo.create_pdo_item(
        pdo_config.OUTPUT_1_REGISTER, servo=servo
    )
    output_2: TPDOMapItem = mc.capture.pdo.create_pdo_item(
        pdo_config.OUTPUT_2_REGISTER, servo=servo
    )
    output_3: TPDOMapItem = mc.capture.pdo.create_pdo_item(
        pdo_config.OUTPUT_3_REGISTER, servo=servo
    )

    rpdo_map, tpdo_map = mc.capture.pdo.create_pdo_maps([input_1], [output_1, output_2, output_3])

    pdo_callbacks: PDOCallbacks = PDOCallbacks(output_1, output_2, output_3, input_1, servo)

    mc.capture.pdo.subscribe_to_receive_process_data(pdo_callbacks.notify_output_value)
    mc.capture.pdo.subscribe_to_send_process_data(pdo_callbacks.update_input_values)
    mc.capture.pdo.set_pdo_maps_to_slave(rpdo_map, tpdo_map, servo=servo)

    return pdo_callbacks


def plot_data(pdo_callbacks_1: PDOCallbacks, pdo_callbacks_2: PDOCallbacks) -> None:
    """Plot the data from the PDO callbacks."""
    plt.figure("Input")
    plt.plot(*pdo_callbacks_1.data_input_1.get_points(), label="Servo 1")
    plt.plot(*pdo_callbacks_2.data_input_1.get_points(), label="Servo 2")
    plt.legend()

    plt.figure("Velocity Output")
    plt.plot(*pdo_callbacks_1.data_output_1.get_points(), label="Servo 1")
    plt.plot(*pdo_callbacks_2.data_output_1.get_points(), label="Servo 2")
    plt.legend()

    plt.figure("Position Output Servo 1")
    plt.plot(*pdo_callbacks_1.data_output_2.get_points(), label="Servo 1")
    plt.legend()
    plt.figure("Position Output Servo 2")
    plt.plot(*pdo_callbacks_2.data_output_2.get_points(), label="Servo 2")
    plt.legend()

    plt.figure("Torque Output Servo 1")
    plt.plot(*pdo_callbacks_1.data_output_3.get_points(), label="Servo 1")
    plt.legend()
    plt.figure("Torque Output Servo 2")
    plt.plot(*pdo_callbacks_2.data_output_3.get_points(), label="Servo 2")
    plt.legend()

    plt.show()


def main() -> None:
    """Main function to run the script."""
    mc: MotionController = MotionController()
    ifname: str = "\\Device\\NPF_{7B84A7B7-2506-44FE-89C3-D97DA2FD2869}"

    pdos_1: PDOConfig = PDOConfig(
        INPUT_REGISTER=POSITION_SET_POINT_REGISTER,
        OUTPUT_1_REGISTER=VELOCITY_ACTUAL_REGISTER,
        OUTPUT_2_REGISTER=POSITION_ACTUAL_REGISTER,
        OUTPUT_3_REGISTER=TORQUE_ACTUAL_REGISTER,
    )
    pdos_2: PDOConfig = PDOConfig(
        INPUT_REGISTER=VELOCITY_SET_POINT_REGISTER,
        OUTPUT_1_REGISTER=VELOCITY_ACTUAL_REGISTER,
        OUTPUT_2_REGISTER=POSITION_ACTUAL_REGISTER,
        OUTPUT_3_REGISTER=TORQUE_ACTUAL_REGISTER,
    )

    mc.communication.connect_servo_ethercat(ifname, 1, "dictionary_path_1.xdf", SRV_1)
    mc.communication.connect_servo_ethercat(ifname, 2, "dictionary_path_2.xdf", SRV_2)

    configure_servo(OperationMode.POSITION, mc, SRV_1)
    configure_servo(OperationMode.VELOCITY, mc, SRV_2)
    mc.motion.motor_enable(SRV_1)
    mc.motion.motor_enable(SRV_2)

    pdo_callbacks_1: PDOCallbacks = configure_pdos(pdos_1, mc, SRV_1)
    pdo_callbacks_2: PDOCallbacks = configure_pdos(pdos_2, mc, SRV_2)
    pdo_callbacks_1.update_wave(amplitude_a=1000, amplitude_b=0, frequency=0.1)

    mc.capture.pdo.start_pdos(refresh_rate=PDO_REFRESH_RATE)
    time.sleep(CAPTURE_TIME)
    mc.capture.pdo.stop_pdos()

    mc.motion.motor_disable(SRV_1)
    mc.motion.motor_disable(SRV_2)

    mc.communication.disconnect(SRV_1)
    mc.communication.disconnect(SRV_2)

    plot_data(pdo_callbacks_1, pdo_callbacks_2)


if __name__ == "__main__":
    main()

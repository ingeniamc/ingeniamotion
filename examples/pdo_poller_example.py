import time
from typing import Dict, List, Union

from ingeniamotion.enums import SensorType
from ingeniamotion.motion_controller import MotionController


def set_feedback_sensors(mc: MotionController) -> None:
    """Set the type of position and velocity feedback sensors.

    Args:
        mc: the controller to configure.
    """
    # Modify the SensorType.
    mc.configuration.set_position_feedback(SensorType.QEI)
    mc.configuration.set_velocity_feedback(SensorType.QEI)


def set_up_pdo_poller(mc: MotionController) -> None:
    """Set-up a PDO poller.

    Read the Actual Position and the Actual Velocity registers using the PDO poller.

    Args:
        mc: The controller where there are all functions to perform a PDO poller.
    """
    registers: List[Dict[str, Union[int, str]]] = [
        {
            "name": "CL_POS_FBK_VALUE",
            "axis": 1,
        },
        {
            "name": "CL_VEL_FBK_VALUE",
            "axis": 1,
        },
    ]

    poller = mc.capture.pdo.create_poller(registers)
    # Waiting time for generating new samples
    time.sleep(1)
    time_stamps, data = poller.data
    poller.stop()

    print(f"Time: {time_stamps}")
    print(f"Actual Position values: {data[0]}")
    print(f"Actual Velocity values: {data[1]}")


def main() -> None:
    mc = MotionController()
    # Modify these parameters to connect a drive
    interface_index = 3
    slave_id = 1
    dictionary_path = "parent_directory/dictionary_file.xdf"
    mc.communication.connect_servo_ethercat_interface_index(
        interface_index, slave_id, dictionary_path
    )
    set_feedback_sensors(mc)
    set_up_pdo_poller(mc)
    mc.communication.disconnect()
    print("The drive has been disconnected.")


if __name__ == "__main__":
    main()

import time
from typing import Dict, List, Union

from ingeniamotion.enums import SensorType
from ingeniamotion.motion_controller import MotionController


def establish_coe_connection(mc: MotionController) -> None:
    """Establish an EtherCAT-CoE communication.

    Find all available nodes, and perform a communication.

    Args:
        mc: The object where there are all functions to establish a communication.
    """
    # Modify these parameters to connect a drive
    interface_index = 3
    slave_id = 1
    dictionary_path = (
        "parent_directory/dictionary_file.xdf"
    )

    interface_selected = mc.communication.get_ifname_by_index(interface_index)
    slave_id_list = mc.communication.scan_servos_ethercat(interface_selected)

    if not slave_id_list:
        interface_list = mc.communication.get_interface_name_list()
        print(f"No slave detected on interface: {interface_list[interface_index]}")
        return
    else:
        print(f"Found slaves: {slave_id_list}")

    mc.communication.connect_servo_ethercat(interface_selected, slave_id, dictionary_path)
    print("Drive is connected.")


def set_feedback_sensors(mc: MotionController) -> None:
    """Set the type of position and velocity feedback sensors.

    Args:
        mc: the controller to configure.
    """
    # Modify the SensorType.
    mc.configuration.set_position_feedback(SensorType.HALLS)
    mc.configuration.set_velocity_feedback(SensorType.HALLS)


def perform_pdo_poller(mc: MotionController) -> None:
    """Perform a PDO poller.

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
    establish_coe_connection(mc)
    set_feedback_sensors(mc)
    perform_pdo_poller(mc)
    mc.communication.disconnect()
    print("The drive has been disconnected.")


if __name__ == "__main__":
    main()

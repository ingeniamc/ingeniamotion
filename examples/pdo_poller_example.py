import time
from typing import Union

from ingeniamotion.motion_controller import MotionController


def set_up_pdo_poller(mc: MotionController) -> None:
    """Set-up a PDO poller.

    Read the Actual Position and the Actual Velocity registers using the PDO poller.

    Args:
        mc: The controller where there are all functions to perform a PDO poller.
    """
    registers: list[dict[str, Union[int, str]]] = [
        {
            "name": "CL_POS_FBK_VALUE",
            "axis": 1,
        },
        {
            "name": "CL_VEL_FBK_VALUE",
            "axis": 1,
        },
    ]

    poller = mc.capture.pdo.create_poller(registers=registers)
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
    interface_ip = "192.168.2.1"
    slave_id = 1
    dictionary_path = "parent_directory/dictionary_file.xdf"
    mc.communication.connect_servo_ethercat_interface_ip(interface_ip, slave_id, dictionary_path)
    set_up_pdo_poller(mc)
    mc.communication.disconnect()
    print("The drive has been disconnected.")


if __name__ == "__main__":
    main()

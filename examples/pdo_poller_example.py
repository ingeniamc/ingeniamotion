import contextlib
from typing import Dict, List, Union

from ingeniamotion import MotionController
from ingeniamotion.exceptions import IMTimeoutError


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

    poller = mc.capture.pdo.create_poller(registers, sampling_time=0.01)
    # Waiting time for generating new samples
    with contextlib.suppress(IMTimeoutError):
        mc.motion.wait_for_velocity(velocity=10, timeout=5)

    time_stamps, data = poller.data
    poller.stop()

    print(f"Time: {time_stamps}")
    print(f"Actual Position values: {data[0]}")
    print(f"Actual Velocity values: {data[1]}")

    for time_series in data:
        for value in time_series:
            assert value == 0


def main() -> None:
    mc = MotionController()
    # Modify these parameters to connect a drive
    interface_ip = "192.168.2.1"
    slave_id = 1
    dictionary_path = "safe_dict.xdf"
    mc.communication.connect_servo_ethercat_interface_ip(
        interface_ip, slave_id, dictionary_path
    )
    set_up_pdo_poller(mc)
    mc.communication.disconnect()
    print("The drive has been disconnected.")


if __name__ == "__main__":
    main()

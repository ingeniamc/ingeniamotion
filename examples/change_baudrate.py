from typing import Optional

from ingenialink import CAN_BAUDRATE, CAN_DEVICE

from ingeniamotion.exceptions import IMException
from ingeniamotion.motion_controller import MotionController


def establish_canopen_communication(mc: MotionController, device: CAN_DEVICE, channel: int, baudrate: CAN_BAUDRATE, dictionary_path: str, node_id: Optional[int]):
    print("Finding the available nodes...")
    node_id_list = mc.communication.scan_servos_canopen(
        device,
        baudrate=baudrate,
        channel=channel,
    )
    if not node_id_list:
        raise IMException(f"Any node is detected.")

    print(f"Found nodes: {node_id_list}")
    if node_id is None:
        print("Node ID is selected automatically.")
        node_to_connect = node_id_list[0]
    else:
        print("Node ID is selected manually.")
        node_to_connect = node_id

    print("Starts to establish a communication.")
    mc.communication.connect_servo_canopen(
        device,
        dictionary_path,
        node_to_connect,
        baudrate=baudrate,
        channel=channel,
    )
    print(f"Drive is connected with {baudrate} baudrate.")


def change_baudrate(device: CAN_DEVICE, channel: int, baudrate: CAN_BAUDRATE, dictionary_path: str, new_baudrate: int, node_id: Optional[int] = None) -> None:
    mc = MotionController()
    try:
        establish_canopen_communication(mc, device, channel, baudrate, dictionary_path, node_id)
    except IMException as e:
        print(e)
        return
    print("Starts to change the baudrate.")
    old_baudrate = mc.info.get_baudrate()
    if old_baudrate == new_baudrate:
        print(f"This drive already has this baudrate: {old_baudrate}.")
        return
    mc.configuration.change_baudrate(new_baudrate)
    print(f"Baudrate has been changed from {old_baudrate} to {new_baudrate}.")

    baudrate = new_baudrate
    mc.communication.disconnect()
    print("Drive is disconnected.")
    print(f"Make a power-cycle on your drive and connect it again using the new baudrate {new_baudrate}")


if __name__ == "__main__":
    # Remember to replace all parameters here
    # If you want to connect to a node manually, set the node_id parameter as an integer.
    # Instead, set the node_id parameter as a NoneType value to connect the first detected CAN node.
    device = CAN_DEVICE.KVASER
    channel = 0
    node_id = 20
    baudrate = CAN_BAUDRATE.Baudrate_1M
    dictionary_path = "\\\\awe-srv-max-prd\\distext\\products\\EVE-NET\\firmware\\2.5.1\\eve-net-c_can_2.5.1.xdf"

    change_baudrate(device, channel, baudrate, dictionary_path, CAN_BAUDRATE.Baudrate_250K, node_id)

from typing import Optional

from ingenialink import CAN_BAUDRATE, CAN_DEVICE

from ingeniamotion.motion_controller import MotionController


def establish_canopen_communication(
    mc: MotionController,
    device: CAN_DEVICE,
    channel: int,
    baudrate: CAN_BAUDRATE,
    dictionary_path: str,
    node_id: Optional[int],
) -> bool:
    """Establish a CANopen communication.
    
    Find all available nodes by means of a scanning, and perform a communication.
    If there isn't a selected node ID, it will perform a communication with the first found node ID.

    Args:
        mc: The object where there are all functions to establish a communication.
        device: The type of transceiver (KVASER, PCAN, IXXAT).
        channel: CANopen channel.
        baudrate: The bit-timing rate of the communication.
        dictionary_path: The absolute path where is placed a xdf file.
        node_id: The selected node ID.

    Returns:
        True if the communication is performed successfully, False if it couldn't be established.
    """
    print("Finding the available nodes...")
    node_id_list = mc.communication.scan_servos_canopen(
        device,
        baudrate=baudrate,
        channel=channel,
    )
    if not node_id_list:
        return False
    else:
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
    print(f"Drive is connected with {node_to_connect} as a node ID.")
    return True


def change_node_id(
    device: CAN_DEVICE,
    channel: int,
    baudrate: CAN_BAUDRATE,
    dictionary_path: str,
    new_node_id: int,
    node_id: Optional[int] = None,
) -> None:
    mc = MotionController()
    if not establish_canopen_communication(mc, device, channel, baudrate, dictionary_path, node_id):
        print("No node is detected.")
        return

    print("Starts to change the node ID.")
    old_node_id = mc.info.get_node_id()
    if old_node_id == new_node_id:
        print(f"This drive already has this node ID: {old_node_id}.")
        mc.communication.disconnect()
        return

    mc.configuration.change_node_id(new_node_id)
    print("Node ID has been changed")

    mc.communication.disconnect()
    print("Drive is disconnected.")

    print("Re-connect to the drive.")
    node_id = new_node_id
    if not establish_canopen_communication(mc, device, channel, baudrate, dictionary_path, node_id):
        print("Any node is detected.")
        return

    mc.communication.disconnect()
    print("Drive is disconnected.")


if __name__ == "__main__":
    # Remember to replace all parameters here
    # If you want to connect to a node manually, set the node_id parameter as an integer.
    # Instead, set the node_id parameter as a NoneType value to connect the first detected CAN node.

    device = CAN_DEVICE.KVASER
    channel = 0
    node_id = 20
    new_node_id = 32
    baudrate = CAN_BAUDRATE.Baudrate_1M
    dictionary_path = "parent_directory/dictionary_file.xdf"

    change_node_id(device, channel, baudrate, dictionary_path, new_node_id, node_id)

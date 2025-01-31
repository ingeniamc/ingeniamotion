from ingenialink import CanBaudrate, CanDevice

from ingeniamotion.motion_controller import MotionController


def change_node_id(
    device: CanDevice,
    channel: int,
    node_id: int,
    baudrate: CanBaudrate,
    dictionary_path: str,
    new_node_id: int,
) -> None:
    mc = MotionController()
    print("Connect to the drive.")
    mc.communication.connect_servo_canopen(
        device,
        dictionary_path,
        node_id,
        baudrate=baudrate,
        channel=channel,
    )
    print(f"Drive is connected with {node_id} as a node ID.")

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
    mc.communication.connect_servo_canopen(
        device,
        dictionary_path,
        new_node_id,
        baudrate=baudrate,
        channel=channel,
    )
    print(f"Now the drive is connected with {new_node_id} as a node ID.")

    mc.communication.disconnect()
    print("Drive is disconnected.")


if __name__ == "__main__":
    # Remember to replace all parameters here
    # If you want to connect to a node manually, set the node_id parameter as an integer.
    # Instead, set the node_id parameter as a NoneType value to connect the first detected CAN node.

    device = CanDevice.KVASER
    channel = 0
    node_id = 20
    new_node_id = 32
    baudrate = CanBaudrate.Baudrate_1M
    dictionary_path = "parent_directory/dictionary_file.xdf"

    change_node_id(device, channel, node_id, baudrate, dictionary_path, new_node_id)

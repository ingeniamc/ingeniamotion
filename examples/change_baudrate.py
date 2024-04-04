from typing import Any, Dict

from ingenialink import CAN_BAUDRATE, CAN_DEVICE

from ingeniamotion.exceptions import IMException
from ingeniamotion.motion_controller import MotionController


def establish_canopen_communication(mc: MotionController, can_drive: Dict[str, Any]):
    print("Finding the available nodes...")
    node_id_list = mc.communication.scan_servos_canopen(
        can_drive["device"],
        baudrate=can_drive["baudrate"],
        channel=can_drive["channel"],
    )
    if not node_id_list:
        raise IMException(f"Any node is detected.")

    print(f"Found nodes: {node_id_list}")
    if can_drive["node_id"] is None:
        print("Node ID is selected automatically.")
        node_to_connect = node_id_list[0]
    else:
        print("Node ID is selected manually.")
        node_to_connect = can_drive["node_id"]

    print("Starts to establish a communication.")
    mc.communication.connect_servo_canopen(
        can_drive["device"],
        can_drive["dictionary_path"],
        node_to_connect,
        baudrate=can_drive["baudrate"],
        channel=can_drive["channel"],
    )
    if "default" in mc.servos:
        print(f"Drive is connected with {can_drive['baudrate']} baudrate.")
    else:
        raise (f"The drive can be connected with {can_drive['baudrate']} baudrate.")


def change_baudrate(can_drive: Dict[str, Any], new_baudrate: CAN_BAUDRATE) -> None:
    mc = MotionController()
    try:
        establish_canopen_communication(mc, can_drive)
    except IMException as e:
        print(e)
        return
    print("Starts to change the baudrate.")
    old_baudrate = mc.info.get_baudrate()
    if old_baudrate == new_baudrate:
        print(f"This drive already has this baudrate: {old_baudrate}.")
        return
    print(f"Old baudrate: {old_baudrate}")
    mc.configuration.change_baudrate(new_baudrate)

    can_drive["baudrate"] = new_baudrate
    mc.communication.disconnect()
    print("Drive is disconnected.")

    print(f"Make a power-cycle on your drive and connect it again using the new baudrate {new_baudrate}")


if __name__ == "__main__":
    # Remember to replace all parameters here
    # If you want to connect to a node manually, set the node_id parameter as an integer.
    # Instead, set the node_id parameter as a NoneType value to connect the first detected CAN node.
    can_drive = {
        "device": CAN_DEVICE.KVASER,
        "channel": 0,
        "node_id": None,
        "baudrate": CAN_BAUDRATE.Baudrate_1M,
        "dictionary_path": "\\\\awe-srv-max-prd\\distext\\products\\EVE-NET\\firmware\\2.5.1\\eve-net-c_can_2.5.1.xdf",
    }
    change_baudrate(can_drive, CAN_BAUDRATE.Baudrate_1M)

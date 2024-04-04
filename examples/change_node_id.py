from typing import Any, Dict

from ingenialink import CAN_BAUDRATE, CAN_DEVICE

from ingeniamotion.exceptions import IMException
from ingeniamotion.motion_controller import MotionController

import ingenialogger

logger = ingenialogger.get_logger(__name__)


def establish_canopen_communication(mc: MotionController, can_drive: Dict[str, Any]) -> None:
    print("Finding the available nodes...")
    node_id_list = mc.communication.scan_servos_canopen(
        can_drive["device"],
        baudrate=can_drive["baudrate"],
        channel=can_drive["channel"],
    )
    if not node_id_list:
        raise IMException(f"Any node is detected.")
    else:
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
        print(f"Drive is connected with {node_to_connect} as a node ID.")
    else:
        raise (f"The drive can be connected with {node_to_connect} as a node ID.")


def change_node_id(can_drive: Dict[str, Any], new_node_id: int) -> None:
    mc = MotionController()
    try:
        establish_canopen_communication(mc, can_drive)
    except IMException as e:
        print(e)
        return
    print("Starts to change the node ID.")
    old_node_id = mc.info.get_node_id()
    if old_node_id == new_node_id:
        print(f"This drive already has this node ID: {old_node_id}.")
        return
    print(f"Old node ID: {old_node_id}")
    mc.configuration.change_node_id(new_node_id)

    can_drive["node_id"] = new_node_id
    mc.communication.disconnect()
    print("Drive is disconnected.")

    print("Starts to establish a communication again.")
    try:
        establish_canopen_communication(mc, can_drive)
    except IMException as e:
        print(e)
        return

    mc.communication.disconnect()
    print("Drive is disconnected.")


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
    change_node_id(can_drive, 20)

from typing import Any, Dict

from ingenialink import CAN_BAUDRATE, CAN_DEVICE
from ingenialink.exceptions import ILFirmwareLoadError

from ingeniamotion.motion_controller import MotionController


def status_log(current_status: str) -> None:
    print(f"Load firmware status: {current_status}")


def progress_log(current_progress: int) -> None:
    print(f"Load firmware progress: {current_progress}%")


def load_firmware_canopen(can_drive: Dict[str, Any]) -> None:
    # Create MotionController instance
    mc = MotionController()
    # Find available nodes
    node_id_list = mc.communication.scan_servos_canopen(
        can_drive["device"],
        baudrate=can_drive["baudrate"],
        channel=can_drive["channel"],
    )
    if can_drive["node_id"] not in node_id_list:
        print("No nodes are connected.")
        return
    else:
        print(f"Found nodes: {node_id_list}")

    # Connect drive
    print("Starts to established a communication.")
    alias_can_servo = "custom_alias"
    mc.communication.connect_servo_canopen(
        can_drive["device"],
        can_drive["dictionary_path"],
        can_drive["node_id"],
        baudrate=can_drive["baudrate"],
        channel=can_drive["channel"],
        alias=alias_can_servo,
    )
    if alias_can_servo in mc.servos:
        print("Drive is connected.")
    else:
        print("Drive is not connected.")
        return

    # Load firmware
    print("Starts to load the firmware.")
    try:
        mc.communication.load_firmware_canopen(
            can_drive["fw_path"],
            servo=alias_can_servo,
            status_callback=status_log,
            progress_callback=progress_log,
        )
        print("Firmware is uploaded successfully.")
    except ILFirmwareLoadError as e:
        print(f"CAN boot error: {e}")
    finally:
        try:
            mc.communication.disconnect(alias_can_servo)
            print("Drive is disconnected.")
        except Exception as e:
            print(f"Error when disconnection from drive: {e}")


if __name__ == "__main__":
    # Remember to replace all parameters here
    can_drive = {
        "device": CAN_DEVICE.KVASER,
        "channel": 0,
        "baudrate": CAN_BAUDRATE.Baudrate_1M,
        "node_id": 20,
        "dictionary_path": "parent_directory/full_dictionary_path.xdf",
        "fw_path": "parent_directory/full_firmware_file_path.lfu",
    }
    load_firmware_canopen(can_drive)

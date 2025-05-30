from ingenialink import CanBaudrate, CanDevice
from ingenialink.exceptions import ILFirmwareLoadError

from ingeniamotion.motion_controller import MotionController


def status_log(current_status: str) -> None:
    print(f"Load firmware status: {current_status}")


def progress_log(current_progress: int) -> None:
    print(f"Load firmware progress: {current_progress}%")


def load_firmware_canopen(
    device: CanDevice,
    channel: int,
    baudrate: CanBaudrate,
    node_id: int,
    dictionary_path: str,
    fw_path: str,
) -> None:
    mc = MotionController()
    # Find available nodes
    node_id_list = mc.communication.scan_servos_canopen(device, baudrate, channel)
    if node_id not in node_id_list:
        print(f"Node {node_id} is not detected.")
        return
    else:
        print(f"Found nodes: {node_id_list}")

    print("Starts to establish a communication.")
    mc.communication.connect_servo_canopen(
        device,
        dictionary_path,
        node_id,
        baudrate,
        channel,
    )
    print("Drive is connected.")

    print("Starts to load the firmware.")
    try:
        mc.communication.load_firmware_canopen(
            fw_path,
            status_callback=status_log,
            progress_callback=progress_log,
        )
        print("Firmware is uploaded successfully.")
    except ILFirmwareLoadError as e:
        print(f"Firmware loading failed: {e}")
    mc.communication.disconnect()
    print("Drive is disconnected.")


if __name__ == "__main__":
    # Remember to replace all parameters here
    device = CanDevice.KVASER
    channel = 0
    baudrate = CanBaudrate.Baudrate_1M
    node_id = 32
    dictionary_path = "parent_directory/full_dictionary_path.xdf"
    fw_path = "parent_directory/full_firmware_file_path.lfu"
    load_firmware_canopen(device, channel, baudrate, node_id, dictionary_path, fw_path)

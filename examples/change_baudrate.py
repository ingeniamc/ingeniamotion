from typing import Optional

from ingenialink import CAN_BAUDRATE, CAN_DEVICE

from ingeniamotion.motion_controller import MotionController


def change_baudrate(
    device: CAN_DEVICE,
    channel: int,
    node_id: int,
    baudrate: CAN_BAUDRATE,
    dictionary_path: str,
    new_baudrate: CAN_BAUDRATE,
) -> None:
    mc = MotionController()
    mc.communication.connect_servo_canopen(device, dictionary_path, node_id, baudrate, channel)
    print(f"Drive is connected with {baudrate} baudrate.")
    print("Starts to change the baudrate.")
    old_baudrate = mc.info.get_baudrate()
    if old_baudrate == new_baudrate:
        print(f"This drive already has this baudrate: {old_baudrate}.")
        mc.communication.disconnect()
        return
    mc.configuration.change_baudrate(new_baudrate)
    print(f"Baudrate has been changed from {old_baudrate} to {new_baudrate}.")

    mc.communication.disconnect()
    print("Drive is disconnected.")
    print(
        f"Perform a power cycle and reconnect to the drive using the new baud rate: {new_baudrate}"
    )


if __name__ == "__main__":
    # Remember to replace all parameters here
    device = CAN_DEVICE.KVASER
    channel = 0
    node_id = 20
    baudrate = CAN_BAUDRATE.Baudrate_1M
    dictionary_path = "parent_directory/dictionary_file.xdf"
    new_baudrate = CAN_BAUDRATE.Baudrate_250K

    change_baudrate(device, channel, node_id, baudrate, dictionary_path, new_baudrate)

import argparse

from ingeniamotion import MotionController
from ingeniamotion.enums import CanBaudrate, CanDevice


def main(args):
    # Create MotionController instance
    mc = MotionController()

    # Get list of all node id available
    can_device = CanDevice(args.can_transceiver)
    can_baudrate = CanBaudrate(args.can_baudrate)
    can_channel = args.can_channel
    node_id_list = mc.communication.scan_servos_canopen(can_device, can_baudrate, can_channel)

    if len(node_id_list) > 0:
        # Connect to servo with CANOpen
        mc.communication.connect_servo_canopen(
            can_device, args.dictionary_path, args.node_id, can_baudrate, can_channel
        )
        print("Servo connected!")
        # Disconnect servo, this lines is mandatory
        mc.communication.disconnect()
    else:
        print("No node id available")


def setup_command():
    parser = argparse.ArgumentParser(description="Canopen example")
    parser.add_argument("--dictionary_path", help="Path to drive dictionary", required=True)
    parser.add_argument("--node_id", default=32, type=int, help="Node ID")
    parser.add_argument(
        "--can_transceiver",
        default="ixxat",
        choices=["pcan", "kvaser", "ixxat"],
        help="CAN transceiver",
    )
    parser.add_argument(
        "--can_baudrate",
        default=1000000,
        type=int,
        choices=[50000, 100000, 125000, 250000, 500000, 1000000],
        help="CAN baudrate",
    )
    parser.add_argument("--can_channel", default=0, type=int, help="CAN transceiver channel")
    return parser.parse_args()


if __name__ == "__main__":
    args = setup_command()
    main(args)

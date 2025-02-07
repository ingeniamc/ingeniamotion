import argparse

import ingeniamotion


def main(args):
    # Create MotionController instance
    mc = ingeniamotion.MotionController()

    # Connect drive
    mc.communication.connect_servo_ethernet(args.ip, args.dictionary_path)

    # Load firmware
    mc.communication.boot_mode_and_load_firmware_ethernet(args.firmware_file)


def setup_command():
    parser = argparse.ArgumentParser(description="Disturbance example")
    parser.add_argument("--dictionary_path", help="Path to drive dictionary", required=True)
    parser.add_argument("--ip", help="Drive IP address", required=True)
    parser.add_argument("--firmware_file", help="Firmware file to be loaded", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = setup_command()
    main(args)

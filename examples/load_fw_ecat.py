import argparse

import ingeniamotion


def main(args):
    # Create MotionController instance
    mc = ingeniamotion.MotionController()

    # Print infame list to get ifname index
    print(mc.communication.get_interface_name_list())

    # Load firmware
    mc.communication.load_firmware_ecat_interface_index(
        args.interface_index,  # ifname index
        args.firmware_file,  # FW file
        args.slave_id)  # Slave index


def setup_command():
    parser = argparse.ArgumentParser(description='Disturbance example')
    parser.add_argument('--interface_index', help='Network adapter inteface index', required=True)
    parser.add_argument('--slave_id', help='Drive slave ID', required=True)
    parser.add_argument('--firmware_file', help='Firmware file to be loaded', required=True)
    return parser.parse_args()


if __name__ == '__main__':
    args = setup_command()
    main(args)

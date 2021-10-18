import logging
import argparse
from ingeniamotion import MotionController


def setup_command():
    parser = argparse.ArgumentParser(description='Run feedback test')
    parser.add_argument('override', help='brake override',
                        choices=['disabled', 'release', 'enable'])
    parser.add_argument('dictionary_path', help='path to drive dictionary')
    parser.add_argument('-ip', default="192.168.2.22", help='drive ip address')
    parser.add_argument('--axis', default=1, help='drive axis')
    return parser.parse_args()


def main(args):
    # Create MotionController instance
    mc = MotionController()
    # Connect Servo with MotionController instance
    mc.communication.connect_servo_eoe(args.ip, args.dictionary_path)
    if args.override == "disabled":
        # Disable brake override
        mc.configuration.disable_brake_override(axis=args.axis)
    if args.override == "release":
        # Release brake
        mc.configuration.release_brake(axis=args.axis)
    if args.override == "enable":
        # Enable brake
        mc.configuration.enable_brake(axis=args.axis)
    mc.communication.disconnect()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    args = setup_command()
    main(args)

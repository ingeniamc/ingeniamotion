import logging
import argparse
from ingeniamotion import MotionController


def setup_command():
    parser = argparse.ArgumentParser(description='Run feedback test')
    parser.add_argument('override', help='brake override', choices=['disabled', 'release', 'enable'])
    parser.add_argument('dictionary_path', help='path to drive dictionary')
    parser.add_argument('-ip', default="192.168.2.22", help='drive ip address')
    parser.add_argument('--axis', default=1, help='drive axis')
    return parser.parse_args()


def main(args):
    mc = MotionController()
    # Connect Servo
    mc.comm.connect_servo_eoe(args.ip, args.dictionary_path)
    if args.override == "disabled":
        # Disable brake override
        mc.config.disable_brake_override(subnode=args.axis)
    if args.override == "release":
        # Release brake
        mc.config.release_brake(subnode=args.axis)
    if args.override == "enable":
        # Enable brake
        mc.config.enable_brake(subnode=args.axis)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    args = setup_command()
    main(args)

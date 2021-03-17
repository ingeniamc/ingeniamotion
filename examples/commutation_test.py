import logging
import argparse
from ingeniamotion import MotionController


def setup_command():
    parser = argparse.ArgumentParser(description='Run commutation test')
    parser.add_argument('dictionary_path', help='path to drive dictionary')
    parser.add_argument('-ip', default="192.168.2.22", help='drive ip address')
    parser.add_argument('--axis', default=1, help='drive axis')
    parser.add_argument('--debug', action='store_true',
                        help="with this flag test doesn't apply any change")
    return parser.parse_args()


def main(args):
    # Create MotionController instance
    mc = MotionController()
    # Connect Servo with MotionController instance
    mc.communication.connect_servo_eoe(args.ip, args.dictionary_path)
    # Run Commutation test
    result = mc.tests.commutation(axis=args.axis,
                                  apply_changes=not args.debug)
    logging.info(result["message"])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    args = setup_command()
    main(args)

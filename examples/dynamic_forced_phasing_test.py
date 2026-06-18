import logging
import argparse
from ingeniamotion import MotionController


def setup_command():
    parser = argparse.ArgumentParser(description="Run dynamic forced phasing test")
    parser.add_argument("dictionary_path", help="path to drive dictionary")
    parser.add_argument("--ifname", help="interface name")
    parser.add_argument("--slave_id", help="slave ID", default=1, type=int)
    parser.add_argument("--axis", default=1, help="drive axis")
    parser.add_argument(
        "--debug", action="store_true", help="with this flag test doesn't apply any change"
    )
    return parser.parse_args()


def main(args):
    # Create MotionController instance
    mc = MotionController()
    # Connect Servo with MotionController instance
    mc.communication.connect_servo_ethercat(args.ifname, args.slave_id, args.dictionary_path)
    # Run Dynamic Forced Phasing test
    result = mc.tests.dynamic_forced_phasing(axis=args.axis, apply_changes=not args.debug)
    logging.info(result.result_message)
    mc.communication.disconnect()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    args = setup_command()
    main(args)

import logging
import argparse
from ingeniamotion import MotionController


def setup_command():
    parser = argparse.ArgumentParser(description='Run feedback test')
    parser.add_argument('feedback', help='feedback to test', choices=['HALLS', 'QEI', 'QEI2'])
    parser.add_argument('dictionary_path', help='path to drive dictionary')
    parser.add_argument('-ip', default="192.168.2.22", help='drive ip address')
    parser.add_argument('--axis', default=1, help='drive axis')
    parser.add_argument('--debug', action='store_true',
                        help="with this flag test doesn't apply any change")
    return parser.parse_args()


def main(args):
    mc = MotionController()
    mc.comm.connect_servo_eoe(args.ip, args.dictionary_path)
    feedback_type = {
        "HALLS": mc.tests.digital_halls_test,
        "QEI": mc.tests.incremental_encoder_1_test,
        "QEI2": mc.tests.incremental_encoder_2_test
    }
    result = feedback_type[args.feedback](subnode=args.axis,
                                          apply_changes=not args.debug)
    if not isinstance(result, int):
        logging.info(result["message"])


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    args = setup_command()
    main(args)

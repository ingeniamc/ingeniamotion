import argparse

from ingeniamotion import MotionController


def main(args):
    mc = MotionController()
    mc.communication.connect_servo_eoe(args.ip, args.dictionary_path)
    mc.communication.set_register("DRV_PROT_USER_OVER_VOLT", 60)
    volt = mc.communication.get_register("DRV_PROT_VBUS_VALUE")
    print("Current voltage is", volt)
    mc.communication.disconnect()


def setup_command():
    parser = argparse.ArgumentParser(description="Disturbance example")
    parser.add_argument("--dictionary_path", help="Path to drive dictionary", required=True)
    parser.add_argument("--ip", help="Drive IP address", required=True)
    return parser.parse_args()


if __name__ == "__main__":
    args = setup_command()
    main(args)

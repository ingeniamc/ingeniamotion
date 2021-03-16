import time
import logging
import argparse
from ingeniamotion import MotionController
from ingenialink.exceptions import ILError


def setup_command():
    parser = argparse.ArgumentParser(description='Run feedback test')
    parser.add_argument('demo', help='Run demo',
                        choices=['velocity', 'torque'])
    parser.add_argument('dictionary_path', help='path to drive dictionary')
    parser.add_argument('-ip', default="192.168.2.22", help='drive ip address')
    return parser.parse_args()


def velocity_ramp(final_velocity, acceleration, mc):
    done = False
    mc.configuration.set_max_acceleration(acceleration)
    mc.motion.set_velocity(final_velocity)
    while not done:
        try:
            mc.motion.wait_for_velocity(final_velocity)
            done = True
        except ILError:
            pass


def torque_ramp(final_torque, rotatum, mc):
    torque = 0
    torque_constant = 0.0376
    init_time = time.time()
    while torque < final_torque:
        try:
            torque = (time.time() - init_time) * rotatum
            current = torque / torque_constant
            mc.motion.set_current_quadrature(current)
        except ILError:
            pass


def velocity_demo(mc):
    mc.motion.set_operation_mode(mc.motion.OperationMode.PROFILE_VELOCITY)
    mc.configuration.set_max_velocity(70)
    mc.motion.motor_enable()
    velocity_ramp(16.667, 0.1667, mc)
    velocity_ramp(66.667, 0.8333, mc)
    time.sleep(40)
    velocity_ramp(0, 20, mc)
    mc.motion.motor_disable()


def torque_demo(mc):
    mc.motion.set_operation_mode(mc.motion.OperationMode.CURRENT)
    mc.motion.motor_enable()
    torque_ramp(0.706, 0.0035, mc)
    mc.motion.set_current_quadrature(0)
    mc.motion.motor_disable()


def main(args):
    mc = MotionController()
    mc.communication.connect_servo_eoe(args.ip, args.dictionary_path)
    if args.demo == "velocity":
        velocity_demo(mc)
    elif args.demo == "torque":
        torque_demo(mc)
    else:
        logging.error("Demo {} does not exist".format(args.demo))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    args = setup_command()
    main(args)

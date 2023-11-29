import time
import logging
import argparse
from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode
from ingenialink.exceptions import ILError

# Set your motor torque constant
TORQUE_CONSTANT = 0.0376


def setup_command():
    parser = argparse.ArgumentParser(description='Run feedback test')
    parser.add_argument('demo', help='Run demo',
                        choices=['velocity', 'torque'])
    parser.add_argument('dictionary_path', help='path to drive dictionary')
    parser.add_argument('-ip', default="192.168.2.22", help='drive ip address')
    parser.add_argument('-target_torque', default=0.706, help='Target torque', type=float)
    return parser.parse_args()


def velocity_ramp(final_velocity, acceleration, mc):
    """
    Creates a velocity ramp from current velocity to ``final_velocity`` with ``acceleration`` as a ramp slope.

    Args:
        final_velocity: target velocity in rev/s.
        acceleration: acceleration in rev/s^2.
        mc: MotionController instance.
    """
    done = False
    mc.configuration.set_max_acceleration(acceleration)
    mc.motion.set_velocity(final_velocity)
    while not done:
        try:
            mc.motion.wait_for_velocity(final_velocity)
            done = True
        except ILError:
            pass


def torque_ramp(final_torque, rotatum, torque_constant, mc):
    """
    Creates a torque ramp from 0 to ``final_torque`` with ``rotatum`` as a ramp slope.

    Args:
        final_torque: target torque in Nm.
        rotatum: torque derivative in Nm/s.
        torque_constant: motor torque constant.
        mc: MotionController instance.
    """
    torque = 0
    torque_constant = torque_constant
    init_time = time.time()
    while torque < final_torque:
        try:
            torque = (time.time() - init_time) * rotatum
            current = torque / torque_constant
            mc.motion.set_current_quadrature(current)
        except ILError:
            pass


def velocity_demo(mc):
    wait_in_seconds = 40
    target_velocity = [16.667, 66.667, 0]
    acceleration = [0.1667, 0.8333, 20]
    mc.motion.set_operation_mode(OperationMode.PROFILE_VELOCITY)
    mc.configuration.set_max_velocity(70)
    mc.motion.motor_enable()
    velocity_ramp(target_velocity[0], acceleration[0], mc)
    velocity_ramp(target_velocity[1], acceleration[1], mc)
    time.sleep(wait_in_seconds)
    velocity_ramp(target_velocity[2], acceleration[2], mc)
    mc.motion.motor_disable()


def torque_demo(mc, target_torque):
    rotatum = 0.0035
    mc.motion.set_operation_mode(OperationMode.CURRENT)
    mc.motion.motor_enable()
    torque_ramp(target_torque, rotatum, TORQUE_CONSTANT, mc)
    mc.motion.set_current_quadrature(0)
    mc.motion.motor_disable()


def main(args):
    mc = MotionController()
    mc.communication.connect_servo_eoe(args.ip, args.dictionary_path)
    if args.demo == "velocity":
        velocity_demo(mc)
    elif args.demo == "torque":
        torque_demo(mc, args.target_torque)
    else:
        logging.error("Demo {} does not exist".format(args.demo))
    mc.communication.disconnect()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    args = setup_command()
    main(args)

from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode


def position_ramp(final_position, mc: MotionController) -> None:
    """
    Creates a position ramp from current position to ``final_position`` as a ramp slope.

    Args:
        final_position: target position in counts.
        mc: Controller with all the functions needed to perform a position ramp.
    """
    done = False
    mc.motion.move_to_position(final_position)
    while not done:
        mc.motion.wait_for_position(final_position)
        done = True


def main() -> None:
    mc = MotionController()
    ip = "192.168.2.1"
    slave_id = 1
    dictionary_path = (
        "\\\\awe-srv-max-prd\\distext\\products\\CAP-NET\\firmware\\2.5.1\\cap-net-e_eoe_2.5.1.xdf"
    )
    mc.communication.connect_servo_ethercat_interface_ip(ip, slave_id, dictionary_path)

    # Select the position mode and trapezoidal profiler
    mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION)
    # Set all registers needed before activating the trapezoidal profiler
    mc.configuration.set_max_profile_velocity(5.0)
    max_acceleration_deceleration = 2.0
    mc.configuration.set_max_profile_acceleration(max_acceleration_deceleration)
    mc.configuration.set_max_profile_deceleration(max_acceleration_deceleration)
    # Enable the motor
    mc.motion.motor_enable()

    target_positions = [1500, 3000, 0]
    for current_target in target_positions:
        position_ramp(current_target, mc)
        actual_position = mc.motion.get_actual_position()
        print(f"Actual final position: {actual_position}")

    # Disable the motor
    mc.motion.motor_disable()

    mc.communication.disconnect()


if __name__ == "__main__":
    # Before running this example, setting-up the drive with a connected motor is required
    main()

from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode


def main() -> None:
    mc = MotionController()
    ip = "192.168.2.1"
    slave_id = 1
    dictionary_path = (
        "parent_directory/dictionary_file.xdf"
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
        mc.motion.move_to_position(current_target, blocking=True, timeout=2.0)
        actual_position = mc.motion.get_actual_position()
        print(f"Actual position: {actual_position}")

    # Disable the motor
    mc.motion.motor_disable()

    mc.communication.disconnect()


if __name__ == "__main__":
    # Before running this example, setting-up the drive with a connected motor is required
    main()

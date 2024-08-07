from ingeniamotion import MotionController


def main() -> None:
    mc = MotionController()
    # Modify these parameters to connect a drive
    interface_index = 3
    slave_id = 1
    dictionary_path = "parent_directory/dictionary_file.xdf"
    mc.communication.connect_servo_ethercat_interface_index(
        interface_index, slave_id, dictionary_path
    )
    # Save the initial configuration of your drive in a file
    initial_config_path = "initial_configuration.xcf"
    mc.configuration.save_configuration(initial_config_path)
    print("The initial configuration is saved.")

    # Get the initial max. velocity and set it with a new value
    new_max_velocity = 20.0
    initial_max_velocity = mc.configuration.get_max_velocity()
    if new_max_velocity == initial_max_velocity:
        print("This max. velocity value is already set.")
        mc.communication.disconnect()
        return
    mc.configuration.set_max_velocity(new_max_velocity)

    # Save the configuration with changes in a file
    modified_config_path = "configuration_example.xcf"
    mc.configuration.save_configuration(modified_config_path)
    print("The configuration file is saved with the modification.")

    # Load the initial configuration and check the max. velocity register has its initial value
    mc.configuration.load_configuration(initial_config_path)
    print(
        f"Max. velocity register should be set to its initial value ({initial_max_velocity}). "
        f"Current value: {mc.configuration.get_max_velocity()}"
    )

    # Load the modified configuration and check the max. velocity value is changed again
    mc.configuration.load_configuration(modified_config_path)
    print(
        f"Max. velocity register should now be set to the new value ({new_max_velocity}). "
        f"Current value: {mc.configuration.get_max_velocity()}"
    )

    mc.communication.disconnect()


if __name__ == "__main__":
    main()

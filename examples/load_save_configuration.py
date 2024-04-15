from ingeniamotion import MotionController


def main() -> None:
    mc = MotionController()
    # Modify these parameters to connect a drive
    interface_index = 3
    slave_id = 1
    dictionary_path = (
        "parent_directory/dictionary_file.xdf"
    )
    mc.communication.connect_servo_ethercat_interface_index(
        interface_index, slave_id, dictionary_path
    )
    # Save the configuration of your drive in a file
    config_path = "configuration.xcf"
    mc.configuration.save_configuration(config_path)
    print("The configuration is saved.")

    # Load the configuration file made previously
    mc.configuration.load_configuration(config_path)

    mc.communication.disconnect()


if __name__ == "__main__":
    main()

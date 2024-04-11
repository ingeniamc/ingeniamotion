import time

from ingeniamotion.motion_controller import MotionController


def establish_coe_connection(mc: MotionController) -> None:
    """Establish an EtherCAT-CoE communication.

    Find all available nodes, and perform a communication.

    Args:
        mc: The object where there are all functions to establish a communication.
    """
    # Modify these parameters to connect a drive
    interface_index = 3
    slave_id = 1
    dictionary_path = (
        "\\\\awe-srv-max-prd\\distext\\products\\CAP-NET\\firmware\\2.5.1\\cap-net-e_eoe_2.5.1.xdf"
    )

    interface_selected = mc.communication.get_ifname_by_index(interface_index)
    slave_id_list = mc.communication.scan_servos_ethercat(interface_selected)

    if not slave_id_list:
        interface_list = mc.communication.get_interface_name_list()
        print(f"No slave detected on interface: {interface_list[interface_index]}")
        return
    else:
        print(f"Found slaves: {slave_id_list}")

    mc.communication.connect_servo_ethercat(interface_selected, slave_id, dictionary_path)


def update_position_value_using_pdo(mc: MotionController) -> None:
    """Updates the position of a motor using PDOs.

    Args:
        mc : The controller where there are all functions to perform PDO exchange.
    """
    position_value = 0
    waiting_time_for_pdo_exchange = 5
    # Create a RPDO map item
    position_set_point = mc.capture.pdo.create_pdo_item(
        "CL_POS_SET_POINT_VALUE", value=position_value
    )
    # Create a TPDO map item
    actual_position = mc.capture.pdo.create_pdo_item("CL_POS_FBK_VALUE")
    # Create the RPDO and TPDO maps
    rpdo_map, tpdo_map = mc.capture.pdo.create_pdo_maps([position_set_point], [actual_position])
    # Map the PDO maps to the slave
    mc.capture.pdo.set_pdo_maps_to_slave(rpdo_map, tpdo_map)
    # Start the PDO exchange
    mc.capture.pdo.start_pdos()
    time.sleep(waiting_time_for_pdo_exchange)
    print(f"Actual Position: {actual_position.value}")
    print(f"Position set-point: {position_set_point.value}")
    # Increase the position set point
    position_set_point.value += 500
    time.sleep(waiting_time_for_pdo_exchange)
    # Get the actual position value
    print(f"Actual Position: {actual_position.value}")
    print(f"Position set-point: {position_set_point.value}")
    # Stop the PDO exchange
    mc.capture.pdo.stop_pdos()


def main() -> None:
    # Before running this example, the drive has to be configured for a your motor.
    mc = MotionController()
    establish_coe_connection(mc)
    print("Drive is connected.")
    mc.motion.motor_enable()
    print(f"Motor is enabled.")
    update_position_value_using_pdo(mc)
    print("Actual value is updated.")
    mc.motion.motor_disable()
    print("Motor is disabled.")
    mc.communication.disconnect()
    print("The drive has been disconnected.")


if __name__ == "__main__":
    main()

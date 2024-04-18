import time
from functools import partial

from ingenialink.pdo import RPDOMapItem, TPDOMapItem

from ingeniamotion.motion_controller import MotionController


def notify_actual_value(actual_position: TPDOMapItem) -> None:
    """Callback that is subscribed to get the actual position for cycle.

    Args:
        actual_position: TPDO mapped to the Actual position register.

    """
    print(f"Actual Position: {actual_position.value}")


def update_position_set_point(position_set_point: RPDOMapItem) -> None:
    """Callback to update the position set point value for each cycle.

    Args:
        position_set_point: RPDO mapped to the Position set-point register.
    """
    position_set_point.value += 100
    print(f"Position set-point: {position_set_point.value}")


def update_position_value_using_pdo(mc: MotionController) -> None:
    """Updates the position of a motor using PDOs.

    Args:
        mc : Controller with all the functions needed to perform a PDO exchange.
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
    # Callbacks subscriptions for TPDO and RPDO map items
    mc.capture.pdo.subscribe_to_receive_process_data(partial(notify_actual_value, actual_position))
    mc.capture.pdo.subscribe_to_send_process_data(
        partial(update_position_set_point, position_set_point)
    )
    # Map the PDO maps to the slave
    mc.capture.pdo.set_pdo_maps_to_slave(rpdo_map, tpdo_map)
    # Start the PDO exchange
    mc.capture.pdo.start_pdos()
    time.sleep(waiting_time_for_pdo_exchange)
    # Stop the PDO exchange
    mc.capture.pdo.stop_pdos()


def main() -> None:
    # Before running this example, the drive has to be configured for a your motor.
    mc = MotionController()

    # Modify these parameters to connect a drive
    interface_ip = "192.168.2.1"
    slave_id = 1
    dictionary_path = "parent_directory/dictionary_file.xdf"
    mc.communication.connect_servo_ethercat_interface_ip(interface_ip, slave_id, dictionary_path)
    print("Drive is connected.")
    mc.motion.motor_enable()
    print("Motor is enabled.")
    update_position_value_using_pdo(mc)
    mc.motion.motor_disable()
    print("Motor is disabled.")
    mc.communication.disconnect()
    print("The drive has been disconnected.")


if __name__ == "__main__":
    main()

import contextlib

from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode
from ingeniamotion.exceptions import IMTimeoutError


def main(interface_ip, slave_id, dict_path):
    """Establish a FSoE connection, deactivate the STO and
    move the motor."""
    mc = MotionController()
    # Connect to the servo drive
    mc.communication.connect_servo_ethercat_interface_ip(interface_ip, slave_id, dict_path)
    current_operation_mode = mc.motion.get_operation_mode()
    # Set the Operation mode to Velocity
    mc.motion.set_operation_mode(OperationMode.VELOCITY)
    # Create and start the FSoE master handler
    mc.fsoe.create_fsoe_master_handler()
    mc.fsoe.start_master(start_pdos=True)
    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data()
    # Deactivate the STO
    mc.fsoe.sto_deactivate()
    # Wait for the STO to be deactivated
    while mc.fsoe.check_sto_active():
        pass
    # Enable the motor
    mc.motion.motor_enable()
    # Wait for the motor to reach a certain velocity (10 rev/s)
    target_velocity = 10
    mc.motion.set_velocity(target_velocity)
    with contextlib.suppress(IMTimeoutError):
        mc.motion.wait_for_velocity(velocity=target_velocity, timeout=5)
    # Activate the STO
    mc.fsoe.sto_activate()
    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)
    # Disable the motor
    mc.motion.motor_disable()
    # Restore the operation mode
    mc.motion.set_operation_mode(current_operation_mode)
    # Disconnect from the servo drive
    mc.communication.disconnect()


if __name__ == '__main__':
    # Modify these parameters according to your setup
    network_interface_ip = "192.168.2.1"
    ethercat_slave_id = 1
    dictionary_path = "safe_dict.xdf"
    main(network_interface_ip, ethercat_slave_id, dictionary_path)

import argparse
import contextlib

from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode
from ingeniamotion.exceptions import IMTimeoutError


def _error_callback(error):
    print(error)


def main(ifname, slave_id, dict_path):
    """Establish a FSoE connection, deactivate the STO and move the motor."""
    mc = MotionController()
    # Configure error channel
    mc.fsoe.subscribe_to_errors(_error_callback)
    # Connect to the servo drive
    mc.communication.connect_servo_ethercat(ifname, slave_id, dict_path)
    current_operation_mode = mc.motion.get_operation_mode()
    # Set the Operation mode to Velocity
    mc.motion.set_operation_mode(OperationMode.VELOCITY)
    # Create and start the FSoE master handler
    mc.fsoe.create_fsoe_master_handler(use_sra=False)
    mc.fsoe.configure_pdos(start_pdos=True)
    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=10)
    # Deactivate the SS1
    mc.fsoe.ss1_deactivate()
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
    # Disable the motor
    mc.motion.motor_disable()
    # Activate the SS1
    mc.fsoe.sto_activate()
    # Activate the STO
    mc.fsoe.sto_activate()
    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)
    # Restore the operation mode
    mc.motion.set_operation_mode(current_operation_mode)
    # Disconnect from the servo drive
    mc.communication.disconnect()


if __name__ == "__main__":
    # Modify these parameters according to your setup
    parser = argparse.ArgumentParser(description="Safety Torque Off Example")
    parser.add_argument(
        "--ifname", help="Interface name ``\\Device\\NPF_[...]``", required=True, type=str
    )
    parser.add_argument(
        "--slave_id", help="Path to drive dictionary", required=False, default=1, type=int
    )
    parser.add_argument(
        "--dictionary_path", help="Path to drive dictionary", required=True, type=str
    )

    args = parser.parse_args()

    main(args.ifname, args.slave_id, args.dictionary_path)

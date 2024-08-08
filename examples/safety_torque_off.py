import time

from ingenialink.enums.register import REG_ACCESS, REG_DTYPE
from ingenialink.ethercat.register import EthercatRegister

from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode

LAST_ERROR = EthercatRegister(
    identifier="LAST_ERROR",
    idx=0x400f,
    subidx=0x00,
    dtype=REG_DTYPE.U32,
    access=REG_ACCESS.RO,
)


def get_last_error(mc):
    drive = mc.servos["default"]
    error = drive.read(LAST_ERROR)

    print(f"Last error {error:x}")


def main(interface_ip, slave_id, dict_path):
    """Establish a FSoE connection, deactivate the STO and
    move the motor."""
    mc = MotionController()
    # Configure error channel
    mc.fsoe.subscribe_to_errors(lambda error: print(error))
    # Connect to the servo drive
    mc.communication.connect_servo_ethercat_interface_ip(interface_ip, slave_id, dict_path)
    current_operation_mode = mc.motion.get_operation_mode()
    # Set the Operation mode to Velocity
    mc.motion.set_operation_mode(OperationMode.VELOCITY)
    # Create and start the FSoE master handler
    mc.fsoe.create_fsoe_master_handler()
    get_last_error(mc)
    mc.fsoe.configure_pdos(start_pdos=True)
    time.sleep(2)
    mc.fsoe.sto_deactivate()
    time.sleep(10)

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)
    get_last_error(mc)

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

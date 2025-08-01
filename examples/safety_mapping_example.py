import argparse
import time

from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED
from ingeniamotion.motion_controller import MotionController

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import (
        SafeInputsFunction,
        SAFunction,
        SOSFunction,
        SS1Function,
        SS2Function,
        STOFunction,
        SVFunction,
    )


def main(interface_ip, slave_id, dict_path) -> None:
    """Establish a FSoE connection, deactivate the STO and move the motor.

    Args:
        interface_ip: IP address of the network interface to use.
        slave_id (int): ID of the servo drive to connect to.
        dict_path: Path to the drive dictionary file.

    Raises:
        FSoEFrameConstructionError: If the FSoE frame construction is invalid.
    """
    mc = MotionController()
    # Configure error channel
    mc.fsoe.subscribe_to_errors(lambda error: print(error))
    # Connect to the servo drive
    mc.communication.connect_servo_ethercat(interface_ip, slave_id, dict_path)

    # Create and start the FSoE master handler
    handler = mc.fsoe.create_fsoe_master_handler(use_sra=True)

    sto = handler.get_function_instance(STOFunction)
    safe_inputs = handler.get_function_instance(SafeInputsFunction)
    ss1 = handler.get_function_instance(SS1Function)
    ss2 = handler.get_function_instance(SS2Function, instance=1)
    sa = handler.get_function_instance(SAFunction)
    sv = handler.get_function_instance(SVFunction)
    sos = handler.get_function_instance(SOSFunction)

    # The handler comes with a default mapping read from the drive.
    # Clear it to create a new one
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()

    # Configure Outputs map
    outputs = handler.maps.outputs
    outputs.add(sto.command)
    outputs.add(ss1.command)
    outputs.add(sos.command)
    outputs.add(ss2.command)
    outputs.add_padding(4 + 8)

    # Configure Inputs Map
    inputs = handler.maps.inputs
    inputs.add(sto.command)
    inputs.add(ss1.command)
    inputs.add_padding(6)
    inputs.add(safe_inputs.value)
    inputs.add_padding(7)

    # Check that the maps are valid
    handler.maps.validate()

    # Print the maps to check the configuration
    print("Inputs Map:")
    print(inputs.get_text_representation())
    print("Outputs Map:")
    print(outputs.get_text_representation())

    # Configure Parameters
    # safe_inputs.map.set(2)  # Linked to SS1 Instance

    # Configure the pdos the FSoE master handler
    mc.fsoe.configure_pdos()

    # After reconfiguring the maps and configuring the pdos,
    # The PDOs can be printed to check the mapping
    print("Outputs PDO Map:")
    print(handler.safety_master_pdu_map.get_text_representation())
    print("Inputs PDO Map:")
    print(handler.safety_slave_pdu_map.get_text_representation())

    # Start pdo transmission
    mc.capture.pdo.start_pdos()

    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=10)

    # Remove fail-safe mode. Output commands will be applied by the slaves
    mc.fsoe.set_fail_safe(False)

    # Stay 5 seconds in Data state
    for i in range(5):
        time.sleep(1)
        # During this time, commands can be changed
        sto.command.set(1)
        ss1.command.set(1)
        # And inputs can be read
        print(f"Safe Inputs Value: {safe_inputs.value.get()}")

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)
    # Disconnect from the servo drive
    mc.communication.disconnect()


if __name__ == "__main__":
    # Example of how to run the script:
    # py -3.9 safety_mapping_example.py --interface_ip 192.168.2.1 --dictionary_path "C:\dictionary\evs-s-net-e_1.2.3_v3.xdf"

    parser = argparse.ArgumentParser(description="Safety Mapping Example")
    parser.add_argument(
        "--interface_ip", help="Interface IP of the network device to use", required=True, type=str
    )
    parser.add_argument(
        "--slave_id", help="Path to drive dictionary", required=False, default=1, type=int
    )
    parser.add_argument(
        "--dictionary_path", help="Path to drive dictionary", required=True, type=str
    )

    args = parser.parse_args()

    main(args.interface_ip, args.slave_id, args.dictionary_path)

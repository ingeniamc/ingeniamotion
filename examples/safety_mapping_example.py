import time

from ingeniamotion import MotionController
import argparse

from ingeniamotion.fsoe_master import STOFunction, SS1Function, PDUMaps
from ingeniamotion.fsoe_master.safety_functions import SS2Function, SafeInputsFunction, SAFunction


def main(interface_ip, slave_id, dict_path):
    """Establish a FSoE connection, deactivate the STO and move the motor."""
    mc = MotionController()
    # Configure error channel
    mc.fsoe.subscribe_to_errors(lambda error: print(error))
    # Connect to the servo drive
    mc.communication.connect_servo_ethercat_interface_ip(interface_ip, slave_id, dict_path)

    # Create and start the FSoE master handler
    handler = mc.fsoe.create_fsoe_master_handler(use_sra=False)

    # Get the safety functions instances
    sto = handler.get_function_instance(STOFunction)
    safe_inputs = handler.get_function_instance(SafeInputsFunction)
    ss1 = handler.get_function_instance(SS1Function)
    ss2 = handler.get_function_instance(SS2Function, instance=1)
    sa = handler.get_function_instance(SAFunction)

    # The handler comes with a default mapping read from the drive.
    # Clear it to create a new one
    handler.maps.inputs.clear()
    handler.maps.outputs.clear()

    # Configure Outputs map
    outputs = handler.maps.outputs
    outputs.add(sto.command)
    outputs.add(ss1.command)
    outputs.add(ss2.command)
    outputs.add_padding(5 + 8)

    # Configure Inputs Map
    inputs = handler.maps.inputs
    inputs.add(sto.command)
    inputs.add(ss1.command)
    inputs.add(ss2.command)
    inputs.add_padding(5)
    inputs.add(safe_inputs.value)
    inputs.add_padding(7)
    # inputs.add(sa.value)

    # Configure Parameters
    safe_inputs.map.set(2)  # Linked to SS1 Instance

    # Configure the pdos the FSoE master handler
    mc.fsoe.configure_pdos()

    # After reconfiguring the maps and configuring the pdos,
    # The PDOs can be printed to check the mapping
    print(handler.safety_master_pdu_map.get_text_representation())
    print(handler.safety_slave_pdu_map.get_text_representation())

    # Start pdo transmission
    mc.capture.pdo.start_pdos()

    # Wait for the master to reach the Data state
    mc.fsoe.wait_for_state_data(timeout=10)

    # Stay 5 seconds in Data state
    time.sleep(5)

    # Stop the FSoE master handler
    mc.fsoe.stop_master(stop_pdos=True)
    # Disconnect from the servo drive
    mc.communication.disconnect()


if __name__ == "__main__":
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

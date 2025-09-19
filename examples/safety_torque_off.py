import argparse
import contextlib

from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode
from ingeniamotion.exceptions import IMTimeoutError
from ingeniamotion.fsoe import FSOE_MASTER_INSTALLED

if FSOE_MASTER_INSTALLED:
    from ingeniamotion.fsoe_master import (
        FSoEMasterHandler,
        SafeInputsFunction,
        SS1Function,
        STOFunction,
    )


def _error_callback(error):
    print(error)


def _set_default_mapping(handler: "FSoEMasterHandler") -> None:
    sto = handler.get_function_instance(STOFunction)
    safe_inputs = handler.get_function_instance(SafeInputsFunction)
    ss1 = handler.get_function_instance(SS1Function)

    handler.maps.inputs.clear()
    handler.maps.inputs.add(sto.command)
    handler.maps.inputs.add(ss1.command)
    handler.maps.inputs.add_padding(6)
    handler.maps.inputs.add(safe_inputs.value)
    handler.maps.inputs.add_padding(7)

    handler.maps.outputs.clear()
    handler.maps.outputs.add(sto.command)
    handler.maps.outputs.add(ss1.command)
    handler.maps.outputs.add_padding(6)


def main(ifname, slave_id, dict_path, config_file=None):
    """Establish a FSoE connection, deactivate the STO and move the motor."""
    mc = MotionController()
    # Configure error channel
    mc.fsoe.subscribe_to_errors(_error_callback)
    # Connect to the servo drive
    mc.communication.connect_servo_ethercat(ifname, slave_id, dict_path)
    # Load configuration if provided
    if config_file is not None:
        try:
            mc.configuration.load_configuration(config_file)
        except Exception as e:
            print(f"There was an error loading the configuration: {e}")
            mc.communication.disconnect()
            return
    current_operation_mode = mc.motion.get_operation_mode()
    # Set the Operation mode to Velocity
    mc.motion.set_operation_mode(OperationMode.VELOCITY)
    # Create and start the FSoE master handler
    handler = mc.fsoe.create_fsoe_master_handler(use_sra=True)
    # Set default mapping if editable
    if handler.maps.editable:
        _set_default_mapping(handler=handler)
    if handler.sout_function():
        handler.sout_disable()
    try:
        mc.fsoe.configure_pdos(start_pdos=True)
        # Wait for the master to reach the Data state
        mc.fsoe.wait_for_state_data(timeout=5)
        # Remove fail-safe mode. Output commands will be applied by the slaves
        mc.fsoe.set_fail_safe(False)
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
            mc.motion.wait_for_velocity(velocity=target_velocity, timeout=10)
        # Disable the motor
        mc.motion.motor_disable()
        # Activate the SS1
        mc.fsoe.ss1_activate()
        # Activate the STO
        mc.fsoe.sto_activate()
        # Restore fail safe
        mc.fsoe.set_fail_safe(True)
    except Exception as e:
        print(e)
    finally:
        try:
            # Stop the FSoE master handler
            if mc.capture.pdo.is_active:
                mc.fsoe.stop_master(stop_pdos=True)
        finally:
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
    parser.add_argument(
        "--configuration_file",
        help="Path to configuration file",
        required=False,
        type=str,
        default=None,
    )

    args = parser.parse_args()

    main(args.ifname, args.slave_id, args.dictionary_path, args.configuration_file)

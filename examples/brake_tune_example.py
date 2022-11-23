import logging
import threading
from pynput import keyboard

from ingeniamotion import MotionController
from ingeniamotion.enums import CAN_BAUDRATE, CAN_DEVICE
from ingeniamotion.wizard_tests.brake_tune import BrakeTune


mc = MotionController()
brake_example = None


def register_loggers():
    global mc
    print(f'Brake current feedback source: {mc.communication.get_register("MOT_BRAKE_CUR_FBK")}')
    print(f'Brake Activation Current: {mc.communication.get_register("MOT_BRAKE_ACTIVATION_CUR")} A')
    print(f'Brake Holding Current: {mc.communication.get_register("MOT_BRAKE_HOLDING_CUR")} A')
    print(f'Brake Activation Time: {mc.communication.get_register("MOT_BRAKE_ACTIVATION_TIME")} ms')
    print(f'Brake Current Control Kp: {mc.communication.get_register("MOT_BRAKE_CL_KP")} 1/A')
    print(f'Brake Current Control Ki: {mc.communication.get_register("MOT_BRAKE_CL_KI")} Hz')
    print(f'Analog Input 1 - Gain: {mc.communication.get_register("IO_ANA1_GAIN")}')
    print(f'Analog Input 1 - Offset: {mc.communication.get_register("IO_ANA1_OFFSET")} A')
    print(f'Digital Outputs Set Value: {mc.communication.get_register("IO_OUT_SET_POINT")}')
    print(f'Brake Override: {mc.communication.get_register("MOT_BRAKE_OVERRIDE")}')


def canopen_connection():
    global mc
    # Connect Servo with MotionController instance
    dict_path = ""
    eds_path = ""
    node_id_list = mc.communication.scan_servos_canopen(
        CAN_DEVICE.PCAN, CAN_BAUDRATE.Baudrate_1M, channel=0)

    if len(node_id_list) > 0:
        mc.communication.connect_servo_canopen(
            CAN_DEVICE.PCAN,  # Peak as a CANOpen device
            # CAN_DEVICE.KVASER and CAN_DEVICE.IXXAT are available too
            dict_path,  # Drive dictionary
            eds_path,  # Drive EDS file
            node_id_list[0],  # First node id found
            CAN_BAUDRATE.Baudrate_1M,  # 1Mbit/s as a baudrate
            # More baudrates are available: Baudrate_500K, Baudrate_250K, etc...
            channel=0  # First CANOpen device channel selected.
        )
        print("Servo connected!")

    return node_id_list


def brake_tuning_configuration():
    global mc
    mc.communication.set_register("MOT_BRAKE_CONTROL_MODE", 1)
    mc.communication.set_register("MOT_BRAKE_CUR_FBK", 1)
    mc.communication.set_register("MOT_BRAKE_HOLDING_CUR", 0.4)
    mc.communication.set_register("MOT_BRAKE_CL_KP", 2.0)
    mc.communication.set_register("MOT_BRAKE_CL_KI", 200.0)
    mc.communication.set_register("IO_ANA1_GAIN", 2.64)
    mc.communication.set_register("IO_ANA1_OFFSET", -0.655)
    mc.communication.set_register("IO_OUT_SET_POINT", 1)
    print("Parameter settings:")
    print("-------------------")
    register_loggers()


def on_press(key):
    global brake_example
    if not brake_example.is_stopped:
        if "s" in str(key):
            print("\ns key is pressed, Brake tune is stopped")
            brake_example.stop()
            return False
        elif "c" in str(key):
            print("\nc key is pressed, Brake is set in Voltage mode")
            mc.communication.set_register("MOT_BRAKE_CONTROL_MODE", 0)
        elif "a" in str(key):
            print("\na key is pressed, there is not any brake current feedback source")
            mc.communication.set_register("MOT_BRAKE_CUR_FBK", 0)


def main():
    global mc
    global brake_example

    node_id_list = canopen_connection()

    if len(node_id_list) > 0:
        brake_tuning_configuration()
        brake_example = BrakeTune(mc, enable_disable_motor_period=2)

        with keyboard.Listener(on_press=on_press) as listener:
            thread = threading.Thread(target=brake_example.run)
            thread.start()
            thread.join()
            listener.join()

        print(f"\nReport Severity: {brake_example.report['result_severity']}")
        print(f"Report Message: {brake_example.report['result_message']}")
        print("Parameter settings:")
        print("-------------------")
        register_loggers()
        mc.communication.disconnect()
    else:
        print(f"There is not any connected slave")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    main()

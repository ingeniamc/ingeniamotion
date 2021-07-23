from ingeniamotion import MotionController
from ingenialink.canopen import CAN_BAUDRATE, CAN_DEVICE

# Create MotionController instance
mc = MotionController()

# Get list of all node id available
node_id_list = mc.communication.scan_servos_canopen(
    CAN_DEVICE.PCAN, CAN_BAUDRATE.Baudrate_1M, channel=0)

dict_path = "./eve-net-c_can_1.8.1.xdf"
eds_path = "./eve-net-c_1.8.1.eds"

if len(node_id_list) > 0:
    # Connect to servo with CANOpen
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
    mc.communication.disconnect_canopen()
else:
    print("No node id available")

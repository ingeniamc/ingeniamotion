from ingeniamotion import MotionController
from ingenialink.canopen import CAN_BAUDRATE, CAN_DEVICE

mc = MotionController()
node_id_list = mc.communication.scan_servos_canopen(
    CAN_DEVICE.PCAN, CAN_BAUDRATE.Baudrate_1M, channel=0)

mc.communication.connect_servo_canopen(
    CAN_DEVICE.PCAN, "./eve-net_canopen_1.7.2.xdf",
    "./eve-net-c_1.7.2.eds", node_id_list[0],
    CAN_BAUDRATE.Baudrate_1M, channel=0
)

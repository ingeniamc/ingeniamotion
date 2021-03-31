from ingeniamotion import MotionController

mc = MotionController()
mc.communication.connect_servo_eoe("192.168.2.22", "cap-net_0.5.0.xdf")
mc.communication.set_register("DRV_PROT_USER_OVER_VOLT", 60)
volt = mc.communication.get_register("DRV_PROT_VBUS_VALUE")
print("Current voltage is", volt)

import ingeniamotion

# Create MotionController instance
mc = ingeniamotion.MotionController()

# Connect drive
mc.communication.connect_servo_ethernet("192.168.2.22", "eve-net-c_eth_1.8.1.xdf")

# Load firmware
mc.communication.boot_mode_and_load_firmware_ethernet("eve-net-c_1.8.1.sfu")

import ingeniamotion

# Create MotionController instance
mc = ingeniamotion.MotionController()

# Print infame list to get ifname index
print(mc.communication.get_interface_name_list())

# Load firmware
mc.communication.load_firmware_ecat_interface_index(
    2,  # ifname index
    "./cap-xcr-e_0.7.1.lfu",  # FW file
    1,  # Slave index
    boot_in_app=False)  # True if Everest, False if Capitan, else contact manufacturer

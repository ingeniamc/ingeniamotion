import math
import time
from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode

mc = MotionController()
mc.communication.connect_servo_eoe("192.168.2.22", "./cap-net-c_eth_0.7.3.xdf")

# Disturbance register
target_register = "CL_POS_SET_POINT_VALUE"
# Frequency divider to set disturbance frequency
divider = 10000
# Calculate time between disturbance samples
sample_period = divider/mc.configuration.get_position_and_velocity_loop_rate()
# The disturbance signal will be a simple harmonic motion (SHM) with frequency 0.5Hz and 2000 counts of amplitude
signal_frequency = 0.1
signal_amplitude = 2
# Calculate number of samples to load a complete oscillation
n_samples = int(1 / (signal_frequency * sample_period))
# Generate a SHM with the formula x(t)=A*sin(t*w) where:
# A = signal_amplitude (Amplitude)
# t = sample_period*i (time)
# w = signal_frequency*2*math.pi (angular frequency)
data = [int(signal_amplitude * math.sin(sample_period*i * signal_frequency * 2*math.pi))
        for i in range(n_samples)]

# Call function create_disturbance to configure a disturbance
dist = mc.capture.create_disturbance(target_register, data, divider, start=True)

# Set profile position operation mode and enable motor to enable motor move
mc.motion.set_operation_mode(OperationMode.PROFILE_POSITION)
# Enable disturbance
mc.capture.enable_monitoring_disturbance()
# Enable motor
mc.motion.motor_enable()
# Wait 10 seconds
time.sleep(100)
# Disable motor
mc.motion.motor_disable()
# Disable disturbance
mc.capture.disable_monitoring_disturbance()

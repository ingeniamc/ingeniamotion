import logging
import numpy as np
import matplotlib.pyplot as plt
import math

from ingeniamotion import MotionController
from ingeniamotion.enums import OperationMode
from ingeniamotion.monitoring import MonitoringSoCType, MonitoringSoCConfig

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('matplotlib.font_manager').disabled = True

mc = MotionController()
mc.communication.connect_servo_eoe("192.168.2.22", "./registers_dictionary.xdf")

# Monitoring registers
registers = [{"axis": 1, "name": "CL_CUR_Q_REF_VALUE"},
             {"axis": 1, "name": "DRV_PROT_VBUS_VALUE"},
             ]

# Disturbance register
dist_target_register = "CL_CUR_Q_SET_POINT"

# Servo frequency divisor to set monitoring frequency
monitoring_prescaler = 60

total_time_s = 1  # Total sample time in seconds
trigger_delay_s = 0  # Trigger delay time in seconds

# trigger_mode = MonitoringSoCType.TRIGGER_EVENT_AUTO
# trigger_mode = MonitoringSoCType.TRIGGER_EVENT_FORCED
trigger_mode = MonitoringSoCType.TRIGGER_EVENT_EDGE

# trigger_config = MonitoringSoCConfig.TRIGGER_CONFIG_RISING_OR_FALLING
trigger_config = MonitoringSoCConfig.TRIGGER_CONFIG_RISING
# trigger_config = MonitoringSoCConfig.TRIGGER_CONFIG_FALLING

# Trigger signal register if trigger_mode is TRIGGER_CYCLIC_RISING_EDGE or TRIGGER_CYCLIC_FALLING_EDGE
# else, it does nothing
trigger_signal = {"axis": 1, "name": "DRV_PROT_VBUS_VALUE"}
# Trigger value if trigger_mode is TRIGGER_CYCLIC_RISING_EDGE or TRIGGER_CYCLIC_FALLING_EDGE
# else, it does nothing
trigger_value = 24


# Frequency divider to set disturbance frequency
dist_divider = 80
# Calculate time between disturbance samples
sample_period = dist_divider/mc.configuration.get_position_and_velocity_loop_rate()
# The disturbance signal will be a simple harmonic motion (SHM) with frequency 0.5Hz and 2000 counts of amplitude
signal_frequency = 10
signal_amplitude = 1
# Calculate number of samples to load a complete oscillation
n_samples = int(1 / (signal_frequency * sample_period))
# Generate a SHM with the formula x(t)=A*sin(t*w) where:
# A = signal_amplitude (Amplitude)
# t = sample_period*i (time)
# w = signal_frequency*2*math.pi (angular frequency)
data = [float(signal_amplitude * math.sin(sample_period*i * signal_frequency * 2*math.pi))
        for i in range(n_samples)]

mc.capture.disable_disturbance()
mc.capture.disable_monitoring()

mc.communication.set_register("DIST_ENABLE", 0, axis=0)

# Call function create_disturbance to configure a disturbance
dist = mc.capture.create_disturbance(dist_target_register, data, dist_divider, start=True)

# Set profile position operation mode and enable motor to enable motor move
mc.motion.set_operation_mode(OperationMode.CURRENT)
# Enable disturbance
mc.capture.enable_disturbance()
# Enable motor
mc.motion.motor_enable()

monitoring = mc.capture.create_monitoring(registers,
                                          monitoring_prescaler,
                                          total_time_s,
                                          trigger_delay=trigger_delay_s,
                                          trigger_mode=trigger_mode,
                                          trigger_signal=trigger_signal,
                                          trigger_value=trigger_value)

# monitoring_lifeguard = 60
# monitoring.mc.communication.set_register(
#     "MON_LIFEGUARD",
#     monitoring_lifeguard,
#     servo=monitoring.servo,
#     axis=0
# )
# monitoring_lifeguard = monitoring.mc.communication.get_register(
#     "MON_LIFEGUARD",
#     servo=monitoring.servo,
#     axis=0
# )

# Enable Monitoring
mc.capture.enable_monitoring()
print("Waiting for trigger")
# Blocking function to read monitoring values
data = monitoring.read_monitoring_data()
print("Triggered and data read!")

# Calculate abscissa values with total_time_s and trigger_delay_s
x_start = -total_time_s/2 + trigger_delay_s
x_end = total_time_s/2 + trigger_delay_s
x_values = np.linspace(x_start, x_end, len(data[0]))

# Plot result
fig, axs = plt.subplots(2)
for index in range(len(axs)):
    ax = axs[index]
    ax.plot(x_values, data[index])
    ax.set_title(registers[index]["name"])

plt.autoscale()
plt.show()

mc.communication.disconnect()

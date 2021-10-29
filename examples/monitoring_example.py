import logging
import numpy as np
import matplotlib.pyplot as plt

from ingeniamotion import MotionController
from ingeniamotion.enums import MonitoringSoCType, MonitoringSoCConfig

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('matplotlib.font_manager').disabled = True

mc = MotionController()
mc.communication.connect_servo_eoe("192.168.2.22", "./eve-net_1.7.0.xdf")

# Monitoring registers
registers = [{"axis": 1, "name": "CL_POS_FBK_VALUE"},
             {"axis": 1, "name": "CL_VEL_FBK_VALUE"}]

# Servo frequency divisor to set monitoring frequency
monitoring_prescaler = 10

total_time_s = 1  # Total sample time in seconds
trigger_delay_s = 0.0  # Trigger delay time in seconds

trigger_mode = MonitoringSoCType.TRIGGER_EVENT_AUTO
# trigger_mode = MonitoringSoCType.TRIGGER_EVENT_EDGE
trigger_config = None
# trigger_config = MonitoringSoCConfig.TRIGGER_CONFIG_RISING
# trigger_config = MonitoringSoCConfig.TRIGGER_CONFIG_FALLING

# Trigger signal register if trigger_mode is TRIGGER_CYCLIC_RISING_EDGE or TRIGGER_CYCLIC_FALLING_EDGE
# else, it does nothing
trigger_signal = {"axis": 1, "name": "CL_POS_FBK_VALUE"}
# Trigger value if trigger_mode is TRIGGER_CYCLIC_RISING_EDGE or TRIGGER_CYCLIC_FALLING_EDGE
# else, it does nothing
trigger_value = 0

monitoring = mc.capture.create_monitoring(registers,
                                          monitoring_prescaler,
                                          total_time_s,
                                          trigger_delay=trigger_delay_s,
                                          trigger_mode=trigger_mode,
                                          trigger_config=trigger_config,
                                          trigger_signal=trigger_signal,
                                          trigger_value=trigger_value)
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

import logging
import numpy as np
import matplotlib.pyplot as plt
import time
from ingeniamotion import MotionController
from ingeniamotion.monitoring import MonitoringSoCType, MonitoringSoCConfig

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('matplotlib.font_manager').disabled = True

mc = MotionController()
mc.communication.connect_servo_eoe("192.168.2.22", "./registers_dictionary.xdf")

# Monitoring registers
registers = [{"axis": 1, "name": "FBK_CUR_MODULE_VALUE"},
             {"axis": 1, "name": "FBK_GEN_VALUE"} ]

# Servo frequency divisor to set monitoring frequency
monitoring_prescaler = 60

total_time_s = 1  # Total sample time in seconds
trigger_delay_s = 0.5  # Trigger delay time in seconds

# trigger_mode = MonitoringSoCType.TRIGGER_EVENT_AUTO
# trigger_mode = MonitoringSoCType.TRIGGER_EVENT_FORCED
trigger_mode = MonitoringSoCType.TRIGGER_EVENT_EDGE

# trigger_config = MonitoringSoCConfig.TRIGGER_CONFIG_RISING_OR_FALLING
trigger_config = MonitoringSoCConfig.TRIGGER_CONFIG_RISING
# trigger_config = MonitoringSoCConfig.TRIGGER_CONFIG_FALLING

# Trigger signal register if trigger_mode is TRIGGER_CYCLIC_RISING_EDGE or TRIGGER_CYCLIC_FALLING_EDGE
# else, it does nothing
trigger_signal = {"axis": 1, "name": "FBK_GEN_VALUE"}
# Trigger value if trigger_mode is TRIGGER_CYCLIC_RISING_EDGE or TRIGGER_CYCLIC_FALLING_EDGE
# else, it does nothing
trigger_value = 1.5

mc.capture.disable_disturbance()
mc.capture.disable_monitoring()

monitoring = mc.capture.create_monitoring(registers,
                                          monitoring_prescaler,
                                          total_time_s,
                                          trigger_delay=trigger_delay_s,
                                          trigger_mode=trigger_mode,
                                          trigger_config=trigger_config,
                                          trigger_signal=trigger_signal,
                                          trigger_value=trigger_value)

# Set internal generator as position feedback
monitoring.mc.communication.set_register(
    "CL_POS_FBK_SENSOR",
    3,
    servo=monitoring.servo,
    axis=1
)

monitoring.mc.communication.set_register(
    "FBK_GEN_OFFSET",
    1.0,
    servo=monitoring.servo,
    axis=1
)
# Set saw tooth as generator output
monitoring.mc.communication.set_register(
    "FBK_GEN_MODE",
    1,
    servo=monitoring.servo,
    axis=1
)

# time.sleep(1.1)
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

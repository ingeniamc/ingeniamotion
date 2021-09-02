import logging
import numpy as np
import matplotlib.pyplot as plt

from ingeniamotion import MotionController
from ingeniamotion.monitoring import MonitoringEventType, MonitoringEventConfig

logging.basicConfig(level=logging.DEBUG)
logging.getLogger('matplotlib.font_manager').disabled = True

mc = MotionController()
mc.communication.connect_servo_eoe("192.168.2.22", "./cap-net-c_eth_0.7.3.xdf")

# Monitoring registers
registers = [{"axis": 1, "name": "DRV_PROT_VBUS_VALUE"},
             {"axis": 1, "name": "CL_VEL_FBK_VALUE"}]

# Servo frequency divisor to set monitoring frequency
monitoring_prescaler = 1

total_time_s = 0.1  # Total sample time in seconds
# total_time_s = 0.5  # Total sample time in seconds
trigger_delay_s = -0.1  # Trigger delay time in seconds

# trigger_type = MonitoringEventType.TRIGGER_EVENT_AUTO
# trigger_type = MonitoringEventType.TRIGGER_EVENT_FORCED
trigger_type = MonitoringEventType.TRIGGER_EVENT_EDGE

# trigger_config = MonitoringEventConfig.TRIGGER_EDGE_RISING_OR_FALLING
trigger_config = MonitoringEventConfig.TRIGGER_EDGE_RISING
# trigger_config = MonitoringEventConfig.TRIGGER_EDGE_FALLING

# Trigger signal register if trigger_mode is TRIGGER_CYCLIC_RISING_EDGE or TRIGGER_CYCLIC_FALLING_EDGE
# else, it does nothing
trigger_signal = {"axis": 1, "name": "DRV_PROT_VBUS_VALUE"}
# Trigger value if trigger_mode is TRIGGER_CYCLIC_RISING_EDGE or TRIGGER_CYCLIC_FALLING_EDGE
# else, it does nothing
trigger_value = 24

monitoring = mc.capture.create_monitoring(registers,
                                          monitoring_prescaler,
                                          total_time_s,
                                          trigger_delay=trigger_delay_s,
                                          trigger_type=trigger_type,
                                          trigger_config=trigger_config,
                                          trigger_signal=trigger_signal,
                                          trigger_value=trigger_value)
# Enable Monitoring
mc.capture.enable_monitoring_disturbance()
while 1:
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
    monitoring.mc.communication.set_register(
            "MON_CFG_TRIGGER_REPETITIONS",
            1,
            servo=monitoring.servo,
            axis=0
        )
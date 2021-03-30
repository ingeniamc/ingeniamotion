import matplotlib.pyplot as plt
import matplotlib.animation as animation

from ingeniamotion import MotionController

mc = MotionController()
mc.communication.connect_servo_eoe("192.168.2.22", "cap-net_0.5.0.xdf")

# List of registers
registers = [
    {
        "name": "CL_POS_FBK_VALUE",  # Register name
        "axis": 1  # Register axis
    },
]
# Create Poller with our registers
poller = mc.capture.create_poller(registers)

# PLOT DATA
fig, ax = plt.subplots()
x_values = []
y_values = []
line, = ax.plot(x_values, y_values)

def animate(i):
    timestamp, registers_values, _ = poller.data  # Read Poller data
    global x_values, y_values
    x_values += timestamp
    y_values += registers_values[0]
    line.set_data(x_values, y_values)
    ax.relim()
    ax.autoscale_view()
    return line,

ani = animation.FuncAnimation(
    fig, animate, interval=100)
plt.autoscale()
plt.show()

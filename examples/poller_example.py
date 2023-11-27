import argparse

import matplotlib.pyplot as plt
import matplotlib.animation as animation

from ingeniamotion import MotionController


def main(args):
    mc = MotionController()
    mc.communication.connect_servo_eoe(args.ip, args.dictionary_path)

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
    global x_values, y_values
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
    if args.close:
        plt.show(block=False)
        plt.pause(5)
        plt.close()
    else:
        plt.show()
    poller.stop()
    mc.communication.disconnect()


def setup_command():
    parser = argparse.ArgumentParser(description='Disturbance example')
    parser.add_argument('--dictionary_path', help='Path to drive dictionary', required=True)
    parser.add_argument('--ip', help='Drive IP address', required=True)
    parser.add_argument('--close', help='Close plot after 5 seconds', action='store_true')
    return parser.parse_args()


if __name__ == '__main__':
    args = setup_command()
    main(args)

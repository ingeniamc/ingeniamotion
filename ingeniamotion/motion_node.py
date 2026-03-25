from collections.abc import Iterator

from ingenialink import Network, Servo

from ingeniamotion.axis import Axis
from ingeniamotion.errors import NodeErrors


class MotionNode:
    """Motion Node."""

    def __init__(self, servo: Servo, network: Network) -> None:
        """Initialize motion node.

        Args:
            servo: servo associated with the motion node.
            network: motion network associated with the motion node.
        """
        self.__servo = servo
        self.__net = network

        self.__axes = {
            axis_number: Axis(self, axis_number)
            for axis_number in self.__servo.dictionary.subnodes
            if axis_number != 0  # Axis 0 is the motion node itself, not an axis
        }

        self.__errors = NodeErrors(self)

    @property
    def servo(self) -> Servo:
        """Get the servo associated with the motion node."""
        return self.__servo

    @property
    def network(self) -> Network:
        """Network associated with the motion node."""
        return self.__net

    @property
    def axes(self) -> Iterator["Axis"]:
        """Get the axes of the motion node.

        Yields:
            Axis: Each axis of the motion node.
        """
        yield from self.__axes.values()

    def get_axis(self, axis_number: int) -> "Axis":
        """Get a specific axis by its number.

        Args:
            axis_number: The number of the axis to retrieve.

        Returns:
            Axis: The axis with the specified number.

        Raises:
            KeyError: If the axis number does not exist.
        """
        return self.__axes[axis_number]

    @property
    def errors(self) -> NodeErrors:
        """Get the errors of the motion node."""
        return self.__errors

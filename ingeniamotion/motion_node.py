from typing import Optional

from ingenialink import Network, Servo


class MotionNode:
    """Motion Node."""

    def __init__(self, servo: Servo, network: Optional[Network]) -> None:
        """Initialize motion node.

        Args:
            servo: servo associated with the motion node.
            network: motion network associated with the motion node.
        """
        self.__servo = servo
        self.__net = network

    @property
    def servo(self) -> Servo:
        """Get the servo associated with the motion node."""
        return self.__servo

    @property
    def network(self) -> Optional[Network]:
        """Network associated with the motion node."""
        return self.__net

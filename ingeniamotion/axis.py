from typing import TYPE_CHECKING

from ingeniamotion._utils import weak_lru
from ingeniamotion.errors import MOCO_ERROR_QUEUE, AxisErrors, ServoErrorQueue

if TYPE_CHECKING:
    from ingeniamotion.motion_node import MotionNode


class Axis:
    """Axis."""

    def __init__(self, motion_node: "MotionNode", axis_number: int) -> None:
        """Initialize axis.

        Args:
            motion_node: motion node associated with the axis.
            axis_number: axis number.
        """
        self.__motion_node = motion_node
        self.__axis_number = axis_number

        self.__errors = AxisErrors(self)

    @property
    def motion_node(self) -> "MotionNode":
        """The motion node associated with the axis."""
        return self.__motion_node

    @property
    def axis_number(self) -> int:
        """The axis number."""
        return self.__axis_number

    @property
    def errors(self) -> AxisErrors:
        """The errors of the axis."""
        return self.__errors

    @property
    @weak_lru()
    def error_queue(self) -> ServoErrorQueue:
        """The error queue of the axis."""
        return ServoErrorQueue(MOCO_ERROR_QUEUE, self.motion_node.servo, axis=self.axis_number)

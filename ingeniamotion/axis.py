from functools import cached_property
from typing import TYPE_CHECKING, Union

from ingenialink.register import Register
from ingenialink.utils._utils import REG_VALUE

from ingeniamotion.errors import MOCO_ERROR_QUEUE, AxisErrors, ServoErrorQueue
from ingeniamotion.feedbacks import AxisFeedbacks

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

    @property
    def motion_node(self) -> "MotionNode":
        """The motion node associated with the axis."""
        return self.__motion_node

    @property
    def axis_number(self) -> int:
        """The axis number."""
        return self.__axis_number

    def read(self, reg: Union[str, Register]) -> REG_VALUE:
        """Read a register of this axis.

        Args:
            reg: register UID or register to read.

        Returns:
            The register value.
        """
        return self.__motion_node.servo.read(reg, subnode=self.__axis_number)

    def write(self, reg: Union[str, Register], value: REG_VALUE) -> None:
        """Write a register of this axis.

        Args:
            reg: register UID or register to write.
            value: value to write.
        """
        self.__motion_node.servo.write(reg, value, subnode=self.__axis_number)

    def get_register(self, reg_uid: str) -> Register:
        """Get a register of this axis from the drive dictionary.

        Args:
            reg_uid: register UID to look up.

        Returns:
            The register.
        """
        return self.__motion_node.servo.dictionary.get_register(reg_uid, axis=self.__axis_number)

    @cached_property
    def errors(self) -> AxisErrors:
        """The errors of the axis.

        Returns:
            The error container, built on first access.
        """
        return AxisErrors(self)

    @cached_property
    def feedbacks(self) -> AxisFeedbacks:
        """The feedbacks of the axis.

        Returns:
            The feedback slots container, built on first access.
        """
        return AxisFeedbacks(self)

    @cached_property
    def error_queue(self) -> ServoErrorQueue:
        """The error queue of the axis.

        Returns:
            The error queue, built on first access.
        """
        return ServoErrorQueue(MOCO_ERROR_QUEUE, self.motion_node.servo, axis=self.axis_number)

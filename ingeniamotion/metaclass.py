import inspect
from functools import wraps
from typing import Callable, TypeVar

from ingeniamotion.exceptions import IMStatusWordError

DEFAULT_SERVO = "default"
DEFAULT_AXIS = 1

T = TypeVar("T")


class MCMetaClass(type):
    """MotionController submodules metaclass.

    This class has decorators that can be useful for some
    functions, as motor disabled checker.
    """

    SERVO_ARG_NAME = "servo"
    AXIS_ARG_NAME = "axis"

    @classmethod
    def check_motor_disabled(cls, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to check if motor is disabled.

        If motor is enabled raises an exception.

        Returns:
            Callable: The wrapped function that checks if the motor is disabled
            before executing the original function.
        """

        @wraps(func)
        def wrapper(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            mc = self.mc
            func_args = inspect.getfullargspec(func).args
            servo_index = func_args.index(cls.SERVO_ARG_NAME)
            axis_index = func_args.index(cls.AXIS_ARG_NAME)
            if len(args) < servo_index:
                servo = kwargs.get(cls.SERVO_ARG_NAME, DEFAULT_SERVO)
            else:
                servo = args[servo_index - 1]
            if len(args) < axis_index:
                axis = kwargs.get(cls.AXIS_ARG_NAME, DEFAULT_AXIS)
            else:
                axis = args[axis_index - 1]
            if mc.configuration.is_motor_enabled(servo=servo, axis=axis):
                raise IMStatusWordError("Motor is enabled")
            return func(self, *args, **kwargs)

        return wrapper

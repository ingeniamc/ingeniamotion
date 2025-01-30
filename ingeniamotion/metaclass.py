import inspect
from functools import wraps
from types import FunctionType
from typing import Any, Callable, TypeVar

from ingeniamotion.exceptions import IMStatusWordError

DEFAULT_SERVO = "default"
DEFAULT_AXIS = 1

T = TypeVar("T")


class MCMetaClass(type):
    """MotionController submodules metaclass to add servo checker for all
    the functions that has an argument named servo.

    This class also have other decorators that can be useful for some
    functions, as motor disabled checker.
    """

    SERVO_ARG_NAME = "servo"
    AXIS_ARG_NAME = "axis"

    def __new__(
        cls: type["MCMetaClass"], name: str, bases: tuple[type, ...], local: dict[str, Any]
    ) -> "MCMetaClass":
        """If a function has argument named servo,
        decorates it with check_servo decorator.
        """
        for attr in local:
            value = local[attr]
            if (
                callable(value)
                and isinstance(value, FunctionType)
                and cls.SERVO_ARG_NAME in inspect.getfullargspec(value).args
            ):
                local[attr] = cls.check_servo(value)
        return type.__new__(cls, name, bases, local)

    @classmethod
    def check_servo(cls, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to check if the servo is connected.
        If servo is not connected raises an exception.
        """

        @wraps(func)
        def wrapper(self, *args, **kwargs):  # type: ignore
            mc = self.mc
            func_args = inspect.getfullargspec(func).args
            servo_index = func_args.index(cls.SERVO_ARG_NAME)
            if len(args) < servo_index:
                servo = kwargs.get(cls.SERVO_ARG_NAME, DEFAULT_SERVO)
            else:
                servo = args[servo_index - 1]
            if servo not in mc.servos:
                raise KeyError(f"Servo '{servo}' is not connected")
            return func(self, *args, **kwargs)

        return wrapper

    @classmethod
    def check_motor_disabled(cls, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to check if motor is disabled.
        If motor is enabled raises an exception.
        """

        @wraps(func)
        def wrapper(self, *args, **kwargs):  # type: ignore
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

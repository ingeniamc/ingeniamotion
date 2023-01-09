import inspect
from functools import wraps

from ingeniamotion.exceptions import IMStatusWordError

DEFAULT_SERVO = "default"
DEFAULT_AXIS = 1


class MCMetaClass(type):
    """MotionController submodules metaclass to add servo checker for all
    the functions that has an argument named servo.

    This class also have other decorators that can be useful for some
    functions, as motor disabled checker.
    """

    SERVO_ARG_NAME = "servo"

    def __new__(mcs, name, bases, local):
        """If a function has argument named servo,
        decorates it with check_servo decorator.
        """
        for attr in local:
            value = local[attr]
            if callable(value) and mcs.SERVO_ARG_NAME in inspect.getfullargspec(value).args:
                local[attr] = mcs.check_servo(value)
        return type.__new__(mcs, name, bases, local)

    @classmethod
    def check_servo(mcs, func):
        """Decorator to check if the servo is connected.
        If servo is not connected raises an exception.
        """

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            mc = self.mc
            func_args = inspect.getfullargspec(func).args
            servo_index = func_args.index(mcs.SERVO_ARG_NAME)
            if len(args) < servo_index:
                servo = kwargs.get(mcs.SERVO_ARG_NAME, DEFAULT_SERVO)
            else:
                servo = args[servo_index - 1]
            if servo not in mc.servos:
                raise KeyError("Servo '{}' is not connected".format(servo))
            return func(self, *args, **kwargs)

        return wrapper

    @classmethod
    def check_motor_disabled(mcs, func):
        """Decorator to check if motor is disabled.
        If motor is enabled raises an exception.
        """

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            mc = self.mc
            servo = kwargs.get("servo", DEFAULT_SERVO)
            axis = kwargs.get("axis", DEFAULT_AXIS)
            if mc.configuration.is_motor_enabled(servo=servo, axis=axis):
                raise IMStatusWordError("Motor is enabled")
            return func(self, *args, **kwargs)

        return wrapper

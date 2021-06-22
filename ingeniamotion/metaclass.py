import types
import inspect
from functools import wraps

DEFAULT_SERVO = "default"
DEFAULT_AXIS = 1


class MCMetaClass(type):

    def __new__(mcs, name, bases, local):
        for attr in local:
            value = local[attr]
            if isinstance(value, types.FunctionType) and \
                    "servo" in inspect.getfullargspec(value).args:
                local[attr] = mcs.check_servo(value)
        return type.__new__(mcs, name, bases, local)

    @classmethod
    def check_servo(mcs, func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            mc = self.mc
            servo = kwargs.get("servo", DEFAULT_SERVO)
            if servo not in mc.servos:
                raise KeyError("Servo '{}' is not connected".format(servo))
            return func(self, *args, **kwargs)
        return wrapper

    @classmethod
    def check_motor_enable(mcs, func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            mc = self.mc
            servo = kwargs.get("servo", DEFAULT_SERVO)
            axis = kwargs.get("axis", DEFAULT_AXIS)
            if mc.configuration.is_motor_enabled(servo=servo,
                                                 axis=axis):
                raise Exception("Motor is enabled")
            return func(self, *args, **kwargs)
        return wrapper

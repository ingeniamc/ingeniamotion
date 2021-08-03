from functools import wraps
from time import time


class StopException(Exception):
    """ Stop exception. """


class Stoppable:

    is_stopped = False

    @staticmethod
    def stoppable(fun):
        @wraps(fun)
        def wrapper(self, *args, **kwargs):
            self.check_stop()
            return fun(self, *args, **kwargs)
        return wrapper

    def reset_stop(self):
        self.is_stopped = False

    def stop(self):
        self.is_stopped = True

    def check_stop(self):
        if self.is_stopped:
            raise StopException

    def stoppable_sleep(self, timeout):
        init_time = time()
        while init_time + timeout < time():
            self.check_stop()

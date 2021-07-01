from functools import wraps
from time import time


class StopException(Exception):
    """ Stop exception. """


class Stoppable:

    stop = False

    @staticmethod
    def stoppable(fun):
        @wraps(fun)
        def wrapper(self, *args, **kwargs):
            self.check_stop()
            return fun(self, *args, **kwargs)
        return wrapper

    def reset_stop(self):
        self.stop = False

    def active_stop(self):
        self.stop = True

    def check_stop(self):
        if self.stop:
            raise StopException

    def stoppable_sleep(self, timeout):
        init_time = time()
        while init_time + timeout < time():
            self.check_stop()

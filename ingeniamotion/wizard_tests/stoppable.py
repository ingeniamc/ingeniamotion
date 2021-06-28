from functools import wraps


class StopException(Exception):
    """ Stop exception. """


class Stoppable:

    stop = False

    @staticmethod
    def stoppable(fun):
        @wraps(fun)
        def wrapper(self, *args, **kwargs):
            if self.stop:
                raise StopException
            return fun(self, *args, **kwargs)
        return wrapper

    def reset_stop(self):
        self.stop = False

    def active_stop(self):
        self.stop = True

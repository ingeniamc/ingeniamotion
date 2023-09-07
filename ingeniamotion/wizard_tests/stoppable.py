from time import time
from functools import wraps
from typing import TypeVar, Callable, Any

F = TypeVar('F', bound=Callable[..., Any])

class StopException(Exception):
    """Stop exception."""


class Stoppable:

    is_stopped = False

    @staticmethod
    def stoppable(fun: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fun)
        def wrapper(self, *args, **kwargs): #type: ignore
            self.check_stop()
            return fun(self, *args, **kwargs)

        return wrapper

    def reset_stop(self) -> None:
        self.is_stopped = False

    def stop(self) -> None:
        self.is_stopped = True

    def check_stop(self) -> None:
        if self.is_stopped:
            raise StopException

    def stoppable_sleep(self, timeout: float) -> None:
        init_time = time()
        while init_time + timeout > time():
            self.check_stop()

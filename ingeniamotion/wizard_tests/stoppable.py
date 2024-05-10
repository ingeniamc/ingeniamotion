import typing
from functools import wraps
from queue import Empty, Queue
from typing import Callable


class StopException(Exception):
    """Stop exception."""


T = typing.TypeVar("T")


class Stoppable:
    stop_queue = Queue(1)

    @staticmethod
    def stoppable(fun: Callable[..., T]) -> Callable[..., T]:
        @wraps(fun)
        def wrapper(self, *args, **kwargs):  # type: ignore
            self.check_stop()
            return fun(self, *args, **kwargs)

        return wrapper

    def reset_stop(self) -> None:
        if self.stop_queue.full():
            self.stop_queue.get(block=False)

    def stop(self) -> None:
        if not self.stop_queue.full():
            self.stop_queue.put(StopException, block=False)

    def check_stop(self) -> None:
        if self.stop_queue.full():
            raise self.stop_queue.get(block=False)

    def stoppable_sleep(self, timeout: float) -> None:
        try:
            stop_exception = self.stop_queue.get(block=True, timeout=timeout)
        except Empty:
            pass
        else:
            raise stop_exception

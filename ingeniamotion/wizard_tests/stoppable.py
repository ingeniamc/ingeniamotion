import typing
from functools import wraps
from queue import Empty, Full, Queue
from typing import Callable


class StopException(Exception):
    """Stop exception."""


T = typing.TypeVar("T")


class Stoppable:
    stop_queue: Queue[StopException] = Queue(1)

    @staticmethod
    def stoppable(fun: Callable[..., T]) -> Callable[..., T]:
        @wraps(fun)
        def wrapper(self, *args, **kwargs):  # type: ignore
            self.check_stop()
            return fun(self, *args, **kwargs)

        return wrapper

    def reset_stop(self) -> None:
        try:
            self.stop_queue.get(block=False)
        except Empty:
            pass

    def stop(self) -> None:
        try:
            self.stop_queue.put(StopException(), block=False)
        except Full:
            pass

    def check_stop(self) -> None:
        try:
            stop_exception = self.stop_queue.get(block=False)
        except Empty:
            pass
        else:
            raise stop_exception

    def stoppable_sleep(self, timeout: float) -> None:
        try:
            stop_exception = self.stop_queue.get(timeout=timeout)
        except Empty:
            pass
        else:
            raise stop_exception

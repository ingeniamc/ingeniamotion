import contextlib
import typing
from functools import wraps
from queue import Empty, Full, Queue
from typing import Callable


class StopExceptionError(Exception):
    """Stop exception."""


T = typing.TypeVar("T")


class Stoppable:
    """Stoppable class.

    It allows a test to be stoppable.

    """

    stop_queue: Queue[StopExceptionError] = Queue(1)

    @staticmethod
    def stoppable(fun: Callable[..., T]) -> Callable[..., T]:
        """Stoppable decorator.

        Args:
            fun: The function to decorate.

        Returns:
            The decorated function.

        """

        @wraps(fun)
        def wrapper(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            self.check_stop()
            return fun(self, *args, **kwargs)

        return wrapper

    def reset_stop(self) -> None:
        """Reset the stop."""
        with contextlib.suppress(Empty):
            self.stop_queue.get(block=False)

    def stop(self) -> None:
        """Stop the test."""
        with contextlib.suppress(Full):
            self.stop_queue.put(StopExceptionError(), block=False)

    def check_stop(self) -> None:
        """Check if the test was stopped."""
        try:
            stop_exception = self.stop_queue.get(block=False)
        except Empty:
            pass
        else:
            raise stop_exception

    def stoppable_sleep(self, timeout: float) -> None:
        """A stoppable sleep.

        Args:
            timeout: Time to sleep.

        """
        try:
            stop_exception = self.stop_queue.get(timeout=timeout)
        except Empty:
            pass
        else:
            raise stop_exception

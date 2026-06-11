import contextlib
import time
import traceback
import typing
from dataclasses import dataclass
from functools import wraps
from queue import Empty, Full, Queue
from typing import Callable, ClassVar, Optional


class StopExceptionError(Exception):
    """Stop exception."""


T = typing.TypeVar("T")


@dataclass(frozen=True)
class StopOpportunityTraceEvent:
    """Captured metadata for a stoppable call.

    Each event represents a period of time during which the test could have
    been stopped. For instantaneous checks, timestamp and finish_timestamp
    will be nearly identical. For blocking operations (like sleeps), they
    define the interval of the operation.
    """

    timestamp: float
    traceback: tuple[traceback.FrameSummary, ...]
    finish_timestamp: float


StopOpportunityRecorder = Callable[..., None]


@dataclass(frozen=True)
class StopOpportunitySubscription:
    """Subscription to stop-opportunity notifications."""

    callback: StopOpportunityRecorder
    with_event: bool = False


class Stoppable:
    """Stoppable class.

    It allows a test to be stoppable.

    """

    stop_queue: Queue[StopExceptionError] = Queue(1)
    _stop_opportunity_subscriptions: ClassVar[list[StopOpportunitySubscription]] = []

    @classmethod
    def subscribe_to_stop_opportunities(
        cls,
        callback: StopOpportunityRecorder,
        with_event: bool = False,
    ) -> StopOpportunitySubscription:
        """Subscribe to stop-opportunity notifications.

        Args:
            callback: Callback invoked for each stop opportunity.
            with_event: When true, the callback receives a `StopOpportunityTraceEvent`.

        Returns:
            The subscription token that can later be unsubscribed.
        """
        subscription = StopOpportunitySubscription(callback=callback, with_event=with_event)
        cls._stop_opportunity_subscriptions.append(subscription)
        return subscription

    @classmethod
    def unsubscribe_from_stop_opportunities(cls, subscription: StopOpportunitySubscription) -> None:
        """Unsubscribe from stop-opportunity notifications."""
        with contextlib.suppress(Exception):
            cls._stop_opportunity_subscriptions.remove(subscription)

    @classmethod
    def _record_stop_opportunity(
        cls, start: Optional[float] = None, finish: Optional[float] = None
    ) -> None:
        subscriptions = cls._stop_opportunity_subscriptions
        if not subscriptions:
            return

        now = time.time()
        start = start if start is not None else now
        finish = finish if finish is not None else now

        event: Optional[StopOpportunityTraceEvent] = None
        for subscription in tuple(subscriptions):
            if subscription.with_event:
                if event is None:
                    event = StopOpportunityTraceEvent(
                        timestamp=start,
                        traceback=tuple(traceback.extract_stack()[:-2]),
                        finish_timestamp=finish,
                    )
                subscription.callback(event)
            else:
                subscription.callback()

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
        self._record_stop_opportunity()
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
        start_time = time.time()
        try:
            stop_exception = self.stop_queue.get(timeout=timeout)
        except Empty:
            stop_exception = None

        self._record_stop_opportunity(start_time, time.time())
        if stop_exception:
            raise stop_exception

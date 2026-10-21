import contextlib
import time
import traceback
import typing
from dataclasses import dataclass
from functools import wraps
from queue import Empty, Full, Queue
from typing import Callable, Final, Optional


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
    owner: Optional["Stoppable"] = None


StoppableInstanceCreations = Callable[["Stoppable"], None]
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

    stop_queue: Final[Queue[StopExceptionError]] = Queue(1)

    _stoppable_instance_creation_subscriptions: Final[list[StoppableInstanceCreations]] = []
    _stop_opportunity_subscriptions: Final[list[StopOpportunitySubscription]] = []

    def __init__(self) -> None:
        """Notify subscribers that a stoppable instance has been created."""
        for sub in self._stoppable_instance_creation_subscriptions:
            sub(self)

    @classmethod
    def subscribe_to_instance_creations(cls, callback: StoppableInstanceCreations) -> None:
        """Subscribe to stoppable instance creations.

        Args:
            callback: Callback invoked with each newly created stoppable instance.
        """
        cls._stoppable_instance_creation_subscriptions.append(callback)

    @classmethod
    def unsubscribe_to_instance_creations(cls, callback: StoppableInstanceCreations) -> None:
        """Unsubscribe from stoppable instance creations.

        Args:
            callback: Previously registered instance-creation callback.
        """
        with contextlib.suppress(ValueError):
            cls._stoppable_instance_creation_subscriptions.remove(callback)

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
        with contextlib.suppress(ValueError):
            cls._stop_opportunity_subscriptions.remove(subscription)

    def _record_stop_opportunity(
        self, start: Optional[float] = None, finish: Optional[float] = None
    ) -> None:
        subscriptions = self._stop_opportunity_subscriptions
        if not subscriptions:
            return

        now = time.time()
        start = start if start is not None else now
        finish = finish if finish is not None else now

        event: Optional[StopOpportunityTraceEvent] = None
        for subscription in tuple(subscriptions):
            if subscription.with_event:
                if event is None:
                    # Extract stack up to (but not including) this method, so the
                    # last frame is the stoppable method (check_stop, stoppable_sleep, etc.)
                    event = StopOpportunityTraceEvent(
                        timestamp=start,
                        traceback=tuple(traceback.extract_stack()[:-1]),
                        finish_timestamp=finish,
                        owner=self,
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
            result = fun(self, *args, **kwargs)
            self.check_stop()
            return result

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

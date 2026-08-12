import contextlib
import functools
import weakref
from collections.abc import Generator, Sequence
from typing import Any, Callable, Optional, TypeVar, cast

from exceptiongroup import ExceptionGroup


class _ExceptionGroupWrapper:
    """Wrapper for grouping exceptions in an exception group context manager."""

    def __init__(self) -> None:
        self.exceptions: list[BaseException] = []

    @contextlib.contextmanager
    def catch(
        self,
        *exception_types: type[BaseException],
    ) -> Generator[None, None, None]:
        """Context manager that catches exceptions of the given types.

        It saves the caught exceptions in the `exceptions` attribute of the wrapper,
        which can be used to raise an exception group after the context manager exits.
        """
        try:
            yield
        except exception_types as e:
            self.exceptions.append(e)


class ExceptionGroupContextError(ExceptionGroup):
    """Base class for exceptions that can be used as context for grouping exceptions."""

    @classmethod
    @contextlib.contextmanager
    def group(cls, message: str = "") -> Generator["_ExceptionGroupWrapper", None, None]:
        """Context manager that allows grouping exceptions into an exception group.

        Yields:
            _ExceptionGroupWrapper: A wrapper that can be used to catch exceptions and group them.

        Example:
            with ExceptionGroupContextError.group("Multiple errors occurred") as grp:
                with grp.catch(ValueError):
                    raise ValueError("Invalid value")
                with grp.catch(TypeError):
                    raise TypeError("Invalid type")
        """
        grp = _ExceptionGroupWrapper()

        try:
            yield grp
        finally:
            if grp.exceptions:
                raise cls(message, cast("Sequence[Exception]", grp.exceptions))


_T = TypeVar("_T")


def weak_lru(
    maxsize: Optional[int] = 128, typed: bool = False
) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """Decorator that allows safe use of lru_cache in class methods.

    Args:
        maxsize: maximum size. Defaults to 128.
        typed: typed. Defaults to False.

    Returns:
        wrapped method.
    """

    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        ref = weakref.ref

        @functools.lru_cache(maxsize, typed)
        def _func(_self: Any, /, *args: Any, **kwargs: Any) -> _T:
            return func(_self(), *args, **kwargs)

        @functools.wraps(func)
        def wrapper(self: Any, /, *args: Any, **kwargs: Any) -> _T:
            return _func(ref(self), *args, **kwargs)

        wrapper.cache_clear = _func.cache_clear  # type: ignore[attr-defined]
        return cast("Callable[..., _T]", wrapper)

    return decorator


def weak_lru_prop(func: Callable[[Any], _T]) -> property:
    """Create a property cached on its instance.

    Args:
        func: Property getter to cache.

    Returns:
        A property whose getter is evaluated only once per instance.
    """
    return cast("property", functools.cached_property(func))

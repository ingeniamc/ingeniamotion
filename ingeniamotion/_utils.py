import functools
import weakref
from typing import Any, Callable, Optional, TypeVar, cast

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

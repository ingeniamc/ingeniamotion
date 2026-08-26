import gc
import weakref

import pytest

from ingeniamotion._utils import weak_lru
from ingeniamotion.exceptions import IMErrorQueueNotExistsError


class ExpensiveCalculator:
    def __init__(self, factor):
        self.factor = factor
        self.calls = 0

    @weak_lru(maxsize=32)
    def compute(self, x):
        self.calls += 1
        return x * self.factor


@pytest.mark.virtual
def test_weak_lru_cache():
    calc = ExpensiveCalculator(10)

    result1 = calc.compute(5)
    result2 = calc.compute(5)

    # The compute method is called only once
    assert calc.calls == 1

    assert result1 == 50
    assert result2 == 50


def test_weak_lru_cache_does_not_retain_instance():
    """A weakly cached method should not keep its instance alive after use."""
    calculator = ExpensiveCalculator(10)
    calculator_ref = weakref.ref(calculator)

    assert calculator.compute(5) == 50

    del calculator
    gc.collect()

    assert calculator_ref() is None


def test_exception_group_context_error():
    should_be_executed = "This should be executed"
    should_not_be_executed = "This should not be executed"

    executed_tokens = []
    with pytest.raises(IMErrorQueueNotExistsError) as exc_info:
        with IMErrorQueueNotExistsError.group("Message of the group") as eg:
            with eg.catch(KeyError, ValueError):
                raise ValueError("Test KeyError")

            with eg.catch(KeyError, ValueError):
                executed_tokens.append(should_be_executed)

            with eg.catch(KeyError):
                raise KeyError("This should be caught by the KeyError catch block")

        executed_tokens.append(should_not_be_executed)

    assert executed_tokens == [should_be_executed]  # Not executed tokens should not be executed
    assert isinstance(exc_info.value, IMErrorQueueNotExistsError)
    assert exc_info.value.args[0] == "Message of the group"

    assert len(exc_info.value.exceptions) == 2

    assert isinstance(exc_info.value.exceptions[0], ValueError)
    assert exc_info.value.exceptions[0].args[0] == "Test KeyError"

    assert isinstance(exc_info.value.exceptions[1], KeyError)
    assert (
        exc_info.value.exceptions[1].args[0] == "This should be caught by the KeyError catch block"
    )


def test_exception_group_lets_non_catched_through():
    """Test that exceptions that are not caught by the catch context manager are propagated."""
    with pytest.raises(NotImplementedError):  # noqa: SIM117
        with IMErrorQueueNotExistsError.group("Message of the group") as eg:
            with eg.catch(KeyError, ValueError):
                raise NotImplementedError("Test KeyError")

import pytest

from ingeniamotion._utils import weak_lru


class ExpensiveCalculator:
    def __init__(self, factor):
        self.factor = factor
        self.calls = 0

    @weak_lru(maxsize=32)
    def compute(self, x):
        self.calls += 1
        return x * self.factor


@pytest.mark.no_connection
def test_weak_lru_cache():
    calc = ExpensiveCalculator(10)

    result1 = calc.compute(5)
    result2 = calc.compute(5)

    # The compute method is called only once
    assert calc.calls == 1

    assert result1 == 50
    assert result2 == 50

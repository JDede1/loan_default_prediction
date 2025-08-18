import pytest

from src.utils import add_numbers


@pytest.mark.unit
def test_add_numbers_basic():
    assert add_numbers(2, 3) == 5
    assert add_numbers(-1, 1) == 0
    assert add_numbers(0, 0) == 0


@pytest.mark.unit
def test_add_numbers_large():
    assert add_numbers(10**6, 10**6) == 2_000_000

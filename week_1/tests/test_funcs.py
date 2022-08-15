import datetime

import pytest
from project.week_1 import (
    find_greatest_high_value,
    get_max,
    Stock,
)


@pytest.fixture
def stocks():
    return [
        Stock(date=datetime.datetime(2022, 1, 1, 0, 0), close=10.0, volume=10, open=10.0, high=10.0, low=10.0),
        Stock(date=datetime.datetime(2022, 1, 2, 0, 0), close=10.0, volume=10, open=11.0, high=10.0, low=10.0),
        Stock(date=datetime.datetime(2022, 1, 3, 0, 0), close=10.0, volume=10, open=10.0, high=12.0, low=10.0),
        Stock(date=datetime.datetime(2022, 1, 4, 0, 0), close=10.0, volume=10, open=10.0, high=11.0, low=10.0),
        Stock(date=datetime.datetime(2022, 1, 5, 0, 0), close=10.0, volume=10, open=10.0, high=13.0, low=10.0),
    ]


def test_get_max():
    first = Stock(date=datetime.datetime(2022, 1, 1, 0, 0), close=10.0, volume=10, open=10.0, high=10.0, low=10.0)
    second = Stock(date=datetime.datetime(2022, 1, 3, 0, 0), close=10.0, volume=10, open=10.0, high=12.0, low=10.0)
    stock = get_max(first, second)

    assert stock.high == 12.0


def test_find_greatest_high_value(stocks):
    stock = find_greatest_high_value(stocks, len(stocks))
    assert stock.high == 13.0

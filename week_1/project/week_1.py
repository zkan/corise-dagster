import csv
from datetime import datetime
from typing import List

from dagster import In, Nothing, Out, job, op, usable_as_dagster_type
from pydantic import BaseModel


@usable_as_dagster_type(description="Stock data")
class Stock(BaseModel):
    date: datetime
    close: float
    volume: int
    open: float
    high: float
    low: float

    @classmethod
    def from_list(cls, input_list: list):
        """Do not worry about this class method for now"""
        return cls(
            date=datetime.strptime(input_list[0], "%Y/%m/%d"),
            close=float(input_list[1]),
            volume=int(float(input_list[2])),
            open=float(input_list[3]),
            high=float(input_list[4]),
            low=float(input_list[5]),
        )


@usable_as_dagster_type(description="Aggregation of stock data")
class Aggregation(BaseModel):
    date: datetime
    high: float


@op(
    config_schema={"s3_key": str},
    out={"stocks": Out(dagster_type=List[Stock])},
    tags={"kind": "s3"},
    description="Get a list of stocks from an S3 file",
)
def get_s3_data(context) -> List[Stock]:
    output = list()
    with open(context.op_config["s3_key"]) as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            stock = Stock.from_list(row)
            output.append(stock)
    return output


def get_max(first: Stock, second: Stock) -> Stock:
    if first.high >= second.high:
        return first
    else:
        return second


def find_greatest_high_value(stocks: List[Stock], n: int) -> Stock:
    if n == 1:
        return stocks[0]

    return get_max(stocks[n - 1], find_greatest_high_value(stocks, n - 1))


@op(
    ins={"stocks": In(dagster_type=List[Stock])},
    out={"agg": Out(dagster_type=Aggregation)},
    description="Given a list of stocks, return the aggregation with the greatest high value",
)
def process_data(stocks: List[Stock]) -> Aggregation:
    greatest_high_stock = find_greatest_high_value(stocks, len(stocks))
    agg = Aggregation(
        date=greatest_high_stock.date,
        high=greatest_high_stock.high,
    )

    return agg


@op(
    ins={"aggregation": In(dagster_type=Aggregation)},
    description="Upload an aggregation to Redis",
)
def put_redis_data(aggregation: Aggregation) -> Nothing:
    pass


@job
def week_1_pipeline():
    stocks = get_s3_data()
    aggregation = process_data(stocks)
    put_redis_data(aggregation)

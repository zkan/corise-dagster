from typing import List

from dagster import (
    asset,
    AssetIn,
    Nothing,
    with_resources,
)
from project.resources import redis_resource, s3_resource
from project.types import Aggregation, Stock


@asset(
    config_schema={"s3_key": str},
    required_resource_keys={"s3"},
    description="Get a list of stocks from an S3 file",
    group_name="corise",
    compute_kind="s3",
)
def get_s3_data(context):
    output = list()
    s3_key = context.op_config["s3_key"]
    for each in context.resources.s3.get_data(s3_key):
        stock = Stock.from_list(each)
        output.append(stock)

    return output


@asset(
    ins={"get_s3_data": AssetIn("get_s3_data")},
    description="Given a list of stocks, return the aggregation with the greatest high value",  # noqa: E501
    group_name="corise",
    compute_kind="python",
)
def process_data(get_s3_data):
    stock = max(get_s3_data, key=lambda x: x.high)
    return Aggregation(date=stock.date, high=stock.high)


@asset(
    ins={"process_data": AssetIn("process_data")},
    required_resource_keys={"redis"},
    description="Upload an aggregation to Redis",
    group_name="corise",
    compute_kind="redis",
)
def put_redis_data(context, process_data):
    date = process_data.date
    value = process_data.high
    context.resources.redis.put_data(str(date), str(value))


get_s3_data_docker, process_data_docker, put_redis_data_docker = with_resources(
    definitions=[get_s3_data, process_data, put_redis_data],
    resource_defs={"s3": s3_resource, "redis": redis_resource},
    resource_config_by_key={
        "s3": {
            "config": {
                "bucket": "dagster",
                "access_key": "test",
                "secret_key": "test",
                "endpoint_url": "http://localstack:4566",
            }
        },
        "redis": {
            "config": {
                "host": "redis",
                "port": 6379,
            }
        },
    },
)

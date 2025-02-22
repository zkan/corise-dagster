from typing import List

from dagster import (
    In,
    Nothing,
    Out,
    ResourceDefinition,
    RetryPolicy,
    RunRequest,
    schedule,
    ScheduleDefinition,
    SkipReason,
    graph,
    op,
    sensor,
    static_partitioned_config,
)
from project.resources import mock_s3_resource, redis_resource, s3_resource
from project.sensors import get_s3_keys
from project.types import Aggregation, Stock


@op(
    config_schema={"s3_key": str},
    required_resource_keys={"s3"},
    out={"stocks": Out(dagster_type=List[Stock])},
    description="Get a list of stocks from an S3 file",
    tags={"kind": "s3"},
)
def get_s3_data(context) -> List[Stock]:
    output = list()
    s3_key = context.op_config["s3_key"]
    for each in context.resources.s3.get_data(s3_key):
        stock = Stock.from_list(each)
        output.append(stock)

    return output


@op(
    ins={"stocks": In(dagster_type=List[Stock])},
    out={"agg": Out(dagster_type=Aggregation)},
    description="Given a list of stocks, return the aggregation with the greatest high value",  # noqa: E501
)
def process_data(stocks: List[Stock]) -> Aggregation:
    stock = max(stocks, key=lambda x: x.high)
    return Aggregation(date=stock.date, high=stock.high)


@op(
    required_resource_keys={"redis"},
    ins={"aggregation": In(dagster_type=Aggregation)},
    description="Upload an aggregation to Redis",
    tags={"kind": "redis"},
)
def put_redis_data(context, aggregation: Aggregation) -> Nothing:
    date = aggregation.date
    value = aggregation.high
    context.resources.redis.put_data(str(date), str(value))


@graph
def week_3_pipeline():
    stocks = get_s3_data()
    aggregation = process_data(stocks)
    put_redis_data(aggregation)


local = {
    "ops": {"get_s3_data": {"config": {"s3_key": "prefix/stock_9.csv"}}},
}

docker_resource_config = {
    "resources": {
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
}
docker = {
    **docker_resource_config,
    "ops": {"get_s3_data": {"config": {"s3_key": "prefix/stock_9.csv"}}},
}
# docker = docker_resource_config | {"ops": {"get_s3_data": {"config": {"s3_key": "prefix/stock_9.csv"}}}}


PARTITIONS = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]


@static_partitioned_config(partition_keys=PARTITIONS)
def docker_config(partition_key: str):
    return {
        **docker_resource_config,
        "ops": {"get_s3_data": {"config": {"s3_key": f"prefix/stock_{partition_key}.csv"}}},
    }
    # return docker_resource_config | {
    #     "ops": {"get_s3_data": {"config": {"s3_key": f"prefix/stock_{partition_key}.csv"}}}
    # }


local_week_3_pipeline = week_3_pipeline.to_job(
    name="local_week_3_pipeline",
    config=local,
    resource_defs={
        "s3": mock_s3_resource,
        "redis": ResourceDefinition.mock_resource(),
    },
)

docker_week_3_pipeline = week_3_pipeline.to_job(
    name="docker_week_3_pipeline",
    config=docker_config,
    resource_defs={
        "s3": s3_resource,
        "redis": redis_resource,
    },
    op_retry_policy=RetryPolicy(max_retries=10, delay=1),
)


local_week_3_schedule = ScheduleDefinition(job=local_week_3_pipeline, cron_schedule="*/15 * * * *", run_config=local)


@schedule(job=docker_week_3_pipeline, cron_schedule="0 * * * *")
def docker_week_3_schedule():
    for p in PARTITIONS:
        request = docker_week_3_pipeline.run_request_for_partition(partition_key=p, run_key=p)
        yield request


@sensor(job=docker_week_3_pipeline, minimum_interval_seconds=30)
def docker_week_3_sensor(context):
    new_keys = get_s3_keys(
        bucket="dagster",
        prefix="prefix",
        endpoint_url="http://host.docker.internal:4566",
    )
    if not new_keys:
        yield SkipReason("No new s3 files found in bucket.")
        return

    for new_key in new_keys:
        run_config = {
            **docker_resource_config,
            "ops": {"get_s3_data": {"config": {"s3_key": new_key}}},
        }
        # run_config = docker_resource_config | {"ops": {"get_s3_data": {"config": {"s3_key": new_key}}}}
        yield RunRequest(
            run_key=new_key,
            run_config=run_config,
        )

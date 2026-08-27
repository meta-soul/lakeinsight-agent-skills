import argparse

import ray
from daft.runners import set_runner_ray

from app.config import ReadConfig
from app.reader import read_lakesoul_sample
from utils.output import print_result


def parse_args() -> ReadConfig:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default="czods")
    parser.add_argument("--table", default="user")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--thread-count", type=int, default=1)

    args, unknown_args = parser.parse_known_args()
    if unknown_args:
        print(f"Ignoring platform arguments: {unknown_args}", flush=True)

    return ReadConfig(
        namespace=args.namespace,
        table=args.table,
        limit=args.limit,
        batch_size=args.batch_size,
        thread_count=args.thread_count,
    )


def main() -> None:
    config = parse_args()

    ray.init(address="auto")
    set_runner_ray(address="auto", noop_if_initialized=True)

    schema, result = read_lakesoul_sample(config)
    print_result(config, schema, result)


if __name__ == "__main__":
    main()

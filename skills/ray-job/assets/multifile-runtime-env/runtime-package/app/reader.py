import daft
import lakesoul.daft  # noqa: F401 - register the LakeSoul Daft integration
from lakesoul import LakeSoulCatalog

from app.config import ReadConfig


def build_dataframe(config: ReadConfig) -> daft.DataFrame:
    catalog = LakeSoulCatalog.from_env()
    scan = catalog.scan(
        config.table,
        namespace=config.namespace,
    ).options(
        batch_size=config.batch_size,
        thread_count=config.thread_count,
    )
    return scan.to_daft()


def read_lakesoul_sample(config: ReadConfig):
    source = build_dataframe(config)
    schema = source.schema()
    result = source.limit(config.limit).collect()
    return schema, result

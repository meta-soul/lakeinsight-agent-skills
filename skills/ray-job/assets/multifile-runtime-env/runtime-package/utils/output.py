from app.config import ReadConfig


def print_result(config: ReadConfig, schema, result) -> None:
    print(f"table: {config.namespace}.{config.table}", flush=True)
    print("schema:", schema, flush=True)
    print("rows:", result.to_arrow().to_pydict(), flush=True)

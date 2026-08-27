from dataclasses import dataclass


@dataclass(frozen=True)
class ReadConfig:
    namespace: str
    table: str
    limit: int
    batch_size: int
    thread_count: int

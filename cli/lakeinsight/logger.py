"""Logging config for the lakeinsight CLI.

Call ``setup_logging(verbosity)`` once at startup.
Other modules use ``log = logging.getLogger("lakeinsight")``.
"""

from __future__ import annotations

import logging

LOG = logging.getLogger("lakeinsight")


def setup_logging(verbosity: int = 0) -> None:
    """Configure the root lakeinsight logger.

    verbosity:
        0 (default) — WARNING
        1 (--verbose) — INFO
        2 (--debug) — DEBUG
    """
    levels = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}
    level = levels.get(verbosity, logging.DEBUG)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))

    LOG.setLevel(level)
    LOG.addHandler(handler)
    LOG.propagate = False

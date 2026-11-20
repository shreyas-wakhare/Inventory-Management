"""Structured logging configuration."""

import logging


def configure_logging(*, debug: bool = False) -> None:
    """Initialize baseline application logging."""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


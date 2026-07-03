import logging
import sys

from app.core.config import settings


def setup_logging() -> logging.Logger:
    log = logging.getLogger("marketmind-oecd")
    log.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    if not log.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        log.addHandler(handler)

    return log


logger = setup_logging()

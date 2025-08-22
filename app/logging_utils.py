#logging_utils.py
import logging
import os

def get_logger(name: str) -> logging.Logger:
    verbosity = os.getenv("VERBOSE", "1")
    level = logging.DEBUG if verbosity == "2" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    return logging.getLogger(name)
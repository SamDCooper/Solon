import datetime
import logging
import os
import sys

from logging import StreamHandler
from logging.handlers import RotatingFileHandler

from .config import get_config

__all__ = []

log = logging.getLogger(__name__)
config = get_config(__name__)

log.info(f"Loading {__name__}")

handler_builders = {}


def handler_builder(func):
    handler_builders[func.__name__] = func
    return func


@handler_builder
def stdout_handler(_):
    return StreamHandler(sys.stdout)


@handler_builder
def rotating_file_handler(params):
    params["filename"] = os.path.join(config["folder"], params["filename"])
    return RotatingFileHandler(**params)


def parse_handlers(d):
    h = []
    for func_name, params in d.items():
        func = handler_builders[func_name]
        h.append(func(params))
    return h


try:
    os.mkdir(config["folder"])
except FileExistsError:
    pass

basic = config["basic_config"]
basic["handlers"] = parse_handlers(basic["handlers"])
basic["level"] = logging.getLevelName(basic["level"])
logging.basicConfig(**basic)

log.info(f"Logging online. Startup time is {datetime.datetime.now()}.")
log.info(f"Logging parameters are as follows: {config}.")

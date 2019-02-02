import json
import logging

log = logging.getLogger(__name__)

log.info(f"Loading {__name__}")

__all__ = ["get_config"]

with open("config.json") as f:
    config = json.load(f)


def get_config(name):
    if name in config:
        return config[name]
    else:
        log.warning(f"There is no config for {name}.")
        return None

import logging
import os
import pprint
import ast

from .config import get_config
from .core import SocratesStaticError
from .core import timedelta_from_string

__all__ = ["get_data", "save_all", "save_interval"]

log = logging.getLogger(__name__)
config = get_config(__name__)

log.info(f"Loading {__name__}")

db = {}
db_folder = config["folder_name"]
enabled = config["enabled"]
save_interval = timedelta_from_string(config["save_interval"])

if not os.path.exists(db_folder):
    os.mkdir(db_folder)

if not os.path.isdir(db_folder):
    raise SocratesStaticError(f"os.path.isdir failed on folder {db_folder}.")

pre_save_all_callbacks = []


def pre_save_all(func):
    pre_save_all_callbacks.append(func)
    return func


def get_data(identifier, create):
    if identifier in db:
        return db[identifier]

    else:
        data = create()
        try:
            path = os.path.join(db_folder, identifier)
            with open(path) as f:
                v = ast.literal_eval(f.read())
                for key, value in v.items():
                    data.__setattr__(key, value)
        except FileNotFoundError as e:
            log.warning(f"Data file with identifier {identifier} not found. This may not be a problem on a fresh run.")

        db[identifier] = data
        return data


def save_all():
    log.info(f"Calling pre-save callbacks.")
    for func in pre_save_all_callbacks:
        func()

    if not enabled:
        rep = {identifier: vars(data) if hasattr(data, "__dict__") else data for identifier, data in db.items()}
        rep_str = "\n".join([f"{k}\n{v}\n" for k, v in rep.items()])
        log.info(f"Saving is disabled. Database looks like:\n{rep_str}")
        return

    log.info(f"Saving {len(db)} objects to {db_folder}.")

    for identifier, data in db.items():
        if hasattr(data, "__dict__"):
            v = vars(data)
        else:
            v = data
        with open(f"{db_folder}/{identifier}", "w") as f:
            print(pprint.pformat(v, width=int(config["line_width"])), file=f)
    log.info("Save finished.")

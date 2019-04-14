import asyncio
import datetime
import logging
import inspect
import traceback
import weakref

from .config import get_config
from .core import DynamicNameCollisionError
from .core import IncorrectSignatureError
from .core import NotACoroutineError
from .core import timedelta_from_string
from .database import get_data

__all__ = ["start_timed_event_loop", "TimedEvent"]

log = logging.getLogger(__name__)
config = get_config(__name__)

log.info(f"Loading {__name__}")

sleep_interval = timedelta_from_string(config["sleep_interval"])


class Data:
    def __init__(self):
        self.last_updated_timestamp = {}  # key -> UNIX timestamp of last time event called


data = get_data(__name__, lambda: Data())

timed_events = {}  # key -> (weakref(obj), callback, properties, timedelta)


async def loop_function():
    global timed_events
    while True:
        dead_objects = []
        now = datetime.datetime.utcnow()
        for key, (obj_ref, callback, properties, timedelta) in timed_events.items():
            last_updated_time = datetime.datetime.utcfromtimestamp(data.last_updated_timestamp[key])
            if (now - last_updated_time) > timedelta:
                try:
                    obj = obj_ref()
                    if obj is None or (hasattr(obj, "active") and not obj.active):
                        dead_objects.append(key)
                    else:
                        # we assume obj is a cog. It might not have an active attribute if it's still
                        # being constructud. In this case, we do not call until construction has finished.
                        # We only call on active cogs.
                        if hasattr(obj, "active") and obj.active:
                            log.info(f"Hit timed event {key}.")
                            await callback(obj)

                except Exception as e:
                    trace = traceback.format_exc()
                    log.error(f"{e}\n{trace}")

                data.last_updated_timestamp[key] = now.timestamp()

        if len(dead_objects) > 0:
            timed_events = {k: v for k, v in timed_events.items() if k not in dead_objects}

        await asyncio.sleep(sleep_interval.total_seconds())


def start_timed_event_loop(loop):
    log.info(f"Timed event loop starting.")
    asyncio.ensure_future(loop_function(), loop=loop)


class TimedEventFunction:
    def __init__(self, callback, properties):
        if not inspect.iscoroutinefunction(callback):
            raise NotACoroutineError(f"{callback} should be a coroutine.")
        if len(inspect.signature(callback).parameters) != 1:
            raise IncorrectSignatureError(
                f"Callback should take 1 argument - instead it takes {len(inspect.signature(callback).parameters)}.")

        self.callback = callback
        self.properties = properties

    def start(self, obj, timedelta):
        key = f"{type(obj).__name__}.{self.callback.__name__}"
        if key in timed_events:
            raise DynamicNameCollisionError(f"There is already a timed event by key {key} running.")

        if key not in data.last_updated_timestamp:
            # We assume latest time - most of the time a newly registered
            # looping function won't be due, and we don't want first-run
            # behaviour to be different for no reason
            now = datetime.datetime.utcnow()
            data.last_updated_timestamp[key] = now.timestamp()

        timed_events[key] = (weakref.ref(obj), self.callback, self.properties, timedelta)

    def is_running(self, obj):
        key = f"{type(obj).__name__}.{self.callback.__name__}"
        return key in timed_events


def TimedEvent(**kwargs):
    def wrapper(func):
        return TimedEventFunction(func, kwargs)

    return wrapper

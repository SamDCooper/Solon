"""
Only stuff which doesn't rely on anything outside the module goes here. No logging. No config, etc.

This file loaded first.
"""

import copy
import datetime
import decimal
import emoji
import importlib
import logging
import re

__all__ = ["copy_class", "CogNotFoundError", "DynamicNameCollisionError", "IncorrectSignatureError",
           "InvalidArgumentsError", "MarkupError", "NamingConventionError",
           "NoPermissionsError", "NotACoroutineError", "SocratesError", "SocratesRuntimeError", "SocratesStaticError",
           "StaticNameCollisionError", "TestFailureError",
           "timedelta_from_string", "UselessCogError", "InvalidConfigError", "merge_dictionaries", "no_guild_id",
           "CommandError", "is_emoji", "compare_emoji", "is_url", "is_youtube_url"]

config = {

}
log = logging.getLogger(__name__)


class SocratesError(Exception):
    def __init__(self, message):
        super(SocratesError, self).__init__(message)
        log.error(message)


class SocratesStaticError(SocratesError):
    pass


class NamingConventionError(SocratesStaticError):
    pass


class MarkupError(SocratesStaticError):
    pass


class StaticNameCollisionError(SocratesStaticError):
    pass


class UselessCogError(SocratesStaticError):
    pass


class NotACoroutineError(SocratesStaticError):
    pass


class IncorrectSignatureError(SocratesStaticError):
    pass


class SocratesRuntimeError(SocratesError):
    pass


class CommandError(SocratesRuntimeError):
    pass


class NoPermissionsError(SocratesRuntimeError):
    pass


class TestFailureError(SocratesRuntimeError):
    pass


class InvalidArgumentsError(SocratesRuntimeError):
    pass


class CogNotFoundError(SocratesRuntimeError):
    pass


class DynamicNameCollisionError(SocratesRuntimeError):
    pass


class InvalidConfigError(SocratesRuntimeError):
    pass


no_guild_id = 0

forward_discord_py_cogs = []


def get_bot():
    m = importlib.import_module("solon.bot")
    return m.Bot


def ForwardDiscordPyCog(cls):
    forward_discord_py_cogs.append(cls)
    return cls


def copy_class(cls, class_name=None):
    if class_name is None:
        class_name = f"{cls.__name__}Copy"
    attrs = {k: v for k, v in cls.__dict__.items() if not k.startswith("__") or callable(v)}
    copy_cls = type(class_name, cls.__bases__, attrs)
    for attr_name, attr in attrs.items():
        try:
            hash(attr)
        except TypeError:
            # Assume lack of __hash__ implies mutability. This is NOT
            # a bullet proof assumption but good in many cases.
            setattr(copy_cls, attr_name, copy.deepcopy(attr))
    return copy_cls


def timedelta_from_string(string):
    string = string.lower()
    total_seconds = decimal.Decimal("0")
    previous_number = []
    for c in string:
        if c.isalpha():
            if previous_number:
                number = decimal.Decimal("".join(previous_number))
                if c == "w":
                    total_seconds += number * 60 * 60 * 24 * 7
                elif c == "d":
                    total_seconds += number * 60 * 60 * 24
                elif c == "h":
                    total_seconds += number * 60 * 60
                elif c == "m":
                    total_seconds += number * 60
                elif c == "s":
                    total_seconds += number
                previous_number = []
        elif c.isnumeric() or c == ".":
            previous_number.append(c)
        else:
            raise InvalidArgumentsError(
                f"{string} does not represent a valid time delta. Looking for formats like 1w2d3h4m5s.")
    return datetime.timedelta(seconds=float(total_seconds))


def merge_dictionaries(dominant, recessive):
    ret = recessive.copy()
    for key, value in dominant.items():
        if isinstance(value, dict):
            node = recessive.setdefault(key, {})
            ret[key] = merge_dictionaries(value, node)
        else:
            ret[key] = value
    return ret


def is_emoji(s):
    if s in emoji.UNICODE_EMOJI:
        return True
    # might be we have to shave off a second character
    if s[0] in emoji.UNICODE_EMOJI:
        return True
    return False


def compare_emoji(lhs, rhs):
    if type(lhs) == type(rhs):
        if type(lhs) == str:
            return lhs == rhs or lhs[0] == rhs or lhs == rhs[0] or lhs[0] == rhs[0]
        else:
            return lhs == rhs
    else:
        return False


def is_url(potential_url):
    return re.match(r"https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{2,256}\.[a-z]{2,6}\b([-a-zA-Z0-9@:%_\+.~#?&//=]*)",
                    potential_url
                    )


def is_youtube_url(potential_url):
    return re.match(
        r"^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$",
        potential_url)

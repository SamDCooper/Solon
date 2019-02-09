import discord
import logging

from .core import SocratesRuntimeError
from .core import get_bot

log = logging.getLogger(__name__)

__all__ = ["Emoji", "emoji_equals"]


class EmojiError(SocratesRuntimeError):
    pass


class Emoji:
    def __init__(self, guild_id, name, id=None, animated=False):
        self.guild_id = guild_id
        self.name = name
        self.id = id
        self.animated = False

    def is_custom_emoji(self):
        return self.id is not None

    def is_unicode_emoji(self):
        return not self.is_custom_emoji()

    @property
    def discord_py_emoji(self):
        if self.is_unicode_emoji():
            return self.name
        else:
            guild = get_bot().get_guild(self.guild_id)
            if guild:
                for emoji in guild.emojis:
                    if emoji.id == self.id:
                        return emoji

        log.warning(f"Could not get discord.py emoji for {self}.")
        return None

    def __str__(self):
        if self.id is None:
            return self.name
        if self.animated:
            return f'<a:{self.name}:{self.id}>'
        return f'<:{self.name}:{self.id}>'


def emoji_equals(lhs, rhs):
    # At least one arg (preferably lhs) must be an Emoji
    if not isinstance(lhs, Emoji) and not isinstance(rhs, Emoji):
        raise EmojiError(f"Wrong emoji comparison.")

    # We assume from here that lhs is an Emoji, rhs might not be
    # if this isn't the case but it can work the other way, we
    # just swap arguments
    if not isinstance(lhs, Emoji):  # we know rhs is an Emoji
        return emoji_equals(rhs, lhs)

    if isinstance(rhs, Emoji):
        # Both Emojis
        if lhs.is_custom_emoji() and rhs.is_custom_emoji():
            return lhs.id == rhs.id
        elif lhs.is_unicode_emoji() and rhs.is_unicode_emoji():
            return lhs.name == lhs.name

    elif isinstance(rhs, str):
        # Comparing lhs to a unicode emoji
        return lhs.name == rhs

    elif isinstance(rhs, discord.Emoji):
        # Comparing lhs to a custom emoji
        return lhs.id == rhs.id

    return False

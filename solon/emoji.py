import discord

from .core import SocratesRuntimeError

__all__ = ["Emoji", "emoji_equals"]


class EmojiError(SocratesRuntimeError):
    pass


class Emoji:
    def __init__(self, name, id=None, animated=False):
        self.name = name
        self.id = id
        self.animated = False

    def is_custom_emoji(self):
        return self.id is not None

    def is_unicode_emoji(self):
        return not self.is_custom_emoji()

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

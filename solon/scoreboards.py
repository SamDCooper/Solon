import logging
import weakref

from .bot import Bot
from .bot import get_identifier
from .config import get_config
from .core import SocratesRuntimeError
from .core import timedelta_from_string
from .timing import TimedEvent

__all__ = ["register_scoreboard", "get_scoreboard_by_identifier"]

log = logging.getLogger(__name__)
config = get_config(__name__)

log.info(f"Loading {__name__}")


class ScoreboardError(SocratesRuntimeError):
    pass


award_rankings_callbacks = {}
award_methods = {}
scoreboards_by_identifier = {}


def get_scoreboard_by_identifier(identifier):
    sb = scoreboards_by_identifier.get(identifier)()
    if sb is None or (hasattr(sb, "active") and not sb.active):
        raise ScoreboardError(f"Could not find any scoreboard with that name.")
    return sb.scoreboard


def AwardMethod(key):
    def wrapper(cls):
        award_methods[key.lower()] = cls
        return cls

    return wrapper


@AwardMethod("score")
class award_by_score:
    def __init__(self, scoreboard):
        self.scoreboard = scoreboard

    @property
    def modified_scoreboard(self):
        return self.scoreboard.items()

    def resolve_awards(self, member, score, award_ranks):
        roles_to_add = []
        roles_to_remove = []

        for threshold, role in award_ranks.items():
            if threshold >= 0:
                if score >= threshold:
                    roles_to_add.append(role)
                else:
                    roles_to_remove.append(role)

            elif threshold < 0:
                if score <= threshold:
                    roles_to_add.append(role)
                else:
                    roles_to_remove.append(role)
        return roles_to_add, roles_to_remove


@AwardMethod("rank")
class award_by_rank:
    def __init__(self, scoreboard):
        self.scoreboard = sorted(scoreboard.items(), key=lambda kv: -kv[1])
        self.member_count = 0

    @property
    def modified_scoreboard(self):
        return self.scoreboard

    def resolve_awards(self, member, score, award_ranks):
        roles_to_add = []
        roles_to_remove = []

        for position, role in award_ranks.items():
            if self.member_count < position:
                roles_to_add.append(role)
            else:
                roles_to_remove.append(role)

        self.member_count = self.member_count + 1

        return roles_to_add, roles_to_remove


def register_scoreboard(scoreboard_cog, guild_id, settings):
    if not hasattr(scoreboard_cog, "scoreboard"):
        raise ScoreboardError("No 'scoreboard' attribute found.")

    @TimedEvent()
    async def award_rankings(_):
        award_ranks = settings["award_ranks"]
        award_eligible = settings["award_eligible"]
        award_ranks_exclude = settings.get("award_ranks_exclude", None)

        guild = Bot.get_guild(guild_id)

        sb = scoreboard_cog.scoreboard

        award_method_key = settings["award_method"].lower()
        if award_method_key not in award_methods:
            raise ScoreboardError(f"I don't recognise the award method {award_method_key} in {guild}.")

        award_method = award_methods[award_method_key](sb)
        for user_id, score in award_method.modified_scoreboard:
            member = guild.get_member(user_id)
            if member:
                excluded = False
                if award_ranks_exclude:
                    for role in member.roles:
                        if role in award_ranks_exclude:
                            excluded = True
                            break

                if award_eligible in member.roles:
                    if not excluded:
                        roles_to_add, roles_to_remove = award_method.resolve_awards(member, score, award_ranks)

                        # Filter roles so we're not sending requests to add Rank X when the member already has Rank X
                        roles_to_add = [role for role in roles_to_add if role not in member.roles]
                        roles_to_remove = [role for role in roles_to_remove if role in member.roles]
                    else:
                        roles_to_add = []
                        roles_to_remove = [role for role in award_ranks.values() if role in member.roles]

                    reason = f"Awards redistribution"
                    if roles_to_add:
                        await member.add_roles(*roles_to_add, reason=reason)
                        reason = None

                    if roles_to_remove:
                        await member.remove_roles(*roles_to_remove, reason=reason)

                    if roles_to_add or roles_to_remove:
                        log.info(f"Adding roles {roles_to_add} and removing "
                                 f"roles {roles_to_remove} for {member} in {scoreboard_cog.identifier}")

    scoreboards_by_identifier[scoreboard_cog.__class__.__name__] = weakref.ref(scoreboard_cog)
    award_rankings.start(scoreboard_cog, timedelta_from_string(config["award_interval"]))

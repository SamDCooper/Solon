import discord
import inspect
import logging
import traceback

from discord.ext.commands import Bot as BaseBotType

from .core import CogNotFoundError
from .core import copy_class
from .core import DynamicNameCollisionError
from .core import InvalidArgumentsError
from .core import MarkupError
from .core import NamingConventionError
from .core import CommandError
from .core import NoPermissionsError
from .core import StaticNameCollisionError
from .core import UselessCogError
from .core import forward_discord_py_cogs
from .core import no_guild_id
from .config import get_config
from .database import get_data
from .timing import start_timed_event_loop
from .settings import create_settings
from .settings import get_setting_value

__all__ = ["Bot", "Cog", "Command", "Event", "parse_identifier", "get_identifier", "check_permissions",
           "get_name_from_user_id"]

log = logging.getLogger(__name__)
config = get_config(__name__)

log.info(f"Loading {__name__}")

all_cog_types = {}


class Data:
    def __init__(self):
        self.active_cog_overrides = {}  # identifiers to bools


data = get_data(__name__, lambda: Data())


def parse_identifier(identifier):
    if "." in identifier:
        cog_type_name, guild_id = identifier.split(".")
        return cog_type_name, int(guild_id)
    else:
        return None, None


def get_identifier(cog_type_name, guild_id):
    cog_type_name = cog_type_name.lower()
    if cog_type_name not in all_cog_types:
        raise CogNotFoundError(f"Can't find a cog called {cog_type_name}.")

    cog_type = all_cog_types[cog_type_name]
    if not cog_type.guild_local:
        guild_id = no_guild_id

    return f"{cog_type_name}.{guild_id}"


class BotType(BaseBotType):
    @staticmethod
    def parse_identifier(identifier):
        return parse_identifier(identifier)

    @staticmethod
    def get_identifier(cog_type_name, guild_id):
        return get_identifier(cog_type_name, guild_id)


Bot = BotType(**config["bot_options"])


def get_name_from_user_id(guild_id, user_id):
    global_settings_identifier = get_identifier("globals", guild_id)
    name_format_has_nick = get_setting_value(global_settings_identifier, "name_format_has_nick")
    name_format_no_nick = get_setting_value(global_settings_identifier, "name_format_no_nick")
    name_decor_absent = get_setting_value(global_settings_identifier, "name_decor_absent")
    name_decor_present = get_setting_value(global_settings_identifier, "name_decor_present")
    name_unknown_user = get_setting_value(global_settings_identifier, "name_unknown_user")

    guild = Bot.get_guild(guild_id)
    member = guild.get_member(user_id)
    if member:
        if member.nick:
            name = name_format_has_nick.format(nick=member.nick, name=member.name, display_name=member.display_name)
        else:
            name = name_format_no_nick.format(name=member.name)
        return name_decor_present.format(user=name)

    else:
        user = Bot.get_user(user_id)
        if user:
            name = name_format_no_nick.format(name=user.name)
        else:
            name = name_unknown_user.format(code=user_id % 10000)
        return name_decor_absent.format(user=name)


async def check_permissions(ctx, perms, *, check=all):
    if ctx.author.guild_permissions.administrator:
        return True

    global_settings_identifier = get_identifier("globals", ctx.guild.id)
    use_commands = get_setting_value(global_settings_identifier, "use_commands")
    if use_commands is None:
        raise CommandError(
            "use_commands role is not set on this server. Nobody has permission to use commands until this is set.")

    if use_commands not in ctx.author.roles:
        return False

    resolved = ctx.channel.permissions_for(ctx.author)

    def get_value(name):
        if name == "is_owner":
            return Bot.owner_id == ctx.author.id
        else:
            return getattr(resolved, name, None)

    return check(get_value(name) == value for name, value in perms.items())


def get_default_cogs(querying_guild_id=None):
    cogs_to_init = []
    # All default-active cogs
    for cog_type_name, cog_type in all_cog_types.items():
        if cog_type.default_active:
            if cog_type.guild_local:
                guilds = [g.id for g in Bot.guilds]
            else:
                guilds = [no_guild_id]

            for guild_id in guilds:
                if querying_guild_id is None or querying_guild_id == guild_id:
                    cogs_to_init.append(get_identifier(cog_type_name, guild_id))
    return cogs_to_init


guild_event_codex = {
    "on_message": lambda args: args[0].guild.id if args[0].guild else 0,
    "on_reaction_add": lambda args: args[0].message.guild.id if args[0].message.guild else 0,
    "on_reaction_remove": lambda args: args[0].message.guild.id if args[0].message.guild else 0,
    "on_member_join": lambda args: args[0].guild.id if args[0].guild else 0,
    "on_member_update": lambda args: args[1].guild.id if args[1].guild else 0
}


def Event():
    def wrapper(func):
        if not func.__name__.startswith("on_"):
            raise NamingConventionError(f"Event function names must start with on_: {func.__qualname__}")

        async def wrapped_func(*args):
            cog_type = all_cog_types[func.__qualname__.split(".")[0].lower()]
            if not cog_type.guild_local:
                return await func(*args)
            else:
                cog = args[0]
                guild_id = guild_event_codex[func.__name__](
                    args[1:])  # 1: because we want the codex to assume no self argument
                gid = parse_identifier(cog.__class__.__name__)[1]
                if gid == guild_id:
                    return await func(*args)

        setattr(wrapped_func, "is_event", True)
        return wrapped_func

    return wrapper


class CommandCog:
    pass


class Subcommand:
    def __init__(self, func, fname, perms):
        self.fname = fname.lower()
        self.perms = perms
        self.func = func


def Command(name=None, **perms):
    def wrapper(func):
        return Subcommand(func, name or func.__name__, perms)

    return wrapper


def get_subcommands(cls):
    subcommands = {}

    members = inspect.getmembers(cls)
    for name, member in members:
        if name.startswith("on_") and not hasattr(member, "is_event"):
            raise MarkupError(f"{member}: Cog event listeners must be marked with @Event")

        if isinstance(member, Subcommand):
            if member.fname in subcommands:
                raise StaticNameCollisionError(f"There is already a subcommand {member.fname} in {cls}")

            subcommands[member.fname] = member
    return subcommands


async def call_command(cls_name, ctx, *args):
    if len(args) == 0:
        raise InvalidArgumentsError(f"No arguments given to {cls_name}.")

    cog_type = all_cog_types[cls_name]
    subcommands = get_subcommands(cog_type)
    subcommand_name = args[0].lower()
    args = args[1:]
    subcommand = subcommands.get(subcommand_name, None)
    if subcommand is None:
        raise InvalidArgumentsError(f"Argument {subcommand_name} did not correspond to a subcommand in {cls_name}.")

    if cog_type.guild_only and ctx.guild is None:
        raise NoPermissionsError(f"{cls_name} can only be used on servers.")

    if not await check_permissions(ctx, subcommand.perms):
        raise NoPermissionsError(
            f"{ctx.author} does not have the permissions to call {subcommand.fname} on {ctx.guild}.")

    cog = Bot.get_cog(get_identifier(cls_name, no_guild_id))
    if cog is None and ctx.guild is not None:
        cog = Bot.get_cog(get_identifier(cls_name, ctx.guild.id))
    if cog is None:
        raise CogNotFoundError(f"Could not get cog {cls_name} for guild {ctx.guild}. Is it activated?")

    signature = inspect.signature(subcommand.func)
    params = list(signature.parameters.values())[2:]  # want to skip self & ctx
    num_args = len(params)

    scargs = [cog, ctx]
    sckwargs = {}

    for i in range(0, num_args):
        if len(args) == 0:
            break

        param = params[i]
        annotation = param.annotation
        arg = args[0] if i != num_args - 1 else " ".join(args)
        if annotation is not inspect.Parameter.empty:
            converter = annotation()
            if isinstance(converter, discord.ext.commands.Converter):
                arg = await converter.convert(ctx, arg)

        if param.kind == inspect.Parameter.POSITIONAL_ONLY or param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            scargs.append(arg)
        elif param.kind == inspect.Parameter.KEYWORD_ONLY:
            sckwargs[param.name] = arg
        elif param.kind == inspect.Parameter.VAR_POSITIONAL:
            scargs.extend(arg)
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            sckwargs.update(arg)
        args = args[1:]

    try:
        await subcommand.func(*scargs, **sckwargs)
    except TypeError as e:
        # probably bad number of command arguments

        tb = "".join(traceback.format_tb(e.__traceback__))
        log.error(f"Command error from {ctx.author}.\n{tb}{e.__class__.__name__}: {e}")
        raise CommandError(f"Invalid command.")


def create_command(cls_name):
    async def command_implementation(_: CommandCog, ctx, *args):
        await call_command(cls_name, ctx, *args)

    command_obj = discord.ext.commands.command(name=cls_name)(command_implementation)
    setattr(CommandCog, cls_name, command_obj)


def Cog(guild_local=True, guild_only=True, default_active=False, toggleable=True, data_type=None,
        default_settings=None):
    l = locals()

    if default_active == False and toggleable == False:
        raise UselessCogError(f"Cog cannot be off by default and non-toggleable - it will never be used.")

    if guild_local == False and default_settings is not None:
        raise UselessCogError(f"Settings are only supported on guild_local cogs. Use config.json for global options.")

    def wrapper(cls):
        if not guild_local and guild_only:
            log.warning(f"Registering {cls.__name__} as guild_only and not guild_local, but all that does "
                        f"is prevent the same global commands being used outside of a guild, and that probably "
                        f"isn't the intention.")
        cls_name = cls.__name__.lower()
        if cls_name in all_cog_types:
            raise StaticNameCollisionError(f"There is already a cog called {cls_name} registered!")

        for name, value in l.items():
            setattr(cls, name, value)

        all_cog_types[cls_name] = cls

        subcommands = get_subcommands(cls)
        if len(subcommands) != 0:
            create_command(cls_name)
        return cls

    return wrapper


def create_cog(cog_type):
    identifier = cog_type.__name__
    guild_id = parse_identifier(identifier)[1]

    kwargs = {}
    if cog_type.data_type is not None:
        kwargs["data"] = get_data(f"{__name__}.cog.{identifier}", lambda: cog_type.data_type())
    if cog_type.guild_local:
        kwargs["guild_id"] = guild_id
    if cog_type.default_settings is not None:
        kwargs["settings"] = create_settings(identifier, cog_type.default_settings, Bot.get_guild(guild_id))
    cog = cog_type(**kwargs)
    setattr(cog, "identifier", identifier)
    return cog


async def load_cog(cog_type, guild_id):
    if not cog_type.guild_local:
        guild_id = no_guild_id
    if cog_type.guild_local and guild_id == no_guild_id:
        raise InvalidArgumentsError(f"Can't load a guild_local cog on no_guild_id.")

    cog_type_name = cog_type.__name__.lower()
    identifier = get_identifier(cog_type_name, guild_id)
    if identifier in Bot.cogs:
        raise DynamicNameCollisionError(f"That cog is already active.")

    if guild_id == no_guild_id or guild_id in [g.id for g in Bot.guilds]:
        log.info(f"Loading {identifier}.")
        cog_type = all_cog_types[cog_type_name]

        new_cog_type = copy_class(cog_type, class_name=identifier)
        cog = create_cog(new_cog_type)
        setattr(cog, "active", True)
        Bot.add_cog(cog)

        data.active_cog_overrides[identifier] = True
    else:
        log.warning(f"Not loading {identifier} because we aren't in that guild.")


async def unload_cog(identifier):
    if identifier in Bot.cogs:
        log.info(f"Unloading {identifier}.")
        data.active_cog_overrides[identifier] = False

        cog = Bot.get_cog(identifier)
        cog.active = False
        del cog
        Bot.remove_cog(identifier)
    else:
        raise DynamicNameCollisionError("That cog is not active.")


def get_cogs_to_load(guild_id=None):
    cogs_to_load = get_default_cogs(guild_id)
    for identifier, enabled in data.active_cog_overrides.items():
        if enabled and identifier not in cogs_to_load:
            cogs_to_load.append(identifier)
        elif not enabled and identifier in cogs_to_load:
            cogs_to_load.remove(identifier)
    return cogs_to_load


class AliasCog:
    pass


def create_alias(alias, full_cmd):
    async def command_implementation(_: CommandCog, ctx, *args):
        prefix = await Bot.get_prefix(ctx.message)
        ctx.message.content = f"{prefix}{full_cmd} " + " ".join(args)
        await Bot.process_commands(ctx.message)

    command_obj = discord.ext.commands.command(name=alias)(command_implementation)
    setattr(AliasCog, alias, command_obj)


def setup_aliases():
    log.info(f"Initializing alias system")

    alias_directory = config["aliases"]  # alias -> command to interpret
    for alias, full_cmd in alias_directory.items():
        create_alias(alias, full_cmd)

    Bot.add_cog(AliasCog())


class CentralCog:
    @staticmethod
    async def on_guild_join(guild):
        cogs_to_load = get_cogs_to_load(guild.id)
        log.info(f"Bot joined guild {guild}. Loading the following cogs: {cogs_to_load}")
        for identifier in cogs_to_load:
            cog_type_name, guild_id = parse_identifier(identifier)
            cog_type = all_cog_types[cog_type_name]
            await load_cog(cog_type, guild_id)

    @staticmethod
    async def on_guild_remove(guild):
        log.info(f"Bot has left {guild} - disabling cogs.")
        guild_cogs = [cog.__name__ for cog in Bot.cogs if parse_identifier(cog.__name__)[1] == guild.id]
        for identifier in guild_cogs:
            await unload_cog(identifier)

            # Set data to true so we have a record of which cogs were active, in case the bot comes back
            data.active_cog_overrides[identifier] = True

    @staticmethod
    async def on_ready():
        if config["disable_help"]:
            Bot.remove_command("help")
        Bot.add_cog(CommandCog())

        cogs_to_load = get_cogs_to_load()
        log.info(f"Bot ready. Loading the following cogs: {cogs_to_load}")
        for identifier in cogs_to_load:
            cog_type_name, guild_id = parse_identifier(identifier)
            if cog_type_name not in all_cog_types:
                raise CogNotFoundError(
                    f"Could not find cog {cog_type_name}, but it's marked as active in the database.")
            cog_type = all_cog_types[cog_type_name]
            await load_cog(cog_type, guild_id)

        setup_aliases()

        start_timed_event_loop(Bot.loop)

    @staticmethod
    async def has_permission(ctx, cog_type):
        if not cog_type.toggleable:
            return False

        if cog_type.guild_local:
            return await check_permissions(ctx, {
                "manage_guild": True
            })
        else:
            return await check_permissions(ctx, {
                "is_owner": True
            })

    @discord.ext.commands.command()
    async def activate(self, ctx, cog_type_name: str):
        cog_type_name = cog_type_name.lower()
        if cog_type_name in all_cog_types:
            cog_type = all_cog_types[cog_type_name]
            if await self.has_permission(ctx, cog_type):
                await load_cog(cog_type, no_guild_id if ctx.guild is None else ctx.guild.id)
                await ctx.send(f"Loaded {cog_type_name}.")
            else:
                await ctx.send(f"You don't have permission to do that!")
        else:
            await ctx.send(f"Can't find a cog called {cog_type_name}.")

    @discord.ext.commands.command()
    async def deactivate(self, ctx, cog_type_name: str):
        cog_type_name = cog_type_name.lower()
        if cog_type_name in all_cog_types:
            cog_type = all_cog_types[cog_type_name]
            if await self.has_permission(ctx, cog_type):
                await unload_cog(get_identifier(cog_type_name, no_guild_id if ctx.guild is None else ctx.guild.id))
                await ctx.send(f"Unloaded {cog_type_name}.")
            else:
                await ctx.send(f"You don't have permission to do that!")
        else:
            await ctx.send(f"Can't find a cog called {cog_type_name}.")


central_cog = CentralCog()
Bot.add_cog(central_cog)

for forward_cog in forward_discord_py_cogs:
    forward_cog.__name__ = f"__forward_cog__{forward_cog.__name__}"
    Bot.add_cog(forward_cog(Bot))

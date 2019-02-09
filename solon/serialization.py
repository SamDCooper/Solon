import datetime
import discord
import re
import ast

from .core import SocratesStaticError
from .core import SocratesRuntimeError
from .core import is_emoji
from .core import timedelta_from_string
from .emoji import Emoji

__all__ = ["serialize", "deserialize", "Codex", "SerializedData", "converter", "SerializedList", "SerializedStructure",
           "SerializedDictionary"]


class SerializationError(SocratesRuntimeError):
    pass


class CodexException(SocratesRuntimeError):
    pass


class StaticCodexException(SocratesStaticError):
    pass


all_codices = {}


def type_to_key(serializable_cls):
    return type_name_to_key(serializable_cls.__name__)


def type_name_to_key(serializable_cls_name):
    return serializable_cls_name.lower()


def type_to_type_name(serializable_cls):
    key = type_to_key(serializable_cls)
    codex_cls = all_codices[key]
    return codex_cls.type_name


def type_name_to_null_value(serializable_cls_name):
    codex = get_codex(serializable_cls_name)
    if hasattr(codex, "null_value"):
        return codex.null_value()
    else:
        return None


def Codex(serializable_cls):
    def wrapper(codex_cls):
        key = type_to_key(serializable_cls)
        if key in all_codices:
            raise StaticCodexException(f"There is already a codex for {key}.")
        all_codices[key] = codex_cls
        if hasattr(codex_cls, "possible_types"):
            codex_cls.possible_types.append(serializable_cls)
        else:
            setattr(codex_cls, "possible_types", [serializable_cls])
        return codex_cls

    return wrapper


def get_codex(serializable_cls_name):
    key = type_name_to_key(serializable_cls_name)
    if key not in all_codices:
        raise CodexException(f"I don't recognise the type {serializable_cls_name}.")
    return all_codices[key]


class SerializedData:
    def __init__(self, *, value_serialized, type_name):
        self.value_serialized = value_serialized
        self.type_name = type_name

    @property
    def as_pair(self):
        return {"value_serialized": self.value_serialized, "type_name": self.type_name}

    def __str__(self):
        return str(self.as_pair)


def serialize(x_data, type_name) -> SerializedData:
    if x_data is not None:
        codex = get_codex(type_name)
        value_serialized = codex.codex_serialize(x_data)
    else:
        value_serialized = ""
    return SerializedData(value_serialized=value_serialized, type_name=type_name)


def deserialize(serialized_data: SerializedData, guild: discord.Guild):
    if serialized_data.value_serialized == "":
        return type_name_to_null_value(serialized_data.type_name)

    codex = get_codex(serialized_data.type_name)
    return codex.codex_deserialize(serialized_data, guild)


def converter(serializable_cls):
    key = type_to_key(serializable_cls)
    if key not in all_codices:
        raise StaticCodexException(f"There is already a codex for {key}.")

    class AsConverter(discord.ext.commands.Converter):
        async def convert(self, ctx, arg: str):
            serialized_data = SerializedData(type_name=serializable_cls.__name__, value_serialized=arg)
            return deserialize(serialized_data, ctx.guild)

    return AsConverter


serialized_list_types = {}


def is_serialized_list(v):
    return v in serialized_list_types.values()


def SerializedList(element_cls):
    key = f"{element_cls.__name__}List"
    if key in serialized_list_types:
        return serialized_list_types[key]

    class SerializedListType(list):
        element_class = element_cls
        element_type_name = type_to_type_name(element_cls)

        def __setitem__(self, key, value):
            if value.__class__ == element_cls:
                super(SerializedListType, self).__setitem__(key, value)
            else:
                raise SerializationError(f"Item {value} is not of type {element_cls.__name__}.")

        def __str__(self):
            return ", ".join([str(v) if "," not in str(v) else f"'{v}'" for v in self]) if self else "<empty>"

    SerializedListType.__name__ = key

    class SerializedListCodex:
        type_name = key

        @classmethod
        def null_value(cls):
            return SerializedListType()

        @classmethod
        def codex_serialize(cls, x_data):
            list_of_serialized = []
            for element in x_data:
                list_of_serialized.append(serialize(element, type_to_type_name(element_cls)).value_serialized)

            return str(list_of_serialized)

        @classmethod
        def codex_deserialize(cls, serialized_data, guild):
            value_serialized = serialized_data.value_serialized

            # First we try the type we serialize to - a list of serialized values
            try:
                return cls.deserialize_list_of_serialized(ast.literal_eval(value_serialized), guild)
            except Exception:
                pass

            # If it's not that then we try it as a single element list holding the whole value
            try:
                return cls.deserialize_list_of_serialized([value_serialized], guild)
            except Exception:
                pass

            # If it's not that then we split it by spaces and try that
            try:
                return cls.deserialize_list_of_serialized(value_serialized.split(), guild)
            except Exception:
                pass

            # If it's not that then we're out of luck and the serialized data is malformed
            raise SerializationError("I don't recognise the format of this list.")

        @classmethod
        def deserialize_list_of_serialized(cls, list_of_serialized, guild):
            deserialized_list = SerializedListType()
            for element_serialized in list_of_serialized:
                element_sd = SerializedData(value_serialized=element_serialized,
                                            type_name=type_to_type_name(element_cls))
                deserialized_list.append(deserialize(element_sd, guild))

            return deserialized_list

    Codex(SerializedListType)(SerializedListCodex)

    serialized_list_types[key] = SerializedListType
    return SerializedListType


serialized_dictionary_types = {}


def is_serialized_dictionary(v):
    return v.__class__ in serialized_dictionary_types.values()


def SerializedDictionary(key_element_cls, value_element_cls):
    key = f"{key_element_cls.__name__}_to_{value_element_cls.__name__}"
    if key in serialized_dictionary_types:
        return serialized_dictionary_types[key]

    class SerializedDictionaryType(dict):
        key_element_class = key_element_cls
        value_element_class = value_element_cls

        def __setitem__(self, key, value):
            if key.__class__ != key_element_cls:
                raise SerializationError(f"Key {key} is not of type {key_element_cls.__name__}")
            if value.__class__ != value_element_cls:
                raise SerializationError(f"Value {value} is not of type {value_element_cls.__name__}")
            super(SerializedDictionaryType, self).__setitem__(key, value)

        def __str__(self):
            return ", ".join(f"{k}={v}" for k, v in sorted(self.items(), key=lambda kv: kv[0]))

    SerializedDictionaryType.__name__ = key

    class SerializedDictionaryCodex:
        type_name = key

        @classmethod
        def null_value(cls):
            return SerializedDictionaryType()

        @classmethod
        def codex_serialize(cls, x_data):
            dict_of_serialized = {}
            key_type_name = type_to_type_name(key_element_cls)
            value_type_name = type_to_type_name(value_element_cls)
            for k, v in x_data.items():
                k_value_serialized = serialize(k, key_type_name).value_serialized
                v_value_serialized = serialize(v, value_type_name).value_serialized
                dict_of_serialized[k_value_serialized] = v_value_serialized
            return str(dict_of_serialized)

        @classmethod
        def codex_deserialize(cls, serialized_data, guild):
            value_serialized = serialized_data.value_serialized
            dict_of_serialized = ast.literal_eval(value_serialized)

            deserialized_dict = SerializedDictionaryType()
            for k_ser, v_ser in dict_of_serialized.items():
                k_sd = SerializedData(value_serialized=k_ser, type_name=type_to_type_name(key_element_cls))
                k_deser = deserialize(k_sd, guild)

                v_sd = SerializedData(value_serialized=v_ser, type_name=type_to_type_name(value_element_cls))
                v_deser = deserialize(v_sd, guild)

                deserialized_dict[k_deser] = v_deser

            return deserialized_dict

    Codex(SerializedDictionaryType)(SerializedDictionaryCodex)

    serialized_dictionary_types[key] = SerializedDictionaryType
    return SerializedDictionaryType


serialized_structure_types = {}


def is_serialized_structure(v):
    return v in serialized_structure_types.values()


def SerializedStructure(structure_name, default_settings):
    structure_name = structure_name.lower()

    if structure_name in serialized_structure_types:
        return serialized_structure_types[structure_name]

    class SerializedStructureType(dict):
        def __init__(self, guild):
            super(SerializedStructureType, self).__init__()
            for field_name, kwargs in default_settings.items():
                serialized_data = SerializedData(**kwargs)
                super(SerializedStructureType, self).__setitem__(field_name, deserialize(serialized_data, guild))

        def __setitem__(self, field_name, value):
            if field_name in default_settings:
                if (value is None) or (value.__class__.__name__.lower() == self.type_name_of(field_name).lower()):
                    super(SerializedStructureType, self).__setitem__(field_name, value)
                else:
                    raise SerializationError(f"Item {value} is not of type {self[field_name].__class__.__name__}.")
            else:
                raise SerializationError(f"No field called {field_name} in structure {structure_name}.")

        @property
        def field_names(self):
            return default_settings.keys()

        def type_name_of(self, field_name):
            return default_settings[field_name]["type_name"]

    SerializedStructureType.__name__ = structure_name

    class SerializedStructureCodex:
        type_name = structure_name

        @classmethod
        def codex_serialize(cls, x_data):
            dict_of_serialized = {}
            for field_name, kwargs in default_settings.items():
                if field_name not in x_data:
                    raise SerializationError(f"{structure_name} structures must have a {field_name} field.")
                field_value = x_data[field_name]
                field_value_serialized = serialize(field_value, kwargs["type_name"])
                dict_of_serialized[field_name] = field_value_serialized.value_serialized

            return str(dict_of_serialized)

        @classmethod
        def codex_deserialize(cls, serialized_data, guild):
            value_serialized = serialized_data.value_serialized
            try:
                dict_of_serialized = {k.strip().lower(): v.strip() for k, v in ast.literal_eval(value_serialized).items()}
            except Exception:
                raise SerializationError("Cannot parse this structure, please check your syntax.")

            deserialized_struct = SerializedStructureType(guild)
            for field_name, field_value_serialized in dict_of_serialized.items():
                type_name = default_settings[field_name]["type_name"]
                field_data_serialized = SerializedData(value_serialized=field_value_serialized, type_name=type_name)
                deserialized_struct[field_name] = deserialize(field_data_serialized, guild)

            return deserialized_struct

    Codex(SerializedStructureType)(SerializedStructureCodex)

    serialized_structure_types[structure_name] = SerializedStructureType
    return SerializedStructureType


@Codex(str)
class StringCodex:
    type_name = "str"

    @staticmethod
    def codex_serialize(x_data):
        return x_data

    @staticmethod
    def codex_deserialize(serialized_data, guild):
        return serialized_data.value_serialized


@Codex(int)
class IntCodex:
    type_name = "int"

    @staticmethod
    def codex_serialize(x_data):
        return str(x_data)

    @staticmethod
    def codex_deserialize(serialized_data, guild):
        base = 10
        if serialized_data.value_serialized.startswith("0x"):
            base = 16
        elif serialized_data.value_serialized.startswith("0b"):
            base = 2

        return int(serialized_data.value_serialized, base=base)


@Codex(float)
class FloatCodex:
    type_name = "float"

    @staticmethod
    def codex_serialize(x_data):
        return str(x_data)

    @staticmethod
    def codex_deserialize(serialized_data, guild):
        return float(serialized_data.value_serialized)


@Codex(bool)
class BoolCodex:
    type_name = "bool"

    @staticmethod
    def codex_serialize(x_data):
        return str(x_data)

    @staticmethod
    def codex_deserialize(serialized_data, guild):
        sv = serialized_data.value_serialized.lower()
        if sv == "true" or sv == "1":
            return True
        elif sv == "false" or sv == "0":
            return False
        else:
            raise CodexException(f"Cannot deserialize {sv} into a bool.")


id_regex = re.compile(r'([0-9]{15,21})$')


@Codex(discord.User)
@Codex(discord.Member)
class MemberCodex:
    type_name = "Member"

    @staticmethod
    def codex_serialize(x_data):
        return x_data.mention

    @staticmethod
    def codex_deserialize(serialized_data, guild):
        sv = serialized_data.value_serialized.lower()
        match = id_regex.match(sv) or re.match(r'<@!?([0-9]+)>$', sv)
        if match is not None:
            user_id = int(match.group(1))
            member = guild.get_member(user_id)
        else:
            # Not a mention, maybe it's the name of someone
            potential_discriminator = None
            member = None
            if len(sv) > 5 and sv[-5] == "#":
                potential_name, potential_discriminator = sv.split("#")
                if re.search(r'\d', potential_discriminator):
                    def pred(m):
                        return m.name.lower() == potential_name and m.discriminator == potential_discriminator

                    member = next((m for m in guild.members if pred(m)), None)

            if member is None:
                def pred(m):
                    return (m.nick and m.nick.lower()) == sv or m.name.lower() == sv

                member = next((m for m in guild.members if pred(m)), None)

        if member is None:
            raise CodexException(f"Cannot deserialize {sv} into a member.")
        return member


@Codex(discord.TextChannel)
@Codex(discord.VoiceChannel)
@Codex(discord.abc.GuildChannel)
@Codex(discord.CategoryChannel)
class ChannelCodex:
    type_name = "GuildChannel"

    @staticmethod
    def codex_serialize(x_data):
        return x_data.mention

    @staticmethod
    def codex_deserialize(serialized_data, guild):
        sv = serialized_data.value_serialized.lower()
        match = id_regex.match(sv) or re.match(r'<#!?([0-9]+)>$', sv)
        if match is not None:
            channel_id = int(match.group(1))
            channel = guild.get_channel(channel_id)
        else:
            # Not a mention
            channel = next((ch for ch in guild.channels if ch.name.lower() == sv), None)

        if channel is None:
            raise CodexException(f"Cannot deserialize {sv} into a channel.")
        return channel


@Codex(discord.Role)
class RoleCodex:
    type_name = "Role"

    @staticmethod
    def codex_serialize(x_data):
        return x_data.mention

    @staticmethod
    def codex_deserialize(serialized_data, guild):
        sv = serialized_data.value_serialized.lower()
        match = id_regex.match(sv) or re.match(r'<@&([0-9]+)>$', sv)
        if match is not None:
            channel_id = int(match.group(1))
            role = guild.get_role(channel_id)
        else:
            # Not a mention
            role = next((r for r in guild.roles if r.name.lower() == sv), None)

        if role is None:
            raise CodexException(f"Cannot deserialize {sv} into a role.")
        return role


@Codex(Emoji)
class EmojiCodex:
    type_name = "Emoji"

    @staticmethod
    def codex_serialize(x_data):
        return str(x_data)

    @staticmethod
    def codex_deserialize(serialized_data, guild):
        sv = serialized_data.value_serialized.lower()
        match = id_regex.match(sv) or re.match(r'<a?:[a-zA-Z0-9\_]+:([0-9]+)>$', sv)
        if match:
            emoji_id = int(match.group(1))
            dpy_emoji = next((e for e in guild.emojis if e.id == emoji_id), None)
            emoji = Emoji(guild_id=guild.id, name=dpy_emoji.name, id=emoji_id, animated=dpy_emoji.animated) if dpy_emoji else None

        elif is_emoji(sv):
            emoji = Emoji(name=sv)

        if emoji is None:
            raise CodexException(f"Cannot deserialize {sv} into an emoji. I only support custom emojis on this guild.")
        return emoji


@Codex(datetime.timedelta)
class TimeDeltaCodex:
    type_name = "timedelta"

    @staticmethod
    def codex_serialize(x_data):
        return f"{x_data.total_seconds()}s"

    @staticmethod
    def codex_deserialize(serialized_data, guild):
        return timedelta_from_string(serialized_data.value_serialized)

from .database import get_data
from .database import pre_save_all
from .serialization import SerializedData
from .serialization import SerializedStructure
from .serialization import deserialize
from .serialization import serialize
from .serialization import type_name_to_null_value
from .serialization import type_to_type_name
from .serialization import is_serialized_dictionary
from .core import get_bot
from .core import SocratesRuntimeError

__all__ = ["get_setting_value", "get_setting_field_names", "set_setting_value", "get_setting_type_name",
           "get_cogs_with_settings"]


class SettingsError(SocratesRuntimeError):
    pass


settings_structures = {}


def guild_from_identifier(identifier):
    return get_bot().get_guild(int(identifier.split(".")[1]))


def cog_type_name_from_identifier(identifier):
    return identifier.split(".")[0]


def create_settings(identifier, default_settings, guild):
    if identifier in settings_structures:
        return settings_structures[identifier]

    struct_name = f"{__name__}.{identifier}"

    struct = SerializedStructure(struct_name, default_settings)(guild)

    class Data:
        def __init__(self):
            self.serialized_struct = serialize(struct, struct_name).as_pair

    d = get_data(struct_name, lambda: Data())

    updated_settings_struct = deserialize(SerializedData(**d.serialized_struct), guild)

    settings_structures[identifier] = updated_settings_struct

    @pre_save_all
    def reserialize_settings():
        d.serialized_struct = serialize(updated_settings_struct, struct_name).as_pair

    return updated_settings_struct


def get_settings(identifier):
    if identifier not in settings_structures:
        raise SettingsError("Can't find a cog with that name - is it active on this server?")
    return settings_structures[identifier]


def get_setting_value(identifier, field_name):
    settings = get_settings(identifier)
    if field_name in settings:
        return settings[field_name]

    # could be a member of a dictionary
    if "." in field_name:
        base_field_name, subfield_name = field_name.split(".", 1)
        base_setting = get_setting_value(identifier, base_field_name)
        if is_serialized_dictionary(base_setting):
            guild = guild_from_identifier(identifier)
            serialized_data = SerializedData(value_serialized=subfield_name,
                                             type_name=type_to_type_name(base_setting.key_element_class))
            deserialized_subfield_name = deserialize(serialized_data, guild)

            setting_value = base_setting.get(deserialized_subfield_name, None)
            if setting_value is not None:
                return setting_value

    raise SettingsError("There is no field with that name.")


def get_setting_field_names(identifier):
    settings = get_settings(identifier)
    return settings.keys()


def get_setting_type_name(identifier, field_name):
    settings = get_settings(identifier)
    if field_name in settings:
        return settings.type_name_of(field_name)

    # could be a member of a dictionary
    if "." in field_name:
        base_field_name, subfield_name = field_name.split(".", 1)
        base_setting = get_setting_value(identifier, base_field_name)
        if is_serialized_dictionary(base_setting):
            return type_to_type_name(base_setting.value_element_class)

    raise SettingsError("There is no field with that name.")


def set_setting_value(identifier, field_name, value):
    settings = get_settings(identifier)
    set_to_null = (value is None)
    if value is None:
        value = type_name_to_null_value(get_setting_type_name(identifier, field_name))

    if field_name in settings:
        settings[field_name] = value
        return

    # could be a member of a dictionary
    if "." in field_name:
        base_field_name, subfield_name = field_name.split(".", 1)
        base_setting = get_setting_value(identifier, base_field_name)
        if is_serialized_dictionary(base_setting):
            guild = guild_from_identifier(identifier)
            serialized_data = SerializedData(value_serialized=subfield_name,
                                             type_name=type_to_type_name(base_setting.key_element_class))
            deserialized_subfield_name = deserialize(serialized_data, guild)

            if set_to_null:
                del base_setting[deserialized_subfield_name]
            else:
                base_setting[deserialized_subfield_name] = value
            return

    raise SettingsError("There is no field with that name.")


def get_cogs_with_settings(guild):
    ret = []
    for identifier in settings_structures:
        sguild = guild_from_identifier(identifier)
        if sguild.id == guild.id:
            cog = get_bot().get_cog(identifier)
            if cog is not None and (not hasattr(cog, "active") or cog.active):
                ret.append(cog_type_name_from_identifier(identifier))
    return ret

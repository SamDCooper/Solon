import discord
import logging

import unittest

import solon

log = logging.getLogger(__name__)

test_passed = False

config = solon.get_config("solon.tests")

class MyClient(discord.Client):
    def __init__(self, test_case):
        super().__init__()
        self.test_case = test_case

    async def on_ready(self):
        guild = self.get_guild(config["testing_guild_id"])
        self.test_case.assertTrue(guild is not None)
        if guild:
            sd = solon.SerializedData(
                value_serialized="@everyone",
                type_name="role"
            )

            role = solon.deserialize(serialized_data=sd, guild=guild)
            self.test_case.assertTrue(role is not None)

        await self.logout()


class TestDeserialization(unittest.TestCase):
    """Tests deserialization"""

    def test_deserialization(self):
        bot = MyClient(self)

        async def do_test():
            await bot.login(solon.get_config("token"))
            await bot.connect(reconnect=False)

        bot.loop.run_until_complete(do_test())


if __name__ == "__main__":
    unittest.main()

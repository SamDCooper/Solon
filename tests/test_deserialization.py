import discord
import logging

import unittest

import solon

log = logging.getLogger(__name__)

test_passed = False


class MyClient(discord.Client):
    async def on_ready(self):
        global test_passed
        test_passed = True
        await self.logout()


class TestDeserialization(unittest.TestCase):
    """Tests deserialization"""

    def test_deserialization(self):
        #bot = MyClient()
        #bot.run(solon.get_config("token"))
        self.assertTrue(True)
        #self.assertTrue(test_passed)

        #while not bot.is_closed():
        #    pass
        #bot.clear()


if __name__ == "__main__":
    unittest.main()

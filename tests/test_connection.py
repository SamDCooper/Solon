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


class TestConnection(unittest.TestCase):
    """Tests connection"""

    def test_connection(self):
        bot = MyClient()

        async def do_test():
            await bot.login(solon.get_config("token"))
            await bot.connect(reconnect=False)
            self.assertTrue(test_passed)

        bot.loop.run_until_complete(do_test())


if __name__ == "__main__":
    unittest.main()

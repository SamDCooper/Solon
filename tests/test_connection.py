import logging
logging.basicConfig(level=logging.DEBUG)

import unittest

import solon

from discord.ext.commands import Bot

class TestConnection(unittest.TestCase):
    """Tests basic connection ability"""

    def test_can_connect(self):
        prefix = "?"
        bot = Bot(command_prefix=prefix)
        bot.run(solon.get_config("token"))
        self.assertTrue(False)


if __name__ == "__main__":
    unittest.main()

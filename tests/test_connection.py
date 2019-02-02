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
        bot.run("NTQxMzQxNTE3Nzc2OTQ1MTYy.DzeDGw.qLpReWeYDZQ4chR02XuUUmFB8fs")
        self.assertTrue(False)


if __name__ == "__main__":
    unittest.main()

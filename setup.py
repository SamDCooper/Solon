import setuptools

setuptools.setup(
    name="Solon",
    version="0.0.11",
    description="discord.py wrapper for bot creation",
    author="Falsely True Bots",
    author_email="FalselyTrueBots@users.noreply.github.com",
    url="https://github.com/FalselyTrueBots",
    packages=["solon"],
    install_requires=[
        "discord.py @ git+ssh://git@github.com/Rapptz/discord.py@4ef0fb0d959b69d3b2cea87b0fc08310028e348f#egg=discord.py-1.3.0a",
        "emoji"
    ]
)

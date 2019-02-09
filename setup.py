import setuptools

setuptools.setup(
    name="Solon",
    version="0.0.3",
    description="discord.py wrapper for bot creation",
    author="Falsely True Bots",
    author_email="FalselyTrueBots@users.noreply.github.com",
    url="https://github.com/FalselyTrueBots",
    packages=["solon"],
    install_requires=[
        "discord.py @ git+ssh://git@github.com/Rapptz/discord.py@1222bce271cf736b4db8c1eecb2823edd22f85dc#egg=discord.py-1.0.0a",
        "emoji"
    ]
)

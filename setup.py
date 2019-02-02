import setuptools

setuptools.setup(
    name="Solon",
    version="0.0.1",
    description="discord.py wrapper for bot creation",
    author="Falsely True Bots",
    author_email="FalselyTrueBots@users.noreply.github.com",
    url="https://github.com/FalselyTrueBots",
    packages=["solon"],
    dependency_links=["git+ssh://git@github.com/Rapptz/discord.py.git@1222bce271cf736b4db8c1eecb2823edd22f85dc#egg=discord.py"]
    )

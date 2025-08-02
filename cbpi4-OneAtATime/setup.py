from setuptools import setup

setup(
    name="cbpi4-OneAtATime",
    version="1.0.0",
    description="CraftBeerPi Plugin to safely control high power outputs. It can run on its own, or also alongside cbpi4-BMT-Key to be enabled/disabled",
    author="Andrew Laister",
    author_email="brewmotron@andrewlaister.com",
    maintainer="Brewmotron Project",
    url="https://github.com/MrLaister/brewmotron",
    license="GPLv3",
    include_package_data=True,
    package_data={
        # If any package contains *.txt or *.rst files, include them:
        "": ["*.txt", "*.rst", "*.yaml"],
        "cbpi4-OneAtATime": ["*", "*.txt", "*.rst", "*.yaml"],
    },
    packages=["cbpi4-OneAtATime"],
)

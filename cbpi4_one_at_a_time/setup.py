from setuptools import setup

setup(
    name="cbpi4-OneAtATime",
    version="1.0.0",
    description=("CraftBeerPi Plugin to safely control high power outputs. " "Can run standalone or with cbpi4-BMT-Key"),
    author="Andrew Laister",
    author_email="brewmotron@andrewlaister.com",
    maintainer="Brewmotron Project",
    url="https://github.com/MrLaister/brewmotron",
    license="GPLv3",
    include_package_data=True,
    package_data={
        # If any package contains *.txt or *.rst files, include them:
        "": ["*.txt", "*.rst", "*.yaml"],
        "cbpi4_one_at_a_time": ["*", "*.txt", "*.rst", "*.yaml"],
    },
    packages=["cbpi4_one_at_a_time"],
)

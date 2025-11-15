from setuptools import setup

setup(
    name="cbpi4-NOR3",
    version="0.0.3",
    description=("CraftBeerPi Plugin to integrate a 3-input NOR function. " "Under development"),
    author="Andrew Laister",
    author_email="brewmotron@andrewlaister.com",
    maintainer="Brewmotron Project",
    url="https://github.com/MrLaister/brewmotron",
    license="GPLv3",
    include_package_data=True,
    package_data={
        # If any package contains *.txt or *.rst files, include them:
        "": ["*.txt", "*.rst", "*.yaml"],
        "cbpi4-BMT-Key": ["*", "*.txt", "*.rst", "*.yaml"],
    },
    packages=["cbpi4-NOR3"],
)

from setuptools import setup

setup(
    name="cbpi4-GPIOInput",
    version="0.0.1",
    description="CraftBeerPi4 Plugin",
    author="Andrew Laister",
    author_email="brewmotron@andrewlaister.com",
    maintainer="Brewmotron Project",
    url="https://github.com/MrLaister/brewmotron",
    license="GPLv3",
    include_package_data=True,
    package_data={
        # If any package contains *.txt or *.rst files, include them:
        "": ["*.txt", "*.rst", "*.yaml"],
        "cbpi4-GPIOInput": ["*", "*.txt", "*.rst", "*.yaml"],
    },
    packages=["cbpi4-GPIOInput"],
)

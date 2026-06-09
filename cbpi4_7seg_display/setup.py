from os import path

from setuptools import find_packages, setup

# read the contents of your README file
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="cbpi4-7SegDisplay",
    version="1.0.1",
    description=("CraftBeerPi4 7 Segment Display Plugin for Brewmotron; " "can be used for other brewing systems"),
    author="Andrew Laister",
    author_email="brewmotron@andrewlaister.com",
    maintainer="Brewmotron Project",
    url="https://github.com/MrLaister/brewmotron",
    license="GPLv3",
    include_package_data=True,
    package_data={
        # If any package contains *.txt or *.rst files, include them:
        "": ["*.txt", "*.rst", "*.yaml"],
        "cbpi4_7seg_display": ["*", "*.txt", "*.rst", "*.yaml"],
    },
    packages=["cbpi4_7seg_display"],
    install_requires=[
        "smbus2",
        "adafruit-blinka",
        "adafruit-circuitpython-ht16k33",
        "requests",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
)

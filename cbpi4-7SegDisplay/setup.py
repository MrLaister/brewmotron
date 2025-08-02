from setuptools import setup, find_packages
from os import path

# read the contents of your README file
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="cbpi4-7SegDisplay",
    version="1.0.1",
    description="CraftBeerPi4 7 Segment Display Plugin used by Brewmotron but can be used for other systems",
    author="Andrew Laister",
    author_email="brewmotron@andrewlaister.com",
    maintainer="Brewmotron Project",
    url="https://github.com/MrLaister/brewmotron",
    license="GPLv3",
    include_package_data=True,
    package_data={
        # If any package contains *.txt or *.rst files, include them:
        "": ["*.txt", "*.rst", "*.yaml"],
        "cbpi4-7SegDisplay": ["*", "*.txt", "*.rst", "*.yaml"],
    },
    # packages=['cbpi4-LCDisplay'],
    packages=find_packages(),
    install_requires=[
        "smbus2",
        "adafruit-blinka",
        "adafruit-circuitpython-ht16k33",
        "requests",
    ],
    long_description=long_description,
    long_description_content_type="text/markdown",
)

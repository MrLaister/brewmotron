from setuptools import setup

setup(
    name="cbpi4-InternetConnectedGPIO",
    version="0.0.1",
    description="CraftBeerPi4 Plugin to set the GPIO state based on if it can see the internet - e.g. Wi-Fi LED",
    author="Andrew Laister",
    author_email="brewmotron@andrewlaister.com",
    maintainer="Brewmotron Project",
    url="https://github.com/MrLaister/brewmotron",
    license="GPLv3",
    include_package_data=True,
    package_data={
        # If any package contains *.txt or *.rst files, include them:
        "": ["*.txt", "*.rst", "*.yaml"],
        "cbpi4-InternetConnectedGPIO": ["*", "*.txt", "*.rst", "*.yaml"],
    },
    packages=["cbpi4-InternetConnectedGPIO"],
)

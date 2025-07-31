from setuptools import setup

setup(name='cbpi4-BMT-Key',
      version='0.0.1',
      description='CraftBeerPi Plugin for BrewMoTron to integrate the Key Mode function. Under development. Also enables/disables cbpi4-OneAtATime Actors based on key state',
      author='Andrew Laister',
      author_email='brewmotron@andrewlaister.com',
      maintainer='Brewmotron Project',
      url='https://github.com/MrLaister/brewmotron',
      license='GPLv3',
      include_package_data=True,
      package_data={
        # If any package contains *.txt or *.rst files, include them:
      '': ['*.txt', '*.rst', '*.yaml'],
      'cbpi4-BMT-Key': ['*','*.txt', '*.rst', '*.yaml']},
      packages=['cbpi4-BMT-Key'],
     )
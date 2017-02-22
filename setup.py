#!/usr/bin/env python3
from distutils.core import setup
from os.path import dirname, join

VERSION = "0.0.1"

install_requires = [
    "aiohttp_jinja2",
    "ipgetter",
    "requests",
    "irc3",
    "markovify",
    "discord.py",
    "discord.py[voice]"
]

setup(
    name='roboto',
    version=VERSION,
    include_package_data=True,
    license="MIT",
    install_requires=install_requires,
    description=r'Discord/Twitch bot',
    author='Leigh MacDonald',
    author_email='leigh.macdonald@gmail.com',
    long_description=open(join(dirname(__file__), "README.rst")).read(),
    url='https://github.com/leighmacdonald/roboto',
    packages=['roboto'],
    scripts=['scripts/roboto_cli.py'],
    download_url='https://github.com/leighmacdonald/roboto/tarball/{}'.format(VERSION),
    keywords=[],
    classifiers=[
        "Environment :: Console",
        "Topic :: Utilities"
    ]
)

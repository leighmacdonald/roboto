import asyncio
from configparser import RawConfigParser
from os.path import abspath, join, dirname
import logging


class Config(dict):
    def get_bool(self, key, d=None):
        value = self.get(key, d)
        if value.lower() not in RawConfigParser.BOOLEAN_STATES:
            raise ValueError('Not a boolean: %s' % value)
        return RawConfigParser.BOOLEAN_STATES[value.lower()]

config = Config()

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

default_file_name = abspath(join(dirname(dirname(__file__)), "corpus.txt"))

loop = asyncio.get_event_loop()

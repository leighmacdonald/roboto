import asyncio
from os.path import abspath, join, dirname
import logging


config = {}

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

default_file_name = abspath(join(dirname(dirname(__file__)), "corpus.txt"))

loop = asyncio.get_event_loop()

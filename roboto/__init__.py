import asyncio
from os.path import abspath, join, dirname
import logging

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

default_file_name = abspath(join(dirname(dirname(__file__)), "corpus.txt"))

headers = {
    'User-Agent': 'Rotobot 1.0'
}

config = {}

loop = asyncio.get_event_loop()


class CommandDispatcher(object):
    @staticmethod
    def help():
        return "> " + " :100: ".join([
            "!rank {bnet}",
            "!stop",
            "!volume 0-100",
            "!talk",
            "!playlist",
            "!next"
        ])

    commands = help


async def parse_message(msg):
    from roboto import media
    from roboto import overwatch

    args = msg.split()
    if msg.startswith(text.add_cmd_prefix("talk")):
        if len(args) >= 2:
            v = " ".join(args[1:])
            t = model.make_sentence_with_start(v)
        else:
            t = model.make_sentence(tries=20)
        return "> {}".format(t) if t else None
    elif msg.startswith(text.add_cmd_prefix("rank")):
        if len(args) > 1:
            bnet = args[1].replace("#", "-")
        else:
            bnet = config.get("bnet_id")
        stats = await overwatch.get_player_stats(bnet)
        return "> {}: SR:{} LVL:{} W/L: {}/{} K/D: {}/{}".format(
            bnet, stats['rank'], stats['level'], stats['wins'],
            stats['losses'], stats['elims'], stats['deaths'])

    elif msg.startswith(text.add_cmd_prefix("stop")):
        media.music_stop(media.media_player)
        return
    elif msg.startswith(text.add_cmd_prefix("playlist")):
        return media.music_playlist_url()
    elif msg.startswith(text.add_cmd_prefix("vol")):
        if len(args) < 2:
            return "Must supply 1 argument: 0-100"
        else:
            try:
                val = int(args[1]) / 100.0
                media.music_set_vol(media.media_player, val)
            except TypeError:
                return "Invalid number. 0-100 accepted"
    elif msg.startswith(text.add_cmd_prefix("help")):
        return CommandDispatcher.help()
    elif msg.startswith(text.add_cmd_prefix("next")):
        if media.music_play_next(media.media_player):
            return "Now Playing: {}".format(media.now_playing)

from roboto import text
model = text.MarkovModel(default_file_name)


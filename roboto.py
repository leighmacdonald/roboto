# -*- coding: utf-8 -*-
import time
import asyncio
import logging
from operator import attrgetter
from os import listdir
from os.path import dirname, join, abspath, exists, isdir, sep, splitext
from urllib.parse import quote_plus, unquote_plus
import aiohttp
import aiohttp_jinja2
import jinja2
import markovify
import irc3
from aiohttp import web
from discord.enums import ChannelType
from irc3 import IrcBot
from irc3.utils import parse_config
import discord
import ipgetter

config = {}

voice_channel = None
now_playing = None
default_file_name = abspath(join(dirname(__file__), "corpus.txt"))

headers = {
    'User-Agent': 'Rotobot 1.0'
}

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

loop = asyncio.get_event_loop()

web_app = web.Application(loop=loop)

media_player = None


ext_ip = None


class MediaFile(object):
    def __init__(self, path):
        self.path = path

    def name(self):
        return self.path.split(sep)[-1]

    @property
    def is_dir(self):
        pcs = self.path.split(sep)
        return len(pcs) > 1

    @property
    def safe_path(self):
        return quote_plus(self.path)

valid_music_ext = {'.flac', '.mp3'}


def is_media_file(path):
    try:
        return splitext(path)[1].lower() in valid_music_ext
    except IndexError:
        return False


@aiohttp_jinja2.template('index.html')
async def handle_index(request):
    global media_player, now_playing
    files = []
    path = config.get('music_path', "")
    if exists(path) and isdir(path):
        for f in listdir(path):
            if isdir(join(path, f)):
                for f2 in listdir(join(path, f)):
                    if is_media_file(f2):
                        files.append(MediaFile(join(f, f2)))
            else:
                if is_media_file(f):
                    files.append(MediaFile(f))
        files.sort(key=attrgetter("path"))
    return {
        "entries": files,
        "now_playing": now_playing if media_player and media_player.is_playing() else None
    }


def play_file(channel, full_path):
    global media_player
    if media_player:
        media_player.stop()
    media_player = channel.create_ffmpeg_player(full_path, use_avconv=True)
    music_set_vol(media_player, 0.5)
    media_player.start()
    return True


def music_set_vol(player, vol):
    if player:
        player.volume = float(vol)


def music_stop(player):
    if player and player.is_playing():
        player.stop()
        return True
    return False


def music_playlist_url():
    return "http://{}:{}".format(ext_ip, config.get("http_port", 8080))


@aiohttp_jinja2.template('play.html')
async def handle_play(request):
    global voice_channel, now_playing
    v = unquote_plus(request.GET['path'])
    full_path = join(config.get("music_path"), v)
    if play_file(voice_channel, full_path):
        now_playing = v
    return {"file_name": v}


class MarkovModel(object):
    def __init__(self, log_file_name=default_file_name, state_size=2):
        self.data_fp = None
        self.log_file_name = log_file_name
        self.state_size = state_size
        self.model = None
        self.rebuild_chain()

    def rebuild_chain(self):
        print("Rebuilding chain...")
        if self.data_fp is not None:
            self.data_fp.close()
        try:
            with open(self.log_file_name) as data_fp:
                text = data_fp.read()
        except Exception:
            text = ""
        self.model = markovify.Text(text, state_size=self.state_size)
        self.data_fp = open(self.log_file_name, "a+")

    def make_sentence_with_start(self, start):
        return self.model.make_sentence_with_start(start)

    def make_sentence(self, tries=20):
        return self.model.make_sentence(tries=tries)

model = MarkovModel()

dc = discord.Client(loop=loop)


@dc.async_event
async def on_message(message):
    print(message)
    resp = await parse_message(message.content)
    if resp:
        await dc.send_message(message.channel, resp)


session = None

async def get_player_stats(battle_tag, region="us"):
    global headers
    url = u"https://owapi.net/api/v3/u/{}/stats".format(battle_tag)
    d = None
    async with aiohttp.get(url, headers=headers) as r:
        if r.status == 200:
            d = await r.json()
    if not d:
        return

    region_key = ""
    regions = {"kr", "eu", "us"}
    for kr in regions:
        try:
            d[kr]['stats']
        except (KeyError, TypeError):
            pass
        else:
            region_key = kr
            break

    try:
        l = d[region_key]['stats']['competitive']['overall_stats']['level']
        p = d[region_key]['stats']['competitive']['overall_stats']['prestige']
        level = l + (p * 100)
        comprank = d[region_key]['stats']['competitive']['overall_stats']['comprank']
        win_rate = d[region_key]['stats']['competitive']['overall_stats']['win_rate']
        wins = d[region_key]['stats']['competitive']['overall_stats']['wins']
        losses = d[region_key]['stats']['competitive']['overall_stats']['losses']
        elims = int(d[region_key]['stats']['competitive']['game_stats']['eliminations'])
        deaths = int(d[region_key]['stats']['competitive']['game_stats']['deaths'])
    except KeyError:
        level = 0
        comprank = 0
        win_rate = d[region_key]['stats']["quickplay"]['overall_stats']['win_rate']
        wins = d[region_key]['stats']["quickplay"]['overall_stats']['wins']
        losses = d[region_key]['stats']["quickplay"]['overall_stats']['losses']
        elims = int(d[region_key]['stats']["quickplay"]['game_stats']['eliminations'])
        deaths = int(d[region_key]['stats']["quickplay"]['game_stats']['deaths'])

    return {
        "rank": comprank,
        "win_rate": win_rate,
        "wins": wins,
        "losses": losses,
        "level": level,
        "elims": elims,
        "deaths": deaths
    }


def normalize(t):
    if t.startswith("!"):
        return False
    if "http" in t.lower():
        return False
    t = " ".join(t.strip().split(" "))
    if not t.endswith("."):
        t += "."
    if len(t) < 10:
        return False
    return t


def add_cmd_prefix(cmd):
    return "{}{}".format(config.get("cmd", "!"), cmd)


async def parse_message(msg):
    args = msg.split()
    if msg.startswith(add_cmd_prefix("talk")):
        if len(args) >= 2:
            v = " ".join(args[1:])
            t = model.make_sentence_with_start(v)
        else:
            t = model.make_sentence(tries=20)
        time.sleep(1)
        return "> {}".format(t) if t else None
    elif msg.startswith(add_cmd_prefix("rank")):
        if len(args) > 1:
            bnet = args[1].replace("#", "-")
        else:
            bnet = config.get("bnet_id")
        stats = await get_player_stats(bnet)
        return "> {}: SR:{} LVL:{} W/L: {}/{} K/D: {}/{}".format(
            bnet, stats['rank'], stats['level'], stats['wins'],
            stats['losses'], stats['elims'], stats['deaths'])

    elif msg.startswith(add_cmd_prefix("stop")):
        music_stop(media_player)
        return
    elif msg.startswith(add_cmd_prefix("playlist")):
        return music_playlist_url()
    elif msg.startswith(add_cmd_prefix("vol")):
        if len(args) < 2:
            return "Must supply 1 argument: 0-100"
        else:
            try:
                val = int(args[1]) / 100.0
                music_set_vol(media_player, val)
            except TypeError:
                return "Invalid number. 0-100 accepted"


@irc3.plugin
class MarkovPlugin(object):

    def __init__(self, bot):
        self.bot = bot
        self.input_lines = 0
        try:
            self.ignored = bot.config.ignored_users
        except AttributeError:
            self.ignored = []
        self.last_cmd_time = 0

    def record(self, sentence):
        norm_str = normalize(sentence)
        if norm_str:
            self.data_fp.write(norm_str + "\n")
            self.data_fp.flush()

    @irc3.event(irc3.rfc.PRIVMSG)
    async def parse_input(self, mask, target, data, event):
        if mask.nick.lower() in self.ignored:
            return
        msg = await parse_message(data)
        if msg:
            self.bot.privmsg(target, msg)
        else:
            self.record(data)
            self.input_lines += 1
            if self.input_lines % 5 == 0:
                model.rebuild_chain()
            print(target, mask, data)


@dc.event
async def on_ready():
    global media_player, voice_channel
    print("logged in: {}/{}".format(dc.user.name, dc.user.id))
    for channel in dc.get_all_channels():
        if channel.type == ChannelType.voice and channel.id in config.get("voice_channels", []):
            voice_channel = await dc.join_voice_channel(channel)
            print("Joined voice channel: {}".format(channel))


def main():

    global config, ext_ip

    ext_ip = ipgetter.myip()

    # Parse & load config file
    config = parse_config('bot', "config.ini")

    # Load IRC Bot
    irc_bot = IrcBot.from_config(config, loop=loop)
    irc_bot.run(forever=False)

    template_path = join(abspath(dirname(__file__)), 'templates')
    aiohttp_jinja2.setup(web_app, loader=jinja2.FileSystemLoader(template_path))
    # Configure & load HTTP Interface
    web_app.router.add_get("/", handle_index)
    web_app.router.add_get("/play", handle_play)

    http_server = loop.create_server(
        web_app.make_handler(),
        config.get("http_host", "localhost"),
        config.get("http_port", 8080),
        ssl=None,
        backlog=128
    )
    loop.run_until_complete(asyncio.gather(http_server, web_app.startup(), loop=loop))

    # Start discord client
    dc.run(config.get("discord_token"))


if __name__ == "__main__":
    main()

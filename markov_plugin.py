# -*- coding: utf-8 -*-
import time
from os.path import dirname, join, abspath

import aiohttp
import markovify
import irc3
from irc3 import IrcBot
from irc3.utils import parse_config
import discord
import asyncio
import logging


logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

loop = asyncio.get_event_loop()

config = {
    'loop': loop,
    'debug': True,
    'verbose': True,
    'raw': True,
    'includes': [''],
}

discord_client = discord.Client(loop=loop)

default_file_name = abspath(join(dirname(__file__), "corpus.txt"))

headers = {
    'User-Agent': 'Rotobot 1.0'
}

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


@irc3.plugin
class MarkovPlugin(object):

    def __init__(self, bot, log_file_name=default_file_name, state_size=2):
        self.log_file_name = log_file_name
        self.bot = bot
        self.data_fp = None
        self.model = None
        self.input_lines = 0
        self.ignored = ["boreasbot"]
        self.state_size = state_size
        self.last_cmd_time = 0
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

    def normalize(self, t):
        if t.startswith("!"):
            return False
        if "http" in t.lower():
            return False
        t = " ".join(t.strip().split(" "))
        if not t.endswith("."):
            t += "."
        if len(t) < 10:
            return False
        self.input_lines += 1
        if self.input_lines % 5 == 0:
            self.rebuild_chain()
        return t

    def record(self, sentence):
        norm_str = self.normalize(sentence)
        if norm_str:
            self.data_fp.write(norm_str + "\n")
            self.data_fp.flush()

    @irc3.event(irc3.rfc.PRIVMSG)
    async def parse_input(self, mask, target, data, event):
        if mask.nick.lower() in self.ignored:
            return
        args = data.split(" ")
        if data.startswith("~talk"):
            if len(args) >= 2:
                t = self.model.make_sentence_with_start(" ".join(args[1:]))
            else:
                t = self.model.make_short_sentence(140)
            time.sleep(1)
            if t:
                self.bot.privmsg(target, "> " + t)
            else:
                print("No results generated")
        elif data.startswith("~rank"):
            if len(args) > 1:
                bnet = args[1].replace("#", "-")
            else:
                bnet = "manOFsnow-1894"
            stats = await get_player_stats(bnet)
            self.bot.privmsg(target, "> {}: SR:{} LVL:{} W/L: {}/{} K/D: {}/{}".format(
                bnet, stats['rank'], stats['level'], stats['wins'],
                stats['losses'], stats['elims'], stats['deaths']))
        else:
            self.record(data)
            print(target, mask, data)


@discord_client.event
async def on_ready():
    print("logged in: {}/{}".format(discord_client.user.name, discord_client.user.id))
    for channel in discord_client.get_all_channels():
        print(channel)


def main():
    config.update(parse_config('bot', "config.ini"))
    chater = IrcBot.from_config(config)
    chater.run(forever=False)
    discord_client.run(config.get("discord_token"))


if __name__ == "__main__":
    main()

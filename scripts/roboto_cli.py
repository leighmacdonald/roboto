# -*- coding: utf-8 -*-
from irc3 import IrcBot
from irc3.utils import parse_config


def main():
    from roboto import http, loop, disc, config

    # Parse & load config file
    config.update(parse_config('bot', "config.ini"))

    # Load IRC Bot
    irc_bot = IrcBot.from_config(config, loop=loop)
    irc_bot.run(forever=False)

    http.setup()

    # Start discord client
    disc.dc.run(config.get("discord_token"))


if __name__ == "__main__":
    main()

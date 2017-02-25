# -*- coding: utf-8 -*-
import asyncio
from irc3 import IrcBot
from irc3.utils import parse_config


def main():
    from roboto import model, http, loop, disc, config, commands

    # Parse & load config file
    config.update(parse_config('bot', "config.ini"))

    # Connect & Init DB
    model.init_db(config)

    # Load IRC Bot
    irc_bot = IrcBot.from_config(config, loop=loop)
    irc_bot.run(forever=False)

    # HTTP Server for playlist
    http.setup()

    # Start background task queue processor
    asyncio.ensure_future(commands.dispatcher.task_consumer(), loop=loop)

    # Start discord client
    disc.dc.run(config.get("discord_token"))


if __name__ == "__main__":
    main()

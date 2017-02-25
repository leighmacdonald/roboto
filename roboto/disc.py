from logging import getLogger
import discord
from discord.enums import ChannelType
from roboto import commands
from roboto import loop, config


dc = discord.Client(loop=loop)

voice_channel = None

log = getLogger("discord")


@dc.async_event
async def on_message(message):
    task = commands.parse_message(message.content)
    if task:
        task.set_client_discord(dc)
        task.set_source(commands.TaskSource.discord)
        task.set_channel(message.channel.id)
        task.set_user(message.author.id)
        await commands.dispatcher.add_task(task)


@dc.event
async def on_ready():
    global voice_channel
    log.info("logged in: {}/{}".format(dc.user.name, dc.user.id))
    for channel in dc.get_all_channels():
        if channel.type == ChannelType.voice and channel.id in config.get("voice_channels", []):
            voice_channel = await dc.join_voice_channel(channel)
            log.info("Joined voice channel: {}".format(channel))



from logging import getLogger
import discord
from sqlalchemy.exc import DBAPIError

from roboto import commands, state
from roboto import loop
from roboto.model import Session, Server

dc = discord.Client(loop=loop)
log = getLogger("discord")


@dc.async_event
async def on_voice_state_update(before, after):
    session = Session()
    try:
        if after.voice_channel:
            voice_channel_id = after.voice_channel.id
        else:
            voice_channel_id = None
        server = Server.get(session, after.server.id)
        server.voice_channel_id = voice_channel_id
        session.commit()
    except DBAPIError:
        log.exception("Failed to update voice state")
        session.rollback()


@dc.async_event
async def on_channel_update(before, after):
    pass


@dc.async_event
async def on_message(message):
    task = commands.parse_message(message.content)
    if task:
        task.set_client_discord(dc)
        task.set_source(commands.TaskSource.discord)
        task.set_channel(message.channel.id)
        task.set_user(message.author.id)
        task.set_server_id(message.server.id)
        await commands.dispatcher.add_task(task)


@dc.event
async def on_ready():
    log.info("logged in: {}/{}".format(dc.user.name, dc.user.id))
    for channel in dc.get_all_channels():
        await state.servers.get_server(channel.server.id)



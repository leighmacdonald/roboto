from roboto import loop, config, parse_message
import discord
from discord.enums import ChannelType

dc = discord.Client(loop=loop)

voice_channel = None


@dc.async_event
async def on_message(message):
    resp = await parse_message(message.content)
    if resp:
        await dc.send_message(message.channel, resp)


@dc.event
async def on_ready():
    global voice_channel
    print("logged in: {}/{}".format(dc.user.name, dc.user.id))
    for channel in dc.get_all_channels():
        if channel.type == ChannelType.voice and channel.id in config.get("voice_channels", []):
            voice_channel = await dc.join_voice_channel(channel)
            print("Joined voice channel: {}".format(channel))



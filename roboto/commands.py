import asyncio
from enum import Enum
import discord
import irc3
from discord import ChannelType
from sqlalchemy import orm
from sqlalchemy.exc import DBAPIError
from roboto import config, loop, logger
from roboto import media
from roboto import overwatch
from roboto import text
from roboto.exc import ValidationError, InvalidArgument
from roboto.model import Session, User, UserMessage, TaskSource, log, Server


def parse_message(msg: str):
    """
    :return:
    :rtype: TaskState
    """
    args = msg.split()
    if not args:
        return
    cmd = Commands.find_command(args[0])
    if not cmd:
        return
    if cmd == Commands.record:
        # Special case for record since we want the complete string
        return TaskState(cmd, [msg])
    return TaskState(cmd, args[1:])


def helpstr(help_msg: str, num_args=None):
    """ Sets the help string shown to users using the help command for the decorated do_* methods

    :return:
    :rtype: callable
    """
    def tags_decorator(func):
        func.__num_args__ = num_args
        func.__help__ = help_msg
        return func
    return tags_decorator


class Commands(Enum):
    """
    Enum for all possible events/tasks that the system can handle
    """
    play = 1
    next = 2
    stop = 3
    vol = 4
    playlist = 5
    join_voice = 6
    now_playing = 7
    np = 8
    pl = 4
    talk = 10
    record = 11
    rank = 50
    yt = 51
    rebuild_markov = 80
    server_connect = 90
    help = 98
    unknown = 99

    @staticmethod
    def find_command(txt: str):
        """ Find the matching enum value from the txt value passed in, leading command prefixes are
        discarded for the matching.

        :param txt:
        :return:
        :rtype: Commands
        """
        if not txt:
            return None
        prefix = config.get("prefix", "!")
        if txt[0] == prefix:
            txt = txt[1:]
        for name, member in Commands.__members__.items():
            if name == txt.lower():
                return member
        return Commands.record


class TaskState(object):
    def __init__(self, command: Commands, args: list, server_id=None, source=None, channel=None, user=None,
                 client_twitch=None, client_discord=None):
        self.command = command
        self.args = args
        self.channel = channel
        self.source = source
        self._user = user
        self._client_twitch = client_twitch
        self._client_discord = client_discord
        self.server_id = server_id

    def set_source(self, cmd_source: TaskSource):
        self.source = cmd_source

    def set_channel(self, channel: str):
        self.channel = channel

    def set_user(self, user: str):
        self._user = user

    def is_valid(self) -> bool:
        return self.source and self.channel and self._user and self.command

    def set_client_twitch(self, client: irc3.IrcBot):
        if self._client_discord:
            raise ValidationError("Twitch client already set")
        self._client_twitch = client

    def set_client_discord(self, client: discord.Client):
        if self._client_twitch:
            raise ValidationError("Discord client already set")
        self._client_discord = client

    def get_user(self, session: orm.Session):
        if self.source == TaskSource.discord:
            return User.get(session, discord_id=self._user)
        elif self.source == TaskSource.twitch:
            return User.get(session, twitch_id=self._user)
        else:
            raise ValidationError("No _user value to search with")

    def get_client_discord(self) -> discord.Client:
        return self._client_discord

    def get_client_twitch(self) -> irc3.IrcBot:
        return self._client_twitch

    def set_server_id(self, server_id):
        self.server_id = server_id

    async def server(self):
        """

        :rtype: roboto.state.ServerState
        """
        return await state.servers.get_server(self.server_id)

    def __str__(self):
        return "Server: {} Cmd: {} Args: {}".format(self.server_id, self.command.name, self.args)


class CommandDispatcher(asyncio.Queue):
    """
    Central event hub where tasks get routed between users and requested services
    """

    def __init__(self, lop):
        super().__init__()
        self._loop = lop
        self._running = False

    async def task_consumer(self):
        """ Background coroutine that will consume the task queue and execute the
        appropriate method.

        :return:
        """
        self._running = True
        while self._running:
            try:
                task = await self.get()
            except asyncio.QueueEmpty:
                await asyncio.sleep(0.1)
            else:
                try:
                    await self.execute_task(task)
                except Exception as err:
                    log.exception("Error executing task")

    async def add_task(self, task: TaskState) -> None:
        log.info("Adding task: {}".format(task))
        await self.put(task)

    @classmethod
    def gen_help(cls, cmd_name=None, help_sep=" :100: ") -> str:
        prefix = config.get("prefix", "!")
        if cmd_name:
            try:
                cmd_name = cmd_name.name
            except AttributeError:
                pass
            if not cmd_name.startswith("do_"):
                cmd_name = "do_{}".format(cmd_name)
        resp = []
        for k, v in cls.__dict__.items():
            if k.startswith("do_"):
                if cmd_name and k != cmd_name:
                    continue
                try:
                    resp.append("{}{}: {}".format(prefix, k[3:], v.__help__))
                except AttributeError:
                    pass
        if len(resp) > 1:
            return help_sep.join(resp)
        return resp[0]

    async def execute_task(self, task: TaskState):
        print("Got task.. {}".format(task))
        try:
            fn = getattr(self, "do_{}".format(task.command.name))
        except AttributeError:
            logger.error("Got invalid/unimplemented task: {}".format(task.command))
        else:
            try:
                if fn.__num_args__ is not None:
                    if fn.__num_args__ != len(task.args):
                        raise InvalidArgument("Your arguments are invalid")
            except AttributeError:
                pass
            except InvalidArgument as err:
                return await self.do_help(task, error_str=str(err), cmd=task.command.name)
            await fn(task)

    @helpstr("Show the title of the currently playing song", num_args=0)
    async def do_now_playing(self, task: TaskState):
        try:
            await media.send_now_playing(task.server_id, task.channel)
        except AttributeError:
            await media.send_now_playing(task.server_id)

    do_np = do_now_playing

    @helpstr("Instruct the bot to join a voice channel", num_args=1)
    async def do_join_voice(self, task: TaskState):
        client = task.get_client_discord()
        channel = client.get_channel(task.args[0])
        # todo correct ???
        if not client.is_voice_connected(channel.server):
            await client.join_voice_channel(channel)

    @staticmethod
    async def do_server_connect(task: TaskState):
        from roboto.disc import dc
        session = Session()
        server_info = Server.get(session, task.server_id, create=True)
        try:
            server = await task.server()
            await asyncio.sleep(1)
            dsc_server = dc.get_server(task.server_id)
            await asyncio.sleep(1)
            for channel in dsc_server.channels:
                if channel.type == ChannelType.voice and channel.id == server_info.voice_channel_id:
                    vc = await dc.join_voice_channel(channel)
                    if channel.id != server_info.voice_channel_id:
                        server_info.voice_channel_id = channel.id
                    server.set_voice_channel(channel.id)
                    server.voice_client = vc
            server.markov_model.rebuild_chain(session)
            session.commit()
        except DBAPIError:
            log.exception("Exception during server connect event")
            session.rollback()
        except AttributeError:
            pass

    @helpstr("Generate a random sentence")
    async def do_talk(self, task: TaskState):
        server = await task.server()
        if len(task.args) >= 1:
            t = server.markov_model.make_sentence_with_start(" ".join(task.args))
        else:
            t = server.markov_model.make_sentence(tries=20)
        if not t:
            t = "Failed to generate message"
        return await self.send_message(task, t)

    @staticmethod
    async def do_record(task: TaskState) -> bool:
        if not task.args:
            return False
        session = Session()
        try:
            UserMessage.record(session, task.get_user(session), task.source,
                               task.server_id, task.channel, task.args[0])
            session.commit()
        except DBAPIError:
            session.rollback()
            log.exception("Failed to add new message")
            return False
        else:
            log.debug("Recorded message")
            return True

    @staticmethod
    async def send_message(task: TaskState, message: str) -> bool:
        if not message:
            return False
        if task.source == TaskSource.discord:
            disc = task.get_client_discord()
            channel = disc.get_channel(task.channel)
            await disc.send_message(channel, message)
        elif task.source == TaskSource.twitch:
            await task.get_client_twitch().privmsg(task.channel, message)
        else:
            log.debug(message)
        return True

    @helpstr("Return info about a overwatch bnet id, uses configured default if none supplied")
    async def do_rank(self, task: TaskState) -> bool:
        if len(task.args):
            bnet = task.args[0].replace("#", "-")
        else:
            bnet = config.get("bnet_id")
        stats = await overwatch.get_player_stats(bnet)
        if stats:
            msg = "{}: SR:{} LVL:{} W/L: {}/{} K/D: {}/{}".format(
                bnet, stats['rank'], stats['level'], stats['wins'],
                stats['losses'], stats['elims'], stats['deaths'])
        else:
            msg = "Error retrieving stats"
        return await self.send_message(task, msg)

    @helpstr("Stop the current song/audio stream")
    async def do_stop(self, task: TaskState):
        server = await state.servers.get_server(task.server_id)
        media.music_stop(server)

    @helpstr("Show the playlist link")
    async def do_playlist(self, task: TaskState):
        await self.send_message(task, media.music_playlist_url(task.server_id))

    @helpstr("Play a specific song by id", num_args=1)
    async def do_play(self, task: TaskState):
        server_state = await state.servers.get_server(task.server_id)
        if media.play_file(server_state, task.args[0]):
            await media.send_now_playing(task.server_id, task.channel)
        else:
            await self.send_message(task, "Failed to play song, invalid id?")

    @helpstr("0-200 Change the volume of the audio stream", num_args=1)
    async def do_vol(self, task: TaskState):
        server = await state.servers.get_server(task.server_id)
        media_player = server.get_media_player()
        if not media_player:
            return
        try:
            val = int(task.args[0]) / 100.0
        except TypeError:
            return "Invalid number. 0-100 accepted"
        else:
            media_player.volume = val

    async def do_help(self, task: TaskState, error_str=None, cmd=None):
        if cmd:
            task_name = cmd
        else:
            task_name = task.args[0] if task.args else None
        msg = self.gen_help(task_name)
        log.debug("MSG: {}", task)
        if error_str:
            msg = "{} [ERR: {}]".format(msg, error_str)
        await self.send_message(task, msg)

    @helpstr("Play the next song in the playlist/albun")
    async def do_next(self, task: TaskState):
        server_state = await state.servers.get_server(task.server_id)
        if media.play_next(server_state):
            await media.send_now_playing(task.server_id, task.channel)

    @helpstr("Play a youtube stream")
    async def do_yt(self, task: TaskState) -> bool:
        server_state = await state.servers.get_server(task.server_id)
        if task.args:
            url = task.args[0]
        else:
            return await self.send_message(task, "Must supply media URL from supported sites ( "
                                                 "https://rg3.github.io/youtube-dl/supportedsites.html "
                                                 ") Majority of common sites are supported ")
        if not text.valid_url(url):
            return await self.send_message(task, "Invalid URL")
        np = await media.play_youtube(server_state, url)
        if np:
            return await self.send_message(task, "Now Playing YT: {}".format(np))

dispatcher = CommandDispatcher(loop)

# cyclic fix
from roboto import state

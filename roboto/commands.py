import asyncio
from enum import Enum
import discord
import irc3
from sqlalchemy import orm
from sqlalchemy.exc import DBAPIError
from roboto import config, loop, logger
from roboto import media
from roboto import overwatch
from roboto import text
from roboto.exc import ValidationError
from roboto.model import Session, User, UserMessage, TaskSource, log


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


def helpstr(help_msg: str):
    """ Sets the help string shown to users using the help command for the decorated do_* methods

    :return:
    :rtype: callable
    """
    def tags_decorator(func):
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
    playlist = 4
    join_voice = 5
    pl = 4
    talk = 10
    record = 11
    rank = 50
    rebuild_markov = 4
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
            await fn(task)

    @helpstr("Instruct the bot to join a voice channel")
    async def do_join_voice(self, task: TaskState):
        if not task.args:
            return await self.send_message(task, self.gen_help(Commands.join_voice))
        client = task.get_client_discord()
        channel = client.get_channel(task.args[0])
        # todo correct ???
        if not client.is_voice_connected(channel.server):
            await client.join_voice_channel(channel)

    @staticmethod
    async def do_server_connect(task: TaskState):
        session = Session()
        try:
            server = await task.server()
            server.markov_model.rebuild_chain(session)
            session.commit()
        except DBAPIError:
            log.exception("Exception during server connect event")
            session.rollback()

    @helpstr("Generate a random sentence")
    async def do_talk(self, task: TaskState):
        server = await task.server()
        if len(task.args) >= 1:
            v = " ".join(task.args[1:])
            t = server.markov_model.make_sentence_with_start(v)
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
            UserMessage.record(session, task.get_user(session), task.source, task.server_id, task.channel, task.args[0])
            session.commit()
        except DBAPIError:
            session.rollback()
            log.exception("Failed to add new message")
            return False
        else:
            log.info("Recording message")
            return True

    @staticmethod
    async def send_message(task: TaskState, message: str) -> bool:
        if not message:
            return False
        if task.source == TaskSource.discord:
            channel = task._client_discord.get_channel(task.channel)
            await task._client_discord.send_message(channel, message)
        elif task.source == TaskSource.twitch:
            await task._client_twitch.privmsg(task.channel, message)
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
        media.music_stop(media.media_player)

    @helpstr("Show the playlist link")
    async def do_playlist(self, task: TaskState):
        await self.send_message(task, media.music_playlist_url())

    @helpstr("0-200 Change the volume of the audio stream")
    async def do_vol(self, task: TaskState):
        if not task.args:
            return "Must supply 1 argument: 0-100"
        else:
            try:
                val = int(task.args[0]) / 100.0
                media.music_set_vol(media.media_player, val)
            except TypeError:
                return "Invalid number. 0-100 accepted"

    async def do_help(self, task: TaskState):
        msg = self.gen_help(task.args[0] if task.args else None)
        log.debug("MSG: {}", task)
        await self.send_message(task, msg)

    async def do_next(self, task: TaskState):
        if media.music_play_next(media.media_player):
            return "Now Playing: {}".format(media.now_playing)

    async def do_yt(self, task: TaskState) -> bool:
        from roboto.disc import voice_channel
        if task.args:
            url = task.args[0]
        else:
            return await self.send_message(task, "Must supply media URL from supported sites ( "
                                                 "https://rg3.github.io/youtube-dl/supportedsites.html "
                                                 ") Majority of common sites are supported ")
        if not text.valid_url(url):
            return await self.send_message(task, "Invalid URL")
        if await media.play_youtube(voice_channel, url):
            return await self.send_message(task, "Now Playing YT: {}".format(media.now_playing))

dispatcher = CommandDispatcher(loop)

# cyclic fix
from roboto import state

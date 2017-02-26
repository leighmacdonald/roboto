import discord
from discord.voice_client import StreamPlayer
from roboto.commands import dispatcher, TaskState, Commands


class ServerState(object):

    def __init__(self, server_id):
        from roboto import text
        self.server_id = server_id
        self._voice_channel_id = None
        self._media_player = None
        self.markov_model = text.MarkovModel(server_id)
        self.ready_state = False

    async def on_connect(self):
        task = TaskState(Commands.server_connect, [], server_id=self.server_id)
        await dispatcher.add_task(task)
        self.ready_state = True

    def has_voice(self) -> bool:
        return self._voice_channel_id

    def set_voice_channel(self, channel_id: str):
        self._voice_channel_id = channel_id

    def set_active_media_player(self, media_player: StreamPlayer):
        self._media_player = media_player

    def get_voice_channel(self, client: discord.Client) -> discord.Channel:
        channel = client.get_channel(self._voice_channel_id)
        return channel


class ServerManager(object):
    def __init__(self):
        self._servers = dict()

    def __len__(self):
        return len([self._servers.keys()])

    async def get_server(self, server_id: str) -> ServerState:
        try:
            return self._servers[server_id]
        except KeyError:
            server = ServerState(server_id)
            if not server.ready_state:
                await server.on_connect()
            self._servers[server_id] = server
            return server


servers = ServerManager()



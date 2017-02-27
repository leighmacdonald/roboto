from functools import lru_cache
from operator import attrgetter
from os.path import sep, splitext, isdir, exists, join
from os import listdir
from urllib.parse import quote_plus
import ipgetter
from logging import getLogger

from discord import ChannelType

from roboto import config, disc

log = getLogger(__name__)

# Continue through the media list via incrementing media_idx


media_continuous = True


class MediaFile(object):
    def __init__(self, path, idx=0):
        self.path = path
        self.idx = idx

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


async def send_now_playing(server_id, channel_id=None):
    from roboto.state import servers
    server_state = await servers.get_server(server_id)
    title = find_song_path(server_state.song_id)
    if not title:
        log.warning("No title for now playing")
        return
    msg = "Now Playing: {}".format(title)
    chan = None
    if channel_id:
        chan = disc.dc.get_channel(channel_id)
    if chan:
        await disc.dc.send_message(chan, content=msg)
    else:
        if channel_id:
            log.warning("Failed to find requested channel for NP")
        server = disc.dc.get_server(server_id)
        for channel in server.channels:
            if not channel.type == ChannelType.voice:
                await disc.dc.send_message(channel, content=msg)
                break


def find_song_path(song_id, full=False):
    if not song_id:
        return None
    files = fetch_media_files()
    try:
        path = files[int(song_id)]
    except IndexError:
        return None
    else:
        if full:
            return join(config['music_path'], path.path)
        return path.path


@lru_cache(maxsize=None)
def fetch_media_files(path=None):
    """ Build a simple list of valid media files. This function assumes you have a shallow dir tree
    no deeper than 1 folder.

    :param path:
    :return: []MediaFile
    """
    if path is None:
        try:
            path = config["music_path"]
        except KeyError:
            return []
    files = []
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

        # Store index *after* sort process
        for idx, f in enumerate(files, start=0):
            f.song_id = idx
    return files


def after_media_handler(player):
    # try:
    #     if not player.server_state.media_continuous:
    #         return
    #
    #     from roboto.commands import TaskState, dispatcher, Commands
    #     task = TaskState(Commands.next, [], server_id=player.server_state.server_id)
    #     dispatcher.put_nowait(task)
    #
    # except Exception as err:
    #     log.exception("Media finalizer error")
    pass


def play_next(server_state):
    if server_state.song_id is not None:
        return play_file(server_state, server_state.song_id + 1)
    return False


def play_file(server_state, song_id: int):
    if not server_state.voice_client:
        return
    old_media_player = server_state.get_media_player()
    if old_media_player:
        old_media_player.is_playing()
        old_media_player.stop()
    avcon = config.get_bool("use_avcon", False)
    full_path = find_song_path(song_id, full=True)
    media_player = server_state.voice_client.create_ffmpeg_player(
        full_path, use_avconv=avcon, after=after_media_handler)
    media_player.volume = 1.0
    media_player.start()
    server_state.set_active_media_player(media_player)
    server_state.song_id = int(song_id)

    return True


def music_set_vol(player, vol):
    if player:
        player.volume = float(vol)


def music_stop(server):
    player = server.get_media_player()
    if player:
        if player.is_playing():
            player.stop()
        if player.is_alive():
            player.join(timeout=5)
            server.set_active_media_player(None)
        return True
    return False

ext_ip = None

async def play_youtube(server_state, url, volume=0.5):
    music_stop(server_state)
    media_player = await server_state.voice_client.create_ytdl_player(url, use_avconv=False)
    music_set_vol(media_player, volume)
    media_player.start()
    media_player.server_state = server_state
    return media_player.title


@lru_cache(maxsize=None)
def music_playlist_url(server_id):
    global ext_ip
    try:
        if not ext_ip:
            ext_ip = ipgetter.myip()
    except Exception:
        ext_ip = "0.0.0.0"
    return "http://{}:{}/{}".format(ext_ip, config.get("http_port", 8080), server_id)

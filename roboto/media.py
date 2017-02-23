from functools import lru_cache
from operator import attrgetter
from os.path import sep, splitext, isdir, exists, join
from os import listdir
from urllib.parse import quote_plus
import ipgetter
from roboto import config

# Active player instance
from roboto import disc

media_player = None

# Current index of active media file
media_idx = 0

# Continue through the media list via incrementing media_idx
media_continuous = True

# Current album/track
now_playing = None


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


async def send_now_playing():
    msg = "Now Playing: {}".format(now_playing)
    channel = disc.dc.get_channel(str(config.get("chat_channel")))
    await disc.dc.send_message(channel, content=msg)


@lru_cache(maxsize=None)
def fetch_media_files(path):
    """ Build a simple list of valid media files. This function assumes you have a shallow dir tree
    no deeper than 1 folder.

    :param path:
    :return: []MediaFile
    """
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
            f.idx = idx
    return files


def after_media_handler(player):
    music_stop(player)
    if not media_continuous:
        return
    music_play_next(player)


def music_play_next(player):
    global media_idx, now_playing
    from roboto.disc import voice_channel
    vol = player.volume if player else 0.5
    files = fetch_media_files(config.get("music_path"))
    media_idx += 1
    try:
        media_file = files[media_idx]
    except IndexError:
        return
    full_path = join(config.get("music_path"), media_file.path)
    if play_file(voice_channel, full_path, volume=vol):
        now_playing = media_file.path
        return True
    return False


def play_file(channel, full_path, volume=0.5):
    global media_player
    if not channel:
        return False
    music_stop(media_player)
    media_player = channel.create_ffmpeg_player(full_path, use_avconv=False, after=after_media_handler)
    music_set_vol(media_player, volume)
    media_player.start()
    return True


def music_set_vol(player, vol):
    if player:
        player.volume = float(vol)


def music_stop(player):
    if player:
        if player.is_playing():
            player.stop()
        if player.is_alive():
            r = player.join(timeout=5)
        return True
    del player
    return False

ext_ip = None

async def play_youtube(channel, url, volume=0.5):
    global media_player, now_playing
    music_stop(media_player)
    media_player = await channel.create_ytdl_player(url, use_avconv=False)
    music_set_vol(media_player, volume)
    media_player.start()
    now_playing = media_player.title
    return True


@lru_cache(maxsize=None)
def music_playlist_url():
    global ext_ip
    try:
        if not ext_ip:
            ext_ip = ipgetter.myip()
    except Exception:
        ext_ip = "0.0.0.0"
    return "http://{}:{}#{}".format(ext_ip, config.get("http_port", 8080), media_idx)

from urllib.parse import unquote_plus
import aiohttp_jinja2
import asyncio
import jinja2
from aiohttp import web
from os.path import join, abspath, dirname
from roboto import disc, media, config, loop

web_app = web.Application(loop=loop)


@aiohttp_jinja2.template('index.html')
async def handle_index(request):
    return {
        "entries": media.fetch_media_files(config.get("music_path")),
        "now_playing": media.now_playing if media.media_player and media.media_player.is_playing() else None,
        "current_idx": media.media_idx
    }


@aiohttp_jinja2.template('play.html')
async def handle_play(request):
    from roboto.disc import voice_channel
    if not voice_channel:
        return {"file_name": "Error..."}
    full_path = None
    idx = unquote_plus(request.GET['idx'])
    file_list = media.fetch_media_files(config.get("music_path"))
    try:
        fp = file_list[int(idx)]
    except Exception:
        pass
    else:
        full_path = join(config.get("music_path"), fp.path)
        if media.play_file(voice_channel, full_path):
            media.now_playing = fp.path
            await media.send_now_playing()
        media.media_idx = int(idx)
    return {"file_name": full_path, "current_idx": media.media_idx}


def setup():
    # Configure & load HTTP Interface
    template_path = join(abspath(dirname(__file__)), 'templates')
    aiohttp_jinja2.setup(web_app, loader=jinja2.FileSystemLoader(template_path))
    web_app.router.add_get("/", handle_index)
    web_app.router.add_get("/play", handle_play)
    http_server = loop.create_server(
        web_app.make_handler(),
        config.get("http_host", "localhost"),
        config.get("http_port", 8080),
        ssl=None,
        backlog=128
    )
    loop.run_until_complete(asyncio.gather(http_server, web_app.startup(), loop=loop))
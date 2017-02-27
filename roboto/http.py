import asyncio
from urllib.parse import unquote_plus
from os.path import join, abspath, dirname
import aiohttp_jinja2
import jinja2
from aiohttp import web
from roboto import disc, media, config, loop, state

web_app = web.Application(loop=loop)


@aiohttp_jinja2.template('index.html')
async def handle_index(request):
    server_id = request.match_info['server_id']
    server_state = await state.servers.get_server(server_id)
    return {
        "entries": media.fetch_media_files(config.get("music_path")),
        "now_playing": None,
        "current_song_id": server_state.song_id,
        "server_id": server_id
    }


@aiohttp_jinja2.template('play.html')
async def handle_play(request):
    full_path = None
    server_id = request.match_info['server_id']
    server = disc.dc.get_server(server_id)
    if not server:
        raise ValueError("Invalid server_id")
    song_id = unquote_plus(request.match_info['song_id'])
    server_state = await state.servers.get_server(server_id)
    if media.play_file(server_state, song_id):
        await media.send_now_playing(server_id)
    return {
        "file_name": full_path,
        "current_song_id": song_id,
        "server_id": request.match_info['server_id']
    }


def setup():
    # Configure & load HTTP Interface
    template_path = join(abspath(dirname(__file__)), 'templates')
    aiohttp_jinja2.setup(web_app, loader=jinja2.FileSystemLoader(template_path))
    web_app.router.add_get("/{server_id}", handle_index)
    web_app.router.add_get("/{server_id}/play/{song_id}", handle_play)
    http_server = loop.create_server(
        web_app.make_handler(),
        config.get("http_host", "localhost"),
        config.get("http_port", 8080),
        ssl=None,
        backlog=128
    )
    loop.run_until_complete(asyncio.gather(http_server, web_app.startup(), loop=loop))

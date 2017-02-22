import aiohttp
from roboto import headers


async def get_player_stats(battle_tag, region="us"):
    url = u"https://owapi.net/api/v3/u/{}/stats".format(battle_tag)
    d = None
    async with aiohttp.get(url, headers=headers) as r:
        if r.status == 200:
            d = await r.json()
    if not d:
        return

    region_key = ""
    regions = {"kr", "eu", "us"}
    if region.lower() not in regions:
        return {}
    for kr in regions:
        try:
            d[kr]['stats']
        except (KeyError, TypeError):
            pass
        else:
            region_key = kr
            break

    try:
        l = d[region_key]['stats']['competitive']['overall_stats']['level']
        p = d[region_key]['stats']['competitive']['overall_stats']['prestige']
        level = l + (p * 100)
        comprank = d[region_key]['stats']['competitive']['overall_stats']['comprank']
        win_rate = d[region_key]['stats']['competitive']['overall_stats']['win_rate']
        wins = d[region_key]['stats']['competitive']['overall_stats']['wins']
        losses = d[region_key]['stats']['competitive']['overall_stats']['losses']
        elims = int(d[region_key]['stats']['competitive']['game_stats']['eliminations'])
        deaths = int(d[region_key]['stats']['competitive']['game_stats']['deaths'])
    except KeyError:
        level = 0
        comprank = 0
        win_rate = d[region_key]['stats']["quickplay"]['overall_stats']['win_rate']
        wins = d[region_key]['stats']["quickplay"]['overall_stats']['wins']
        losses = d[region_key]['stats']["quickplay"]['overall_stats']['losses']
        elims = int(d[region_key]['stats']["quickplay"]['game_stats']['eliminations'])
        deaths = int(d[region_key]['stats']["quickplay"]['game_stats']['deaths'])

    return {
        "rank": comprank,
        "win_rate": win_rate,
        "wins": wins,
        "losses": losses,
        "level": level,
        "elims": elims,
        "deaths": deaths
    }
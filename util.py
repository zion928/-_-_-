import os
from typing import List, Tuple
from collections import Counter, defaultdict
import requests
from riotwatcher import LolWatcher

RIOT_API_KEY = os.environ.get('RIOT_API_KEY')

lol_watcher = LolWatcher(RIOT_API_KEY)

async def get_most_played_champion(lol_watcher, summoner_puuid, region):
# Get recent match history
    match_history = await lol_watcher.match_v5.matchlist_by_puuid(region, summoner_puuid)
    champion_play_count = defaultdict(int)
    for match in match_history[:min(10, len(match_history))]:
        match_detail = await lol_watcher.match_v5.by_id(region, match)
        for participant in match_detail['info']['participants']:
            if participant['puuid'] == summoner_puuid:
                champion_play_count[participant['championId']] += 1
                break

    most_played_champ_id = max(champion_play_count, key=champion_play_count.get)

    # Get champion name
    champion_data = await lol_watcher.data_dragon.champions(latest_version)
    most_played_champ = champion_data['data'][str(most_played_champ_id)]['name']

    return most_played_champ
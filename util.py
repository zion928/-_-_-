import requests
from riotwatcher import LolWatcher, ApiError
from bs4 import BeautifulSoup
from typing import List, Dict, Union, Optional
import itertools
import random
from LMBlearn import create_team_evaluator, train_team_evaluator, evaluate_teams

recent_teams = []

def find_recent_teams() -> List[List[Dict[str, Union[str, int]]]]:
    return recent_teams[-1]

def teams_to_input_vector(teams: List[List[Dict[str, Union[str, int]]]]) -> np.ndarray:
    input_vector = []
    
    for team in teams:
        for summoner in team:
            input_vector.append(summoner['mmr'])
            # 각 소환사의 선호 포지션은 다음과 같이 벡터로 나타낼 수 있습니다.
            # [Top, Jungle, Mid, ADC, Support]
            input_vector.extend(summoner['preferred_position'])
    
    return np.array(input_vector)

def get_summoner_info(summoner_name: str, api_key: str) -> Union[Dict, None]:
    summoner_name = summoner_name.replace(" ", "")
    try:
        lol_watcher = LolWatcher(api_key)
        region = 'kr'
        summoner = lol_watcher.summoner.by_name(region, summoner_name)

        # 솔로랭크 정보를 가져옵니다.
        ranked_stats = lol_watcher.league.by_summoner(region, summoner['id'])
        solo_ranked_stats = next((q for q in ranked_stats if q['queueType'] == 'RANKED_SOLO_5x5'), None)

        # 솔로랭크 정보가 있다면 MMR을 계산합니다.
        if solo_ranked_stats is not None:
            mmr = tier_rank_to_value(solo_ranked_stats['tier'], solo_ranked_stats['rank'])
        else:
            # 솔로랭크 정보가 없다면 자유랭크 정보를 가져옵니다.
            ranked_stats = lol_watcher.league.by_summoner(region, summoner['id'], "RANKED_FLEX_SR")
            flex_ranked_stats = next((q for q in ranked_stats if q['queueType'] == 'RANKED_FLEX_SR'), None)
            if flex_ranked_stats is not None:
                mmr = tier_rank_to_value(flex_ranked_stats['tier'], flex_ranked_stats['rank'])
            else:
                # 자유랭크 정보가 없다면 일반게임 MMR을 계산합니다.
                normal_game_stats = lol_watcher.league.by_summoner(region, summoner['id'], 'RANKED_FLEX_SR')
                normal_game_mmr = get_normal_game_mmr(normal_game_stats)
                if normal_game_mmr is None:
                    # 일반게임 정보도 없다면 None을 반환합니다.
                    return None
                else:
                    mmr = normal_game_mmr

        opgg_url = f"https://www.op.gg/summoner/userName={summoner_name}"

        summoner_info = {
            "name": summoner['name'],
            "level": summoner['summonerLevel'],
            "tier": solo_ranked_stats['tier'] if solo_ranked_stats is not None else None,
            "rank": solo_ranked_stats['rank'] if solo_ranked_stats is not None else None,
            "mmr": mmr,
            "opgg_url": opgg_url,
        }

        return summoner_info
    except ApiError as err:
        if err.response.status_code == 429:
            print('We should retry in {} seconds.'.format(err.headers['Retry-After']))
        elif err.response.status_code == 404:
            print('Summoner not found.')
        else:
            raise

def get_ranked_stats(lol_watcher: LolWatcher, region: str, summoner_id: str) -> tuple[str, Optional[int]]:
    ranks = lol_watcher.league.by_summoner(region, summoner_id)
    for rank in ranks:
        if rank['queueType'] == 'RANKED_SOLO_5x5':
            return rank['tier'], rank.get('rank')
    return 'UNRANKED', None

def balance_teams(summoners_list: List[Dict[str, Union[str, int]]]) -> List[List[Dict[str, Union[str, int]]]]:
    num_teams = len(summoners_list) // 5
    sorted_summoners = sorted(summoners_list, key=lambda x: tier_rank_to_value(x['tier'], x['rank']), reverse=True)
    teams = [[] for _ in range(num_teams)]

    for i, summoner in enumerate(sorted_summoners):
        teams[i % num_teams].append(summoner)

    return teams

def tier_rank_to_value(tier: str, rank: Union[int, None]) -> int:
    tier_values = {
        "IRON": 0,
        "BRONZE": 700,
        "SILVER": 1500,
        "GOLD": 2500,
        "PLATINUM": 4000,
        "DIAMOND": 6000,
        "MASTER": 7000,
        "GRANDMASTER": 7250,
        "CHALLENGER": 7500,
    }
    rank_values = {
        "IV": 4,
        "III": 3,
        "II": 2,
        "I": 1
    }
    if tier in tier_values:
        if rank:
            return tier_values[tier] + rank_values[rank] * 100
        else:
            return tier_values[tier]
    else:
        return 0

def get_normal_game_mmr(summoner_name: str) -> Optional[int]:
    # op.gg에서 소환사 정보를 가져오는 요청을 보냅니다.
    response = requests.get(f"https://www.op.gg/summoner/userName={summoner_name}")
    soup = BeautifulSoup(response.text, 'html.parser')

    # 최근 20판의 일반 게임 데이터를 가져옵니다.
    game_data = soup.select('.GameItemList .GameItemWrap')[:20]

    # 일반 게임 전적이 없는 경우 None을 반환합니다.
    if not game_data:
        return None

    # 각 게임의 평균 MMR을 계산합니다.
    mmr_sum = 0
    for game in game_data:
        tier, rank = game.select_one('.TierRank').text.split()
        rank_value = {'IV': 0, 'III': 1, 'II': 2, 'I': 3}[rank]
        tier_values = {
            'IRON': 0,
            'BRONZE': 700,
            'SILVER': 1500,
            'GOLD': 2500,
            'PLATINUM': 4000,
            'DIAMOND': 6000,
            'MASTER': 7000,
            'GRANDMASTER': 7250,
            'CHALLENGER': 7500,
        }
        mmr_sum += tier_values[tier] + rank_value * 100 + 50

    # 평균 MMR을 계산합니다.
    mmr = mmr_sum // len(game_data)

    return mmr

def get_average_tier(tiers: List[str], ranks: List[str]) -> str:
    total_value = 0
    num_summoners = len(tiers)
    for tier, rank in zip(tiers, ranks):
        total_value += tier_rank_to_value(tier, rank)

    average_value = total_value // num_summoners
    average_tier, average_rank = value_to_tier_rank(average_value)

    return f"{average_tier} {average_rank}"

def get_max_tier_and_rank(tiers: List[str], ranks: List[str]) -> tuple[str, str]:
    max_value = -1
    max_tier = ""
    max_rank = ""

    for tier, rank in zip(tiers, ranks):
        value = tier_rank_to_value(tier, rank)
        if value > max_value:
            max_value = value
            max_tier = tier
            max_rank = rank

    return max_tier, max_rank

def value_to_tier_rank(value: int) -> str:
    # 각 티어의 값 범위를 딕셔너리로 정의합니다.
    tier_values = {
        'IRON': (0, 699),
        'BRONZE': (700, 1499),
        'SILVER': (1500, 2499),
        'GOLD': (2500, 3999),
        'PLATINUM': (4000, 5999),
        'DIAMOND': (6000, 6999),
        'MASTER': (7000, 7249),
        'GRANDMASTER': (7250, 7499),
        'CHALLENGER': (7500, float('inf')),
    }

    # 주어진 값에 해당하는 티어와 랭크를 찾습니다.
    for tier, value_range in tier_values.items():
        if value_range[0] <= value <= value_range[1]:
            rank_value = (value - value_range[0]) // 100
            rank = {0: 'IV', 1: 'III', 2: 'II', 3: 'I'}.get(rank_value, '')
            return f"{tier} {rank}"
    return ""
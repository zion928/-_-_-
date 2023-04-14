import requests
from riotwatcher import LolWatcher, ApiError
from bs4 import BeautifulSoup
from typing import List, Dict, Union, Optional

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
    sorted_summoners = sorted(
        summoners_list, key=lambda summoner: tier_rank_to_value(summoner["tier"], summoner["rank"]), reverse=True
    )
    
    num_teams = 2  # Change this to the desired number of teams
    teams = [[] for _ in range(num_teams)]

    for idx, summoner in enumerate(sorted_summoners):
        teams[idx % num_teams].append(summoner)

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

def get_average_tier(tiers: List[str]) -> str:
    # 각 티어의 값을 리스트로 변환합니다.
    values = [tier_rank_to_value(tier, "IV") for tier in tiers]
    
    # 평균 값을 계산합니다.
    avg_value = sum(values) / len(values)
    
    # 평균 값에 해당하는 티어와 랭크를 반환합니다.
    return value_to_tier_rank(int(avg_value))

def get_max_tier_and_rank(tiers: List[str], ranks: List[str]) -> tuple[str, str, int]:
    max_value = -1
    max_tier = ""
    max_rank = ""
    max_score = 0

    for tier, rank in zip(tiers, ranks):
        value = tier_rank_to_value(tier, rank)
        if value > max_value:
            max_value = value
            max_tier = tier
            max_rank = rank
            max_score = value

    return max_tier, max_rank, max_score

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
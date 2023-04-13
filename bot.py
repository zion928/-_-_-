import discord
import os
import random
from discord.ext import commands
from riotwatcher import LolWatcher, ApiError
from bs4 import BeautifulSoup
import requests
from requests.exceptions import HTTPError
from util import get_most_played_champion
from collections import defaultdict

DISCORD_BOT_TOKEN = os.environ.get('DISCORD_BOT_TOKEN')
RIOT_API_KEY = os.environ.get('RIOT_API_KEY')

lol_watcher = LolWatcher(RIOT_API_KEY)
intents = discord.Intents.default()
intents.message_content = True

summoner_list = []
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            application_id=1036275674694037594
        )

    async def on_ready(self):
        print("ready!")
        activity = discord.Game("상태 메세지")
        await self.change_presence(status=discord.Status.online, activity=activity)

async def create_teams(ctx: commands.Context, summoners: list) -> None:
    if len(summoners) < 10:
        await ctx.send("10명 이상의 소환사를 입력해주세요.")
        return

    team_size = len(summoners) // 2 if len(summoners) < 15 else len(summoners) // 3 if len(summoners) < 20 else len(summoners) // 4
    if len(summoners) % team_size != 0:
        await ctx.send(f"{team_size}의 배수인 소환사를 입력해주세요.")
        return

    team_list = []
    for i in range(team_size):
        team_list.append([])

    for i, summoner_name in enumerate(summoners):
        try:
            summoner = lol_watcher.summoner.by_name('kr', summoner_name)
            league_entries = lol_watcher.league.by_summoner('kr', summoner['id'])
            solo_rank = None
            flex_rank = None

            for entry in league_entries:
                if entry['queueType'] == 'RANKED_SOLO_5x5':
                    solo_rank = entry
                elif entry['queueType'] == 'RANKED_FLEX_SR':
                    flex_rank = entry

            if solo_rank:
                tier = solo_rank['tier']
                rank = solo_rank['rank']
                lp = solo_rank['leaguePoints']
                team_list[i % team_size].append(f"{summoner_name} ({tier} {rank}, {lp} LP)")
            elif flex_rank:
                tier = flex_rank['tier']
                rank = flex_rank['rank']
                lp = flex_rank['leaguePoints']
                team_list[i % team_size].append(f"{summoner_name} ({tier} {rank}, {lp} LP)")
            else:
                tier, rank = get_last_season_tier(summoner_name)
                team_list[i % team_size].append(f"{summoner_name} ({tier} {rank}, 언랭)")

        except ApiError as err:
            print(f'잘못된 소환사명입니다: {summoner_name}')

    response = ""
    for i, team in enumerate(team_list):
        response += f"team{i+1}: {', '.join(team)}\n"

    await ctx.send(response)

def get_last_season_tier(summoner_name):
    opgg_url = f'https://www.op.gg/summoner/userName={summoner_name.replace(" ", "+")}'
    response = requests.get(opgg_url)
    soup = BeautifulSoup(response.text, 'html.parser')
    last_season_tier = soup.find('div', {'class': 'PastRankList'})
    if last_season_tier is None:
        return "언랭", "I"

    tier_and_rank = last_season_tier.find('div', {'class': 'TierRank'}).text.strip()
    tier, rank = tier_and_rank.split()

    return tier, rank

bot = MyBot()

@bot.command(name="소환사등록")
async def register_summoner(ctx: commands.Context, *, summoner_name: str) -> None:
    global summoner_list
    summoner_list.append(summoner_name)
    await ctx.send(f"{summoner_name} 등록 완료! 현재 소환사 목록: {', '.join(summoner_list)}")

@bot.command(name="팀짜기")
async def create_teams_command(ctx: commands.Context) -> None:
    await create_teams(ctx, summoner_list)

@bot.command(name='확인하기')
async def check_summoners(ctx):
    try:
        region = 'kr' # 기본 region을 'kr'으로 설정
        response = ""
        for summoner_name in summoner_list:
            summoner = await lol_watcher.summoner.by_name(region, summoner_name)
            summoner_puuid = summoner['puuid']
            most_played_champ = await get_most_played_champion(lol_watcher, summoner_puuid, region)
            solo_rank = None
            flex_rank = None

            league_entries = lol_watcher.league.by_summoner(region, summoner['id'])
            for entry in league_entries:
                if entry['queueType'] == 'RANKED_SOLO_5x5':
                    solo_rank = entry
                elif entry['queueType'] == 'RANKED_FLEX_SR':
                    flex_rank = entry
            
            if solo_rank:
                tier = solo_rank['tier']
                rank = solo_rank['rank']
                lp = solo_rank['leaguePoints']
                response += f"{summoner_name}: {tier} {rank}, {lp} LP, {most_played_champ}\n"
            elif flex_rank:
                tier = flex_rank['tier']
                rank = flex_rank['rank']
                lp = flex_rank['leaguePoints']
                response += f"{summoner_name}: {tier} {rank}, {lp} LP, {most_played_champ}\n"
            else:
                tier, rank = get_last_season_tier(summoner_name)
                response += f"{summoner_name}: {tier} {rank}, 언랭, {most_played_champ}\n"

        embed = discord.Embed(title="소환사 정보", description=response, color=0xFF5733)
        await ctx.send(embed=embed)
    except HTTPError as err:
        if err.response.status_code == 429:
            await ctx.send('죄송합니다. API 요청 한도를 초과하였습니다. 잠시 후 다시 시도해주세요.')
        else:
            await ctx.send(f'죄송합니다. 오류가 발생했습니다: {err}')

@bot.command(name="help")
async def help_command(ctx: commands.Context):
    help_message = '''
    사용 가능한 명령어:
    !소환사등록 "닉네임"
    - 소환사를 목록에 추가합니다.
    !확인하기
    - 현재 등록된 소환사들의 이름과 간략한 정보 (티어와 랭크, 주로 사용하는 챔피언과 포지션)를 출력합니다.
    !팀짜기
    - 소환사 목록을 기반으로 균형있는 팀을 생성합니다. 팀은 최소 10명일 때 2팀, 15명일 때 3팀, 20명일 때 4팀으로 나뉩니다.
    '''
    await ctx.send(help_message)    

try:
    bot.add_command(register_summoner)
except discord.ext.commands.errors.CommandRegistrationError:
    pass

try:
    bot.add_command(create_teams_command)
except discord.ext.commands.errors.CommandRegistrationError:
    pass

try:
    bot.add_command(help_command)
except discord.ext.commands.errors.CommandRegistrationError:
    pass

try:
    bot.add_command(check_summoners)
except discord.ext.commands.errors.CommandRegistrationError:
    pass

bot.run(DISCORD_BOT_TOKEN)
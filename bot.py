import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from util import *

load_dotenv()
RIOT_API_KEY = os.getenv('RIOT_API_KEY')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

intents = discord.Intents.default()
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            application_id=1036275674694037594
        )

        self.summoners_list = []
        self.db = {} # Assuming this is your database connection

    async def on_ready(self):
        print(f'We have logged in as {self.user}')

bot = MyBot()

# Updated command
@bot.command()
async def 소환사추가(ctx, *summoner_name: str):
    summoner_name = ' '.join(summoner_name)
    summoner_info = get_summoner_info(summoner_name, RIOT_API_KEY)
    if summoner_info:
        bot.summoners_list.append(summoner_info)
        await ctx.send(f"소환사 {summoner_name}이(가) 추가되었습니다.")
    else:
        await ctx.send(f"소환사 {summoner_name}을(를) 찾을 수 없습니다.")

# Updated command
@bot.command()
async def 소환사등록(ctx, summoner_name: str):
    summoner_info = get_summoner_info(summoner_name, RIOT_API_KEY)
    if summoner_info:
        bot.db[summoner_name] = summoner_info
        await ctx.send(f"소환사 {summoner_name}이(가) 등록되었습니다.")
    else:
        await ctx.send(f"소환사 {summoner_name}을(를) 찾을 수 없습니다.")

# Updated command
@bot.command()
async def 확인하기(ctx):
    if not bot.summoners_list:
        await ctx.send("추가된 소환사가 없습니다.")
        return

    embed = discord.Embed(title="소환사 정보", color=0x00ff00)
    for summoner in bot.summoners_list:
        embed.add_field(name=f"{summoner['name']} - {summoner['tier']} {summoner['rank']}",
                        value=f"Level: {summoner['level']}\nOP.GG: {summoner['opgg_url']}",
                        inline=False)
    await ctx.send(embed=embed)

tier_colors = {
    "IRON": 0x5D5D5D,
    "BRONZE": 0x824A02,
    "SILVER": 0x8C8C8C,
    "GOLD": 0xD4AF37,
    "PLATINUM": 0x0FB9B1,
    "DIAMOND": 0x1774FF,
    "MASTER": 0x9437D4,
    "GRANDMASTER": 0xE23B3B,
    "CHALLENGER": 0x1D8FE1,  # 새로운 색상 코드로 변경
}

@bot.command()
async def 팀짜기(ctx):
    teams = balance_teams(bot.summoners_list)
    
    if not teams:
        await ctx.send("팀을 짤 수 없습니다.")
        return
    
    global recent_teams
    recent_teams.append(teams)
    team_color = [tier_colors[team[0]['tier']] for team in teams]

    for i, (team, color) in enumerate(zip(teams, team_color)):
        summoners_str = ", ".join([f"{summoner['name']} - {summoner['tier']} {summoner['rank']}" for summoner in team])
        avg_tier = get_average_tier([summoner['tier'] for summoner in team], [summoner['rank'] for summoner in team])
        embed = discord.Embed(title=f"TEAM {i + 1}", description=summoners_str, color=color)
        embed.add_field(name="주목해야 할 소환사", value=f"{team[0]['name']} - {team[0]['tier']} {team[0]['rank']}", inline=False)
        embed.add_field(name="평균 티어", value=avg_tier, inline=False)
        await ctx.send(embed=embed)

# New help command
@bot.command()
async def help(ctx):
    help_embed = discord.Embed(title="도움말", description="사용 가능한 명령어 목록입니다.", color=0x00ff00)
    help_embed.add_field(name="!소환사추가 [소환사 이름]",
                         value="소환사를 리스트에 저장합니다.\nex) !소환사추가 hide on bush",
                         inline=False)
    help_embed.add_field(name="!소환사등록 [소환사 이름]",
                         value="소환사를 데이터베이스에 저장합니다.\nex) !소환사등록 hide on bush",
                         inline=False)
    help_embed.add_field(name="!확인하기",
                         value="추가된 소환사들의 정보를 확인합니다.",
                         inline=False)
    help_embed.add_field(name="!팀짜기",
                         value="추가된 소환사들을 바탕으로 내전 팀을 구성합니다.",
                         inline=False)
    await ctx.send(embed=help_embed)

@bot.command()
async def 평가하기(ctx, evaluation: float):
    global team_evaluator
    
    teams = find_recent_teams()
    input_vector = teams_to_input_vector(teams)
    
    x_train = np.array([input_vector])
    y_train = np.array([evaluation])
    train_team_evaluator(team_evaluator, x_train, y_train)
    await ctx.send("팀 평가를 기반으로 AI를 업데이트했습니다.")

bot.run(DISCORD_BOT_TOKEN)

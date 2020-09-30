import discord
import requests
import xml.etree.ElementTree as ET
import datetime
import pytz
import math

import asyncio

# Number of seconds between polling the recent games
POLL_FREQUENCY = 300

client = discord.Client()

secret = 'THIS ISNT THE REAL SECRET'

gameCache = {}

playerCache = {}

async def poll_games():
  await client.wait_until_ready()

  # Assumes bot is only connected to one server
  guild = client.guilds[0]
  # Get our bot channel
  channel = discord.utils.get(guild.text_channels, name="luxbot")

  while True:  # TODO(jestelle) Maybe only loop while connected?
    await get_games(channel, gameCache, playerCache)
    await asyncio.sleep(POLL_FREQUENCY)

newUserMessage = """
Welcome to the bestest, Lux Delux'iest discord server around.

Here you can chat about Lux if you want, but better yet you can
sign up for notifications of people actively playing.

If you'd like to receive notifications for Bio full-house games, type:
```.iwant bio```
If you'd like to receive notifications for _any_ ranked Classic games, type:
```.iwant classic```
If you'd like to receive notifications for high average RAW games, type:
```.iwant highraw```
If you want something else, talk to SecondTermMistake. Enjoy!
"""

@client.event
async def on_member_join(member):
    guild = client.guilds[0]
    # Get our primary channel where we'll welcome people
    channel = discord.utils.get(guild.text_channels, name="general")

    welcome_message(channel, member)

async def welcome_message(channel, member):
    print("Recognised that a member called " + member.name + " joined")
    try: 
      await channel.send("Hello " + member.mention + "\n" + newUserMessage)
      print("Sent message to " + member.name)
    except:
        print("Couldn't message " + member.name)

@client.event
async def on_ready():
  print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
  if message.author == client.user:
    return

  if message.content.startswith('hello'):
    await message.channel.send('Hello!')

  if message.content.startswith('.checknow'):
    await get_games(message.channel, gameCache, playerCache);

  if message.content.startswith('.iwant'):
    await add_roles(message.author, message.channel, message.content[7:], True)

  if message.content.startswith('.idontwant'):
    await add_roles(message.author, message.channel, message.content[11:], False)

  if message.content.startswith('.rankings'):
    await display_rankings(message.channel, playerCache)

  if message.content.startswith('.help'):
    await welcome_message(message.channel, playerCache)


async def display_rankings(channel, players):
  sorted_players = sorted(players.items(), key=lambda x: x[1], reverse=True)
  result = map(lambda x: str(x[1]) + " " + x[0], sorted_players)
  await channel.send("\n".join(result))


async def add_roles(member, channel, role_str, add):
  guild = channel.guild
  for role in guild.roles:
    if (role.name.lower() == role_str.lower()):
      if add:
        await member.add_roles(role)
        await channel.send(member.mention + " will be notified about " + role.name + " games.\n" + \
                           "Turn off with ```.idontwant " + role.name + "```")
      else:
        await member.remove_roles(role)
        await channel.send(member.mention + " will no longer be notified about " + role.name + " games.\n" + \
                           "Turn on with ```.iwant " + role.name + "```")


async def get_games(channel, theCache, thePlayers):
  guild = channel.guild
  # Find roles so we can ping them
  classic_role = None
  bio_role = None
  highraw = None
  for role in guild.roles:
    if (role.name == "Classic"):
      classic_role = role
    if (role.name == "Bio"):
      bio_role = role
    if (role.name == "HighRaw"):
      highraw = role

  stm = None
  for member in guild.members:
    if (member.name == "jestelle"):
      stm = member

  url = 'http://sillysoft.net/lux/xml/gameHistory.php?lastGames=10'
  
  # creating HTTP response object from given url 
  resp = requests.get(url) 

  classicTime = False
  bioTime = False
  latestGames = ""
  
  tree = ET.fromstring(resp.content)
  for game in tree:
    # Assumes daylight savings time right now
    dtEnd = datetime.datetime.strptime(game.attrib['end'] + "-0400", "%Y-%m-%d %H:%M:%S%z")

    dtUtcNow = datetime.datetime.utcnow()
    dtUtcNow = dtUtcNow.replace(tzinfo=pytz.utc)

    dtDiff = dtUtcNow - dtEnd

    beforeRaw = thePlayers.copy()

    if not (game.attrib['game_id'] in theCache):
      net_raw = 0
      total_raw = 0
      for player in game:
        if player.attrib['raw_new']:
          total_raw += int(player.attrib['raw_new'])
          # Update player raw
          thePlayers[player.attrib['nick']] = int(player.attrib['raw_new'])
        if player.attrib['raw_change']:
          net_raw += int(player.attrib['raw_change'])
      avg_raw = math.floor(total_raw / 6.0)

      latestGames += game.attrib['map'] + ", " + \
                     game.attrib['numberHumans'] + " humans, " + \
                     str(math.floor(dtDiff.total_seconds() / 60.0)) + " minutes ago - " + \
                     str(avg_raw) + " avg raw, " + str(net_raw) + " net change\n"
                     #game.attrib['end'] + "\n"


      if avg_raw >= 900:
        await channel.send(highraw.mention + " We just saw a game with " + \
                           str(avg_raw) + " avg raw, come and get some!")

      # do we know STMs raw?
      stm_raw = 0
      for player in thePlayers:
        if player == "SecondTermMistake":
          stm_raw = thePlayers[player]
      for player in game:
        # the player has new raw, were in the before raw
        # their before raw was less than STMs, but their 
        # now raw is more than STMs, then let STM know
        if (player.attrib['raw_new'] and
            player.attrib['nick'] != "SecondTermMistake" and
            player.attrib['nick'] in beforeRaw and
            beforeRaw[player.attrib['nick']] <= stm_raw and
            thePlayers[player.attrib['nick']] >= stm_raw):
          await channel.send(stm.mention + ", " + player.attrib['nick'] + " just passed you in raw!") 


    if (classic_role and game.attrib['map'].startswith('Classic') and
        not (game.attrib['game_id'] in theCache)):
      classicTime = classic_role.mention + " It's Classic time! " + \
                    game.attrib['numberHumans'] + " humans finished a game " + \
                    str(math.floor(dtDiff.total_seconds() / 60.0)) + " minutes ago"
    if (bio_role and game.attrib['map'].startswith('BioDeux') and
        int(game.attrib['numberHumans']) >= 6 and
        not (game.attrib['game_id'] in theCache)):
      bioTime = bio_role.mention + " It's Bio FULL HOUSE time! " + \
                game.attrib['numberHumans'] + " humans finished a game " + \
                str(math.floor(dtDiff.total_seconds() / 60.0)) + " minutes ago, " + \
                str(avg_raw) + " avg raw, " + str(net_raw) + " net change\n"


  # Reset the cache
  theCache.clear()
  for game in tree:
    theCache[game.attrib['game_id']] = True;

  if len(latestGames) > 0:
    await channel.send(latestGames)

  if (classicTime):
    await channel.send(classicTime)
  if (bioTime):
    await channel.send(bioTime)


client.loop.create_task(poll_games())
client.run(secret)

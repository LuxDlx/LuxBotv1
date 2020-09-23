import discord
import requests
import xml.etree.ElementTree as ET
import datetime
import pytz
import math

import asyncio

# Number of seconds between polling the recent games
POLL_FREQUENCY = 600

client = discord.Client()

secret = 'THIS ISNT THE REAL SECRET'

gameCache = {}

async def poll_games():
  await client.wait_until_ready()

  # Assumes bot is only connected to one server
  guild = client.guilds[0]
  # Get our bot channel
  channel = discord.utils.get(guild.text_channels, name="luxbot")

  while True:  # TODO(jestelle) Maybe only loop while connected?
    await get_games(channel, gameCache)
    await asyncio.sleep(POLL_FREQUENCY)

newUserMessage = """
Welcome to the bestest, Lux Delux'iest discord server around.

Here you can chat about Lux if you want, but better yet you can
sign up for notifications of people actively playing.

If you'd like to receive notifications for Bio full-house games, type:
```.iwant bio```
If you'd like to receive notifications for _any_ ranked Classic games, type:
```.iwant classic```
If you want something else, talk to SecondTermMistake. Enjoy!
"""

@client.event
async def on_member_join(member):
    guild = client.guilds[0]
    # Get our primary channel where we'll welcome people
    channel = discord.utils.get(guild.text_channels, name="general")

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
    await get_games(message.channel, gameCache);

  if message.content.startswith('.iwant'):
    await add_roles(message.author, message.channel, message.content[7:], True)

  if message.content.startswith('.idontwant'):
    await add_roles(message.author, message.channel, message.content[11:], False)


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


async def get_games(channel, theCache):
  guild = channel.guild
  # Find roles so we can ping them
  classic_role = None
  bio_role = None
  for role in guild.roles:
    if (role.name == "Classic"):
      classic_role = role
    if (role.name == "Bio"):
      bio_role = role

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

    if not (game.attrib['game_id'] in theCache):
      latestGames += game.attrib['map'] + ", " + \
                     game.attrib['numberHumans'] + " humans, " + \
                     str(math.floor(dtDiff.total_seconds() / 60.0)) + " minutes ago - " + \
                     game.attrib['end'] + "\n"

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
                str(math.floor(dtDiff.total_seconds() / 60.0)) + " minutes ago"

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

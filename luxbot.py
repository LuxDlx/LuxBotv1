import discord
import requests
import xml.etree.ElementTree as ET
import datetime
import pytz
import math

import asyncio
import subprocess
import threading
import re

import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore

# Number of seconds between polling the recent games
POLL_FREQUENCY = 30

MENTIONS_ON = False

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

secret = 'THIS ISNT THE REAL SECRET'
regcode = 'THIS ISNT THE REAL REGCODE'

gameCache = {}

playerCache = {}

processHolder = {}


# Use the application default credentials
cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred, {
  'projectId': 'botsetc',
})

db = firestore.client()

#doc_ref = db.collection(u'users').document(u'alovelace')
#doc_ref.set({
#    u'first': u'Ada',
#    u'last': u'Lovelace',
#    u'born': 1815
#})



async def poll_games():
  await client.wait_until_ready()

  # Assumes bot is only connected to one server
  guild = client.guilds[0]
  # Get our bot channel
  channel = discord.utils.get(guild.text_channels, name="luxbot")

  while True:  # TODO(jestelle) Maybe only loop while connected?
    await get_tracker(channel, gameCache, playerCache)
    await asyncio.sleep(POLL_FREQUENCY)

newUserMessage = """
Welcome to the bestest, Lux Delux'iest discord server around.

Here you can chat about Lux if you want, but better yet you can
sign up for notifications of people actively playing.

First, tell us your Lux user name by typing:
```.iam <username>```
for example, ```.iam SecondTermMistake```

Then type ```.iwant <min humans>```
to get notifications when there are at least <min humans>
available to play. e.g., `.iwant 2`
"""

old123 = """
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

    await welcome_message(channel, member)

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

  if(message.channel.name == 'stm-host'):
    if ('proc' in processHolder):
        proc = processHolder['proc']
        # this probably has security issues
        if (message.author.id == NOT_SO_SECRET_ID and message.content.startswith('.send ')):
          proc.stdin.write((message.content[6:]).encode() + b'\n')
        else:
          proc.stdin.write(("(discord) " + message.author.nick + ": " + message.content).encode() + b'\n')
        await proc.stdin.drain()

  if message.content.startswith('hello'):
    await message.channel.send('Hello!')

  if message.content.startswith('.checknow'):
    await get_tracker(message.channel, gameCache, playerCache);

  if message.content.startswith('.iplay'):
    await add_roles(message.author, message.channel, message.content[7:], True)

  if message.content.startswith('.idontplay'):
    await add_roles(message.author, message.channel, message.content[11:], False)

  if message.content.startswith('.rankings'):
    await display_rankings(message.channel, playerCache)

  if message.content.startswith('.help'):
    await welcome_message(message.channel, message.author)

  if message.content.startswith('.iwant'):
    await configure_notifs(message.author, message.channel, message.content[7:])

  if message.content.startswith('.iam'):
    if len(message.content) > 5:
      doc_ref = db.collection(u'users').document(str(message.author.id))
      doc_ref.set({
        u'username': message.content[5:],
        u'mention': message.author.mention
      })
      await message.channel.send("Thanks " + message.author.mention + "\n" + \
                                 "Will give you notifications about ```" + \
                                 message.content[5:] + "```\n" + \
                                 "Please type ```.iwant <min humans>```" + \
                                 "to get notifications when there are at least <min humans> " +\
                                 "available to play. e.g., `.iwant 2`")
    else:
      doc_ref = db.collection(u'users').document(str(message.author.id))
      doc = doc_ref.get()
      if doc.exists and 'username' in doc.to_dict():
        await message.channel.send(message.author.mention + " is known as " + \
                                   doc.to_dict()['username'])
      else:
        await message.channel.send("Sorry " + message.author.mention + ", " + \
                                   "We don't know who you are. Please tell us " + \
                                   "with ```.iam <username>```")


async def configure_notifs(member, channel, number):
  doc_ref = db.collection(u'users').document(str(member.id))
  doc = doc_ref.get()

  if len(number) > 0:
    # TODO catch error when number isn't a number
    doc_ref.update({
      u'num': int(number)
    })
    await channel.send("Thanks " + member.mention + "\n" + \
                       "Will give you notifications when there are " + \
                       str(int(number)) + " humans available to play.")
  else:
    if doc.exists and 'num' in doc.to_dict() and doc.to_dict()['num'] > 0:
      await channel.send(member.mention + " will be notified when " + \
                         str(doc.to_dict()['num']) + " humans are available to play.")
    else:
      await channel.send("Ummm " + member.mention + ", " + \
                         "We don't know what you want. Please tell us " + \
                         "with for example: ```.iwant 5``` if you want to be notified " + \
                         "when it's _almost_ a full house.")



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


async def get_tracker(channel, theCache, thePlayers):
  # first check the tracker
  tracker = 'https://sillysoft.net/lux/list503.php'
  tr_resp = requests.get(tracker)

  now = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
  now_plus_10 = now + datetime.timedelta(minutes = 10)

  docs = db.collection(u'users').stream()
  docsAll = []
  for doc in docs:
    docsAll.append(doc)

  tr_tree = ET.fromstring(tr_resp.content)
  muteMe = []
  for host in tr_tree.findall('host'):
    mapDesc = host.find('boardSize').text
    playerNames = host.find('playerNames').text
    guestNames = host.find('guestNames').text or ""
    numPlayers = int(host.find('numberOfPlayers').text.split("/",1)[-1])
    print(mapDesc, numPlayers, playerNames)
    if "Classic" in mapDesc or "BioDeux" in mapDesc:
      mentionList = []
      for doc in docsAll:
        docDict = doc.to_dict()
        if 'num' in docDict and \
           docDict['num'] <= numPlayers and \
           not (docDict['username'] in playerNames) and \
           not (docDict['username'] in guestNames) and \
           (not 'muted' in docDict or docDict['muted'].replace(tzinfo=pytz.UTC) <= now):
          mentionList.append(docDict['mention'])
          muteMe.append(doc.id)
      if len(mentionList) > 0:
        await channel.send("".join(mentionList) + " come and join us for `" + \
                           mapDesc + "`, there's `" + str(numPlayers) + "` waiting.")
      
  for muteId in muteMe:
    doc_ref = db.collection(u'users').document(muteId)
    doc_ref.update({
      u'muted': now_plus_10
    })

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

#  stm = None
#  for member in guild.members:
#    if (member.name == "jestelle"):
#      stm = member

  url = 'http://sillysoft.net/lux/xml/gameHistory.php?lastGames=10'
  
  # creating HTTP response object from given url 
  resp = requests.get(url) 

  classicTime = False
  bioTime = False
  latestGames = ""

  mostRaw = 0
  
  tree = ET.fromstring(resp.content)
  for game in tree:
    # Assumes daylight savings time right now
    dtEnd = datetime.datetime.strptime(game.attrib['end'] + "-0000", "%Y-%m-%d %H:%M:%S%z")
    # This one is for not daylight savings
    #dtEnd = datetime.datetime.strptime(game.attrib['end'] + "-0500", "%Y-%m-%d %H:%M:%S%z")

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


      if avg_raw >= mostRaw:
        mostRaw = avg_raw

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
          await channel.send("<@!182175563115528192>" + ", " + player.attrib['nick'] + " just passed you in raw!") 


    if (classic_role and game.attrib['map'].startswith('Classic') and
        not (game.attrib['game_id'] in theCache) and
        MENTIONS_ON):
      classicTime = classic_role.mention + " It's Classic time! " + \
                    game.attrib['numberHumans'] + " humans finished a game " + \
                    str(math.floor(dtDiff.total_seconds() / 60.0)) + " minutes ago"
    if (bio_role and game.attrib['map'].startswith('BioDeux') and
        int(game.attrib['numberHumans']) >= 6 and
        not (game.attrib['game_id'] in theCache) and
        MENTIONS_ON):
      bioTime = bio_role.mention + " It's Bio FULL HOUSE time! " + \
                game.attrib['numberHumans'] + " humans finished a game " + \
                str(math.floor(dtDiff.total_seconds() / 60.0)) + " minutes ago, " + \
                str(avg_raw) + " avg raw, " + str(net_raw) + " net change\n"

  sorted_players = list(map(lambda x: int(x[1]), sorted(thePlayers.items(), key=lambda x: x[1], reverse=True)))
  high_raw = 0.85 * sum(sorted_players[0:3]) / len(sorted_players[0:3])
  print(mostRaw, high_raw)
  if mostRaw > high_raw and MENTIONS_ON:
    await channel.send(highraw.mention + " We just saw a game with " + \
                       str(mostRaw) + " avg raw, come and get some!")

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



ip_addr_regex = re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b')

supress_if_match = [
            re.compile(r'Crash check: timeRunningMinutes'),
            re.compile(r'STM : \(discord\)')
        ]

async def start_host():
    await client.wait_until_ready()

    # Assumes bot is only connected to one server
    guild = client.guilds[0]
    channel = discord.utils.get(guild.text_channels, name="stm-host")

#                             '-desc=Brought to you by SecondTermMistake. Join my Discord server (https://discord.gg/pfEVcqR).',
    proc = await asyncio.create_subprocess_exec('linux-private-jre8_73-64bit/bin/java',
                             '-Djava.awt.headless=true', '-cp', 'LuxCore.jar:lib/*',
                             'com.sillysoft.lux.Lux', '-headless', '-network=true', '-public=true',
                             '-name=STM_',
                             '-desc=Be nice. No calling people stupid. Have fun. Discord: https://discord.gg/pfEVcqR',
                             '-shuffle3', '-nofirstturncontbonus', '-agent=reapermix',
                             '-regcode=' + regcode,
                             '-map=BioDeux-extreme', '-cards=5e25', '-conts=25', '-time=28', '-gamelimit=45',
                             cwd='/home/josh_estelle/LuxDelux',
                             stdin=asyncio.subprocess.PIPE,
                             stdout=asyncio.subprocess.PIPE,
                             stderr=asyncio.subprocess.PIPE)
    processHolder['proc'] = proc

    while True:
        line = await proc.stdout.readline()
        print('got line: {0}'.format(line.decode('utf-8')), end='')
        strline = re.sub(ip_addr_regex, "---", line.decode('utf-8'))
        if (len(strline) > 0):
            found = False
            for supress in supress_if_match:
                if(re.match(supress, strline)):
                    found=True
                    break
            if (not found):
                try:
                    await channel.send(strline)
                except discord.errors.HTTPException:
                    pass


client.loop.create_task(poll_games())
client.loop.create_task(start_host())
client.run(secret)

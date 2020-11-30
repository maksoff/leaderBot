# maksoff - KSP leaderbot (automagically calculates the rating and etc.)
# ideas - graph of progress

import os
import time

import requests

import discord
from dotenv import load_dotenv

from jsonReader import json_class

import json


check_role = False
check_channel = True

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
ROLE  = os.getenv('DISCORD_ROLE')
CHANNEL = os.getenv('DISCORD_CHANNEL')

class state_machine_class():
    guild_id = None
    next_function = None
    next_next_function = None
    leaderboard_channel_id = None
    leaderboard_message_id = None
    json_path = None
    json_data = None
    
    author_id = None
    last_time = 0
    timeout = 60

    new_submission = {}

    @staticmethod
    def get_int (string):
        return int(''.join(filter(str.isdigit, string)))
    
    @staticmethod
    def yes_no(val):
        val = val.lower()
        if val in ('yes', 'y', 'true', 't', '1', 'enable', 'on'):
            return True
        elif val in ('no', 'n', 'false', 'f', '0', 'disable', 'off'):
            return False
        
    def save_json(s):
        with open(s.json_path, 'w') as f:
            f.write(s.json_data.dump())
            
    def open_json(s):
        with open(s.json_path, 'r') as f:
            try:
                s.json_data.load(f)
                s.leaderboard_channel_id, s.leaderboard_message_id = s.json_data.get_lb_message()
            except Exception as e:
                print(e)
                print('wrong json')
                
    async def get_message(s, ch_id, m_id):
        try:
            channel = s.client.get_channel(ch_id)
            #print('> getting message', channel)
            return await channel.fetch_message(m_id)
        except Exception as e:
            print(e)
            return
    
    async def send(s, channel, content):
        while content:
            await channel.send(content[:2000])
            content = content[2000:]
        
    async def update(s, ch, msg, content):
        s.json_data.calculate_rating()
        if (not msg) or (not ch):
            return 'no message set to update - check settings'
        #print ('> entering update routine')
        msg = await s.get_message(ch, msg)
        #print ('> message is', msg)
        try:
            await msg.edit(content = content)
            return 'updated'
        except Exception as e:
            print(e)
            return 'something wrong'

    async def admin_help(s, *args):
        response = 'Hello! This bot helps to update the leaderboard.\nUse these commands (in `#leaderbot` channel!):\n'
        for n, t, _ in s.commands:
            response += '`{}` - {}\n'.format(n, t)

        response += '\nAll users have additional commands:\n' + await s.user_help()
        return response

    async def user_help(s, *args):
        response = 'Check ranking:\n'
        for n, t, _ in s.user_commands:
            response += '`{}` - {}\n'.format(n, t)
        return response
    
    async def add_static_points(s, msg):
        s.next_function = None
        player = s.json_data.find(s.json_data.j['aPlayer'], sName=s.new_submission['sPlayerName'])
        try:
            player['iStaticPoints'] = player.get('iStaticPoints', 0) + float(msg.content)
            s.save_json()
            return await s.update_lb()
        except Exception as e:
            print(e)
            return 'something wrong'

    async def add_score(s, msg):
        s.next_function = None
        try:
            iSubmissionId = 0
            for ss in s.json_data.j['aSubmission']:
                if (ss.get('sChallengeName') == s.new_submission.get('sChallengeName') and
                        ss.get('sChallengeTypeName') == s.new_submission.get('sChallengeTypeName') and
                        ss.get('sPlayerName') == s.new_submission.get('sPlayerName')):
                    iSubmissionId += 1
            s.new_submission['iSubmissionId'] = iSubmissionId
            s.new_submission['fScore'] = float(msg.content)
            s.json_data.j['aSubmission'].append(s.new_submission)
            s.json_data.calculate_rating()
            s.save_json()
            await s.update_winners()
            await s.update_lb()
            return 'Ready!'
        except Exception as e:
            print(e)
            return 'Something really wrong'

    async def add_challenge_type(s, msg):
        s.next_function = None
        temp = msg.content.strip().split(' ')
        if len(temp) == 1:
            s.new_submission['sChallengeTypeName'] = s.json_data.j['aChallengeType'][int(temp[0])-1]['sName']
            s.next_function = s.add_score
            return 'Now enter score for this challenge:'
        elif len(temp) == 4:
            s.json_data.j['aChallengeType'].append({'sName':temp[0],
                                                    'sNick':temp[1],
                                                    'bHigherScore':temp[2][0] == 'h',
                                                    'fMultiplier':float(temp[3].replace(',','.'))})
            s.new_submission['sChallengeTypeName'] = temp[0]
            s.save_json()
            s.next_function = s.add_score
            return 'New type created!\nNow enter score for this challenge:'
        else:
            return 'Wrong parameter count'
        return 'not implemented'

    def get_challenge_types(s):
        response = 'You already have following challenge types (`>` = used in this challenge):'
        for i, chl in enumerate(s.json_data.j['aChallengeType'], 1):
            bold = False
            if s.json_data.find(s.json_data.j['aSubmission'], sChallengeName=s.new_submission['sChallengeName'], sChallengeTypeName=chl.get('sName')):
                bold = True
            response += '\n{5}**{0:3}**. `{1}`; display name: **{2}**, *{3}* score wins, multiplier **{4}**'.format(
                i, chl.get('sName'), chl.get('sNick', chl.get('sName')),
                '*higher*' if chl.get('bHigherScore') else 'lower',
                chl.get('fMultiplier', 1),
                '\>' if bold else '   ')
        return response
            

    async def add_challenge_user(s, msg):
        s.next_function = None
        response = ''
        try:
            user_id = s.get_int(msg.content)
            user = await s.client.fetch_user(user_id)
            player = s.json_data.find(s.json_data.j['aPlayer'], iID=user_id)
            if player:
                response += 'Existing user\n'
                s.new_submission['sPlayerName'] = player['sName']
            else:
                response += 'New user, cool!\n'
                s.json_data.j['aPlayer'].append({'sName':user.name + '#' + user.discriminator,
                                                 'iID':user_id})
                s.new_submission['sPlayerName'] = user.name + '#' + user.discriminator
                s.save_json()
            if s.next_next_function:
                s.next_function = s.next_next_function
                s.next_next_function = None
                return 'how many points?'
            s.next_function = s.add_challenge_type
            response += s.get_challenge_types()
            response += '\n\nEnter number of existing type (e.g. `1`)'
            response += '\nor create new type in format `unique_name display_name lower/higher multiplier`'
            response += '\n(e.g. `extra_x3 impossible lower 3.14`)'
            return response
        except Exception as e:
            print(e)
            return 'something gone wrong'
        return 'not implemented'

    async def add_winners_channel(s, msg):
        s.next_function = None
        try:
            channel_id = s.get_int(msg.content)
            channel = client.get_channel(channel_id)
            msg = await channel.send('Here will be winners published')
            message_id = msg.id
            s.json_data.j['aChallenge'].append({'sName':s.new_submission['sChallengeName'],
                                                 'idChannel':channel_id,
                                                 'idMessage':message_id})
            s.save_json()
        except Exception as e:
            print(e)
            return "channel doesn't exist"
        else:
            s.next_function = s.add_challenge_user
            return 'Placeholder created. \nPlease enter user (e.g. @best_user) or user id:'
        return

    async def add_challenge(s, msg):
        s.next_function = None
        s.new_submission['sChallengeName'] = msg.content
        if msg.content in s.json_data.list_of_challenges():
            s.next_function = s.add_challenge_user
            return 'Existing challenge. \nPlease enter user (e.g. @best_user) or user id:'
        s.next_function = s.add_winners_channel
        return 'New challenge, cool! \n In which channel should be added winners-table? (e.g. #winners-42)'

    async def add_submission(s, _):
        s.next_function = s.add_challenge
        s.new_submission = {}
        response = 'Past challenges: ' + ', '.join(s.json_data.list_of_challenges())
        response += '\nFor which challenge is this submission? (e.g. 42):'
        return response
    
    async def del_submission(s, _):
        return '_not implemented_'
    
    async def add_points(s, _):
        s.next_next_function = s.add_static_points
        s.next_function = s.add_challenge_user
        return 'Please enter user (e.g. @best_user) or user id:'

    async def entries(s, _):
        return '_not implemented_'

    async def del_submission(s, _):
        return '_not implemented_'

    # settings for leaderboard
    async def set_lb_channel_name(s, msg):
        s.next_function = None
        try:
            s.leaderboard_channel_id = s.get_int(msg.content)
            channel = client.get_channel(s.leaderboard_channel_id)
            msg = await channel.send('Here will be leaderboard published')
            s.leaderboard_message_id = msg.id
            s.json_data.set_lb_message(s.leaderboard_channel_id, s.leaderboard_message_id)
            s.save_json()
        except Exception as e:
            print(e)
            return "channel doesn't exist"
        else:
            await s.update_lb()
            return 'placeholder created'

    async def set_lb(s, _):
        s.next_function = s.set_lb_channel_name
        return 'In which channel should be posted leaderboard?'

    async def update_winners(s, *args):
        sub = s.new_submission.get('sChallengeName')
        if sub:
            sub = [sub]
        else:
            sub = s.json_data.list_of_challenges()
        for sub in sub:
            try:
                challenge = s.json_data.find(s.json_data.j['aChallenge'], sName=sub)
                idChannel = challenge.get('idChannel')
                idMessage = challenge.get('idMessage')
                if idChannel and idMessage:
                    await s.update(idChannel, idMessage, s.json_data.result_challenge(sub))
            except Exception as e:
                print(e)
    
    async def update_lb(s, *args):
        try:
            s.json_data.calculate_rating()
            s.save_json()
            try:
                url = s.json_data.j.get('sPOSTURL')
                if url:
                    payload = s.json_data.j
                    payload['iGuildID'] = s.guild_id
                    headers = {'content-type': 'application/json'}
                    for player in payload['aPlayer']:
                        player['iID'] = str(player['iID'])
                    data = json.dumps(payload)
                    for player in payload['aPlayer']:
                        player['iID'] = int(player['iID'])
                    requests.post(url, data=data, headers=headers)
            except Exception as e:
                print(str(e))
            return await s.update(s.leaderboard_channel_id, s.leaderboard_message_id, s.json_data.result_leaderboard())
        except Exception as e:
            print(e)
            return 'something wrong'
            
    async def print_lb(s, msg):
        try:
            for l in s.json_data.list_of_challenges():
                if s.json_data.result_challenge(l):
                    await msg.channel.send(s.json_data.result_challenge(l))
            await msg.channel.send(s.json_data.result_leaderboard())                       
            return '*** Done ***'
        except:
            return 'no/corrupt json'
    
    async def json_exp(s, message):
        try:
            await message.channel.send(file=discord.File(s.json_path))
        except:
            return '**No file found.** Please add some challenges or import json.'
        return 'Here we go'

    async def json_read(s, message):
        s.next_function = None
        if message.attachments:
            test = message.attachments[0].filename
            try:
                await message.attachments[0].save(fp=s.json_path)
                s.open_json()
                await s.update_lb()
                s.save_json()
                await s.update_winners()
            except Exception as e:
                print(e)
                return 'failed to save'
            return test + ' received and saved'
        return 'No file sent. Try again'

    async def json_imp(s, _):
        s.next_function = s.json_read
        return 'Please send me your json!'

    async def json_del_confirm(s, msg):
        s.next_function = None
        if s.yes_no(msg.content):
            if os.path.exists(s.json_path):
                await s.json_exp(msg)
                os.remove(s.json_path)
                return 'All info removed! Now you can delete bot, or start from scratch'
            else:
                return 'File not found'
        else:
            return 'Cancelled'

    async def json_del(s, *msg):
        s.next_function = s.json_del_confirm
        return 'Do you really want to delete all info?'

    async def get_rank(s, msg):
        message = msg.content.strip().split(' ')
        if len(message) == 1:
            user_id = msg.author.id
        else:
            user_id = s.get_int(message[1])
        try:
            user = await s.client.fetch_user(user_id)
            name = '@' + user.name
            response = s.json_data.get_rank(user_id)
        except:
            name = 'user not found'
            response = 'maybe invite him?'
        embed = discord.Embed()
        embed.add_field(name=name, value=response)
        #embed.remove_author()
        await msg.channel.send(embed=embed)
        
    async def get_top(s, msg):
        limit = 7
        if len(msg.content.strip().split(' ')) > 1:
            try:
                limit = int(msg.content.split(' ')[1])
            except:
                ...
        response = s.json_data.get_top(limit)
        if s.leaderboard_channel_id:
            response += '\n\nFull list: <#' + str(s.leaderboard_channel_id) + '>'
        embed = discord.Embed()
        embed.add_field(name='TOP '+str(limit), value=response)
        await msg.channel.send(embed=embed)

    async def post(s, msg):
        try:
            url = msg.content.strip().split(' ')[1]
            payload = s.json_data.j
            payload['iGuildID'] = s.guild_id
            headers = {'content-type': 'application/json'}
            try:
                if len(msg.content.split(' ')) > 2:
                    r = requests.post(url, data='', headers=headers)
                else:
                    for player in payload['aPlayer']:
                        player['iID'] = str(player['iID'])
                    data = json.dumps(payload)
                    for player in payload['aPlayer']:
                        player['iID'] = int(player['iID'])
                    r = requests.post(url, data=data, headers=headers)       
                response = '\nstatus: {} \ntext: {}'.format(
                    r.status_code, r.text)
            except Exception as e:
                response = 'Exception: ' + str(e)
            return 'Done: ' + str(response)
        except Exception as e:
            return 'Specify URL `?post URL`'
    

    async def seturl(s, msg):
        data = msg.content.strip().split(' ')
        if len(data) == 1:
            try:
                del s.json_data.j['sPOSTURL']
            except:
                return 'No Auto-POST URL found'
            return 'Auto-POST URL deleted'
        else:
            s.json_data.j['sPOSTURL'] = data[1]
            s.save_json()
            return 'Auto-POST URL updated'
            
    async def __call__(s, message):
        response = ''
        
        bChannel = message.channel.name == CHANNEL

        try:
            bRole = ROLE in [role.name for role in message.author.roles]
        except:
            bRole = False
            

        if (((check_channel and check_role) and (bChannel and bRole)) or
            ((check_channel and (not check_role)) and bChannel) or
            (((not check_channel) and check_role) and bRole)):
            if s.next_function and s.author_id and (message.author.id != s.author_id and time.time() - s.last_time > s.timeout):
                s.author_id = None
                s.next_function = None
                s.next_next_function = None
                await s.send(message.channel, '**timeout**')
            for n, _, f in s.commands:
                if message.content.lower().startswith(n):
                    s.next_function = None
                    s.next_next_function = None
                    s.author_id = message.author.id
                    s.last_time = time.time()
                    response = await f(message)
                    break
            else:
                if s.next_function and s.author_id == message.author.id:
                    response = await s.next_function(message)  
            if response:
                await s.send(message.channel, response)
                return
                    
        for n, _, f in s.user_commands:
            if message.content.lower().startswith(n):
                response = await f(message)
                break
            
        if response:
            await s.send(message.channel, response)
            return
        
        if 'good' in message.content.lower() and 'bot' in message.content.lower():
            if len(message.content) == 8:
                await message.channel.send('Thanks!')
                return
            
    def create_help (s, *args):

        s.user_commands = (
                              ('?help', 'prints this message', s.user_help),
                              ('?rank', 'your rank; `?rank @user` to get @user rank', s.get_rank),
                              ('?top', 'leaderboard; add number to limit positions `?top 3`', s.get_top),
                              ('?leaderboard', 'same as `?top`', s.get_top),
                          )
        
        s.commands = (('?help', 'prints this message', s.admin_help),
                      ('?add', 'to add new submission', s.add_submission),
                      ('?static points', 'add points (e.g. giveaways)', s.add_points),
                      ('?update', 'force leaderboard update', s.update_lb),
                      ('?print all', 'prints leaderboard for all challenges **can be slow because of discord**', s.print_lb),
                      ('?set leaderboard', 'set in which channel to post leaderboard', s.set_lb),
                      ('?export json', 'exports data in json', s.json_exp),
                      ('?import json', 'imports data from json', s.json_imp),
                      ('?delete json', 'clears all you data from server', s.json_del),
                      ('?post', 'send json over `post` request. e.g.`?post http://URL`', s.post),
                      ('?seturl', '`?seturl URL` - where will be JSON posted after each ranking update', s.seturl),
                      )
    
    def __init__(s, client, guild_id):
        s.guild_id = guild_id
        s.client = client
        s.json_data = json_class()
        s.create_help()
        
        s.json_path = str(guild_id)+'.txt'
        if(os.path.isfile(s.json_path)):
            s.open_json()
            print ('json loaded')
        else:
            print('no json found')

client = discord.Client()

sm = {}

@client.event
async def on_ready():
    for guild in client.guilds:
        sm[guild.id] = state_machine_class(client, guild.id)
        await sm[guild.id].update_lb()
        await sm[guild.id].update_winners()
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='your ?rank'))
        print(
            f'{client.user} is connected to the following guild:\n'
            f'{guild.name}(id: {guild.id})'
        )

@client.event
async def on_message(message):             
    if message.author == client.user:
        return
    await sm[message.guild.id](message)
        
client.run(TOKEN)

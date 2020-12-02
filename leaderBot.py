# maksoff - KSP leaderbot (automagically calculates the rating and etc.)
# ideas - graph of progress

import os
import time
import asyncio

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
    leaderboard_channel_id = None
    leaderboard_message_id = None
    json_path = None
    json_data = None

    client = None
    
    ## assistant functions

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

    async def wait_response(s, message, timeout=30):
        '''returns message or None if timeout'''
        try:
            def check(m):
                return (m.author.id == message.author.id) and (m.channel == message.channel)
            return await client.wait_for('message', timeout=timeout, check=check)
        except asyncio.TimeoutError:
            await message.channel.send(f'`timeout {timeout}s`')
            return 
        except Exception as e:
            print(e)
            return
                    
    async def get_message(s, ch_id, m_id):
        try:
            channel = s.client.get_channel(ch_id)
            return await channel.fetch_message(m_id)
        except Exception as e:
            print(e)
            return
    
    async def send(s, channel, content):
        content = str(content)
        while content:
            await channel.send(content[:2000])
            content = content[2000:]
        
    async def update(s, ch, msg, content):
        if (not msg) or (not ch):
            return 'no message set to update - check settings'
        msg = await s.get_message(ch, msg)
        try:
            await msg.edit(content = content)
            return 'updated'
        except Exception as e:
            print(e)
            return 'something wrong'

    ## json file functions
          
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
        
    async def json_exp(s, message):
        try:
            await message.channel.send(file=discord.File(s.json_path))
        except:
            return '**No file found.** Please add some challenges or import json.'
        return 'Here we go'


    async def json_imp(s, message):
        await message.channel.send('Please send me your json!')

        message = await s.wait_response(message)
        if not message:
            return 'cancelled'
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


    async def json_del(s, message):
        await message.channel.send('Do you really want to delete all info?')
        message = await s.wait_response(message, timeout=5)
        if not message:
            return 'cancelled'
        if s.yes_no(message.content):
            if os.path.exists(s.json_path):
                await s.json_exp(message)
                os.remove(s.json_path)
                return 'All info removed! Now you can delete bot, or start from scratch'
            else:
                return 'File not found'
        else:
            return 'Cancelled'

    ## state machine functions
    
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

    def get_challenge_types(s, sChallengeName):
        response = 'You already have following challenge types (`>` = used in this challenge):'
        for i, chl in enumerate(s.json_data.j['aChallengeType'], 1):
            bold = False
            if s.json_data.find(s.json_data.j['aSubmission'], sChallengeName=sChallengeName, sChallengeTypeName=chl.get('sName')):
                bold = True
            response += '\n{5}**{0:3}**. `{1}`; display name: **{2}**, *{3}* score wins, multiplier **{4}**'.format(
                i, chl.get('sName'), chl.get('sNick', chl.get('sName')),
                '*higher*' if chl.get('bHigherScore') else 'lower',
                chl.get('fMultiplier', 1),
                '\>' if bold else '   ')
        return response

    async def ask_for_challenge_type(s, message, sChallengeName):
        ''' returns sChallengeTypeName, if new - creates'''
        response = s.get_challenge_types(sChallengeName)
        response += '\n\nEnter number of existing type (e.g. `1`)'
        response += '\nor create new type in format `unique_name display_name lower/higher multiplier`'
        response += '\n(e.g. `extra_x3 impossible lower 3.14`)'
        await s.send(message.channel, response)
        
        message = await s.wait_response(message)
        if not message:
            return 'aborted'
        
        temp = message.content.strip().split(' ')
        if len(temp) == 1:
            return s.json_data.j['aChallengeType'][int(temp[0])-1]['sName']
        elif len(temp) == 4:
            s.json_data.j['aChallengeType'].append({'sName':temp[0],
                                                    'sNick':temp[1],
                                                    'bHigherScore':temp[2][0] == 'h',
                                                    'fMultiplier':float(temp[3].replace(',','.'))})
            s.save_json()
            return temp[0]
        else:
            await s.send(message.channel, 'Wrong parameter count')
            return 

    async def ask_for_user_id(s, message):
        '''returns user_id or None if failed, creates user if new'''
        await s.send(message.channel, 'Please enter user (e.g. @best_user) or user id:')
        
        message = await s.wait_response(message)
        if not message:
            return
        
        try:
            user_id = s.get_int(message.content)
            user = await s.client.fetch_user(user_id)
            user_id = user.id
            player = s.json_data.find(s.json_data.j['aPlayer'], iID=user_id)
            if player:
                await s.send(message.channel,  'Existing user')
            else:
                await s.send(message.channel, '**New** user, cool!')
                s.json_data.j['aPlayer'].append({'sName':user.name, 'iDiscriminator': user.discriminator,
                                                 'iID':user_id})
                s.save_json()
            return user_id
        except Exception as e:
            await s.send(message.channel, 'No user with this id found. Aborting')
            print(e)
            return


    async def set_challenge_channel(s, message, change_existing_channel=True):
        '''selection for challenge, and updating/creating of channel. Returns None in case of error or sChallengeName'''
        # challenges list
        response = 'Past challenges: `' + '`, `'.join(s.json_data.list_of_challenges())
        response += '`\nEnter challenge name (e.g. `42`)\n(if challenge not in the list, new challenge will be created)'
        await s.send(message.channel, response)
        # select challenge
        message = await s.wait_response(message)
        if not message:
            return
        sChallengeName = message.content
        if sChallengeName in s.json_data.list_of_challenges():
            await s.send(message.channel, 'Existing challenge')
            if not change_existing_channel: return ('Done: ' if change_existing_channel else '') + sChallengeName 
        else:
            await s.send(message.channel, '**New** challenge, cool!')
        try:
            await s.send(message.channel, 'Select channel to post winners (e.g. `#winners-42`)')
            message = await s.wait_response(message)
            if not message:
                return 'aborted'
            channel_id = s.get_int(message.content)
            channel = client.get_channel(channel_id)
            msg = await channel.send('Here will be winners published')
            message_id = msg.id
            if sChallengeName in s.json_data.list_of_challenges():
                sC = s.json_data.find(s.json_data.j['aChallenge'], sName=sChallengeName)
                sC['idChannel'] = channel_id
                sC['idMessage'] = message_id
            else:
                s.json_data.j['aChallenge'].append({'sName':sChallengeName,
                                                     'idChannel':channel_id,
                                                     'idMessage':message_id})
            s.save_json()
            await s.update_winners(sChallengeName=sChallengeName)
            return ('Done: ' if change_existing_channel else '') + sChallengeName 
        except Exception as e:
            print(e)
            return None
        return

    async def add_submission(s, message):
        await s.send(message.channel, 'For which challenge is this submission?')
        # select challenge
        sChallengeName = await s.set_challenge_channel(message, change_existing_channel=False)
        if not sChallengeName:
            return 'Something wrong'
        # select user
        user_id = await s.ask_for_user_id(message)
        if not user_id:
            return 'wrong id - aborted'
        # select challenge type
        sChallengeTypeName = await s.ask_for_challenge_type(message, sChallengeName)
        if not sChallengeName:
            return 'wrong challenge type - aborted'
        # add score
        try:
            iSubmissionId = 0
            for ss in s.json_data.j['aSubmission']:
                if (ss.get('sChallengeName') == sChallengeName and
                        ss.get('sChallengeTypeName') == sChallengeTypeName and
                        ss.get('iUserID') == user_id):
                    iSubmissionId += 1
            
            embed = discord.Embed()
            embed.add_field(name='Submissions for this challenge',
                value=s.json_data.result_challenge(sChallengeName, ignoreScore=False))
            #embed.remove_author()
            await message.channel.send(embed=embed)
            await s.send(message.channel, 'Enter score (e.g. `3.14`):')
            message = await s.wait_response(message)
            if not message:
                return 'aborted'
            fScore = float(message.content)
            s.json_data.j['aSubmission'].append({'iUserID':user_id,
                                                 'sChallengeName':sChallengeName,
                                                 'sChallengeTypeName':sChallengeTypeName,
                                                 'iSubmissionId':iSubmissionId,
                                                 'fScore':fScore})
            s.json_data.calculate_rating()
            response = await s.update_all(message)
            return response
        except Exception as e:
            print(e)
            return 'Something really wrong'
        return 'not ready'
    
    async def add_points(s, message):
        user_id = await s.ask_for_user_id(message)
        if not user_id:
            return 'cancelled'
        player = s.json_data.find(s.json_data.j['aPlayer'], iID=user_id)
        await s.send(message.channel, 'How many points? (e.g. `2.5`)')
        message = await s.wait_response(message)
        if not message:
            return 'cancelled'
        try:
            player['iStaticPoints'] = player.get('iStaticPoints', 0) + float(message.content)
            s.save_json()
            return await s.update_lb()
        except Exception as e:
            print(e)
            return 'something wrong'

    async def set_lb(s, message):
        await s.send(message.channel, 'In which channel should be posted leaderboard?')
        message = await s.wait_response(message)
        if not message:
            return 'cancelled'
        try:
            channel_id = s.get_int(message.content)
            channel = client.get_channel(channel_id)
            msg = await channel.send('Here will be published leaderboard')
            s.leaderboard_channel_id = channel.id
            s.leaderboard_message_id = msg.id
            s.json_data.set_lb_message(s.leaderboard_channel_id, s.leaderboard_message_id)
            s.save_json()
        except Exception as e:
            print(e)
            return "channel doesn't exist"
        else:
            await s.update_lb()
            return 'placeholder created'

    async def update_usernames(s, *args):
        for player in s.json_data.j['aPlayer']:
            try:
                user = await s.client.fetch_user(player.get('iID'))
                player['sName'] = user.name
                player['iDiscriminator'] = user.discriminator
            except Exception as e:
                print(e)
        s.save_json()
        return

    async def update_winners(s, *args, sChallengeName=None):
        if sChallengeName:
            sub = [sChallengeName]
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
            await s.post()
            return await s.update(s.leaderboard_channel_id, s.leaderboard_message_id, s.json_data.result_leaderboard())
        except Exception as e:
            print(e)
            return 'something wrong'

    async def update_all(s, message):
        await s.send(message.channel, '*updating...*')
        response = await s.update_lb()
        await s.update_winners()
        return response
            
    async def print_lb(s, msg):
        try:
            for l in s.json_data.list_of_challenges():
                if s.json_data.result_challenge(l):
                    await msg.channel.send(s.json_data.result_challenge(l))
            await msg.channel.send(s.json_data.result_leaderboard())                       
            return '*** Done ***'
        except:
            return 'no/corrupt json'

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
        except Exception as e:
            print(e)
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

    async def post(s, *args):
        data = None
        if len(args) == 0:
            try:
                url = s.json_data.j.get('sPOSTURL')
                if not url:
                    return
            except Exception as e:
                print(str(e))
                return
        else:
            try:
                url = args[0].content.strip().split(' ')[1]
            except Exception as e:
                return 'Specify URL `?post URL`'

            # send empty data
            if len(args[0].content.split(' ')) > 2:
                data = ''

        if data == None:    
            def deepcopy(temp):
                ret = None
                if type(temp) is dict:
                    ret = {}
                    for key, val in temp.items():
                        ret[key] = deepcopy(val)
                elif type(temp) is list:
                    ret = []
                    for val in temp:
                        ret.append(deepcopy(val))
                else:
                    return str(temp)
                return ret
            await s.update_usernames()
            payload = deepcopy(s.json_data.j)            
            payload['iGuildID'] = s.guild_id
            data = json.dumps(payload)
            
        headers = {'content-type': 'application/json'}
        try:
            r = requests.post(url, data=data, headers=headers)       
            response = '\nstatus: `{}` \ntext: `{}`'.format(
                        r.status_code, r.text)
        except Exception as e:
            response = 'Exception: {}'.format(e)
        return 'Done: ' + str(response)
    

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
        
        def has_rights(message):
            bChannel = message.channel.name == CHANNEL
            try:
                bRole = ROLE in [role.name for role in message.author.roles]
            except:
                bRole = False
            return (((check_channel and check_role) and (bChannel and bRole)) or
                    ((check_channel and (not check_role)) and bChannel) or
                    (((not check_channel) and check_role) and bRole))

        if has_rights(message):
            for n, _, f in s.commands:
                if message.content.lower().startswith(n):
                    response = await f(message)
                    break
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
                      ('?update', 'force leaderboard update', s.update_all),
                      ('?print all', 'prints leaderboard for all challenges **can be slow because of discord**', s.print_lb),
                      ('?set leaderboard', 'set in which channel to post leaderboard', s.set_lb),
                      ('?set winners', 'set in which channel to post winners for challenge', s.set_challenge_channel),
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

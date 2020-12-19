# maksoff - KSP leaderbot (automagically calculates the rating and etc.)

### beautify fScore output
### cancel input
### sort winners
### activity card
### activity (sum of last 3 challenges)
### try to create submission from embed (role react?)
### hash avatars

# TODO: #
# hyperkerbalnaut role - automatic
# leaderboard ?help -> add image
# create channels for new submissions
# change prefix
# ?about ?invite

import io
import os
import copy
import time
import asyncio

import requests
import random

import discord
from dotenv import load_dotenv

from jsonReader import json_class
import rankDisplay

import json


check_role = False
check_channel = True

load_dotenv()
TOKEN   = os.getenv('DISCORD_TOKEN')
ROLE    = os.getenv('DISCORD_ROLE')
CHANNEL = os.getenv('DISCORD_CHANNEL')
DEBUG_CH = os.getenv('DISCORD_DEBUG_CH')
if DEBUG_CH:
    DEBUG_CH = int(DEBUG_CH)

DEBUG = os.getenv('DISCORD_TEST')


def deepcopy(temp):
    '''deepcopy for json - with integer encapsulating'''
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


def deepcopy_nostring(temp):
    return copy.deepcopy(temp)

    ret = None
    if type(temp) is dict:
        ret = {}
        for key, val in temp.items():
            ret[key] = deepcopy_nostring(val)
    elif type(temp) is list:
        ret = []
        for val in temp:
            ret.append(deepcopy_nostring(val))
    else:
        return temp
    return ret

class leaderBot_class():
    guild_id = None
    leaderboard_channel_id = None
    leaderboard_message_id = None
    json_path = None
    json_data = None

    client = None

    ksp_hints = None
    avatar_cache={}
    
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

    async def wait_response(s, message, timeout=120, **kwargs):
        '''returns message or None if timeout'''

        # if from reaction - parse author_id
        author_id = kwargs.get('author_id')
        if not author_id:
            author_id = message.author.id
        try:
            def check(m):
                return (m.author.id == author_id) and (m.channel == message.channel)
            msg = await client.wait_for('message', timeout=timeout, check=check)
            if msg.content.lower() == 'cancel':
                await message.channel.send(f'`canceled`')
                return
            return msg
        except asyncio.TimeoutError:
            await message.channel.send(f'`timeout {timeout}s`')
            return 
        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            return
                    
    async def get_message(s, ch_id, m_id):
        try:
            channel = s.client.get_channel(ch_id)
            return await channel.fetch_message(m_id)
        except Exception as e:
            print(e)
            return

    async def get_avatar(s, user_id, update=False, user = None):

        if not update and user_id in s.avatar_cache:
            return s.avatar_cache[user_id].get('avatar_asset')

        if not user:
            user = await s.client.fetch_user(user_id)

        # if in cache and hash not changed return saved thingy
        if user_id in s.avatar_cache:
            if user.avatar == s.avatar_cache[user_id].get('hash'):
                return s.avatar_cache[user_id].get('avatar_asset')
        else:
            s.avatar_cache[user_id] = {}
            
        if not user: # wrong id ?
            return
        # nothing found - get avatar   
        AVATAR_SIZE = 128
        try:
            avatar_asset = user.avatar_url_as(format='png', size=AVATAR_SIZE)
            user_avatar = io.BytesIO(await avatar_asset.read())
        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            user_avatar = None

        s.avatar_cache[user_id]['hash'] = user.avatar
        s.avatar_cache[user_id]['avatar_asset'] = user_avatar

        return user_avatar
    
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
            if DEBUG:
                raise e
            else:
                print(e)
            return 'something wrong'

    ## json file functions
          
    def save_json(s):
        if s.json_data.dump():
            with open(s.json_path, 'w') as f:
                f.write(s.json_data.dump())
            
    def open_json(s):
        with open(s.json_path, 'r') as f:
            try:
                s.json_data.load(f)
                s.leaderboard_channel_id, s.leaderboard_message_id = s.json_data.get_lb_message()
            except Exception as e:
                if DEBUG:
                    raise e
                else:
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
                if DEBUG:
                    raise e
                else:
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
            response += '\n{5}**{0:3}**. `{1}`; display name: **{2}**, *{3}* score wins, multiplier **{4}**{6}'.format(
                i, chl.get('sName'), chl.get('sNick', chl.get('sName')),
                '*higher*' if chl.get('bHigherScore') else 'lower',
                chl.get('fMultiplier', 1),
                '\>' if bold else '   ',
                '; points[score] (special)' if chl.get('bSpecial') else '')
        return response

    async def ask_for_challenge_type(s, message, sChallengeName, **kwargs):
        ''' returns sChallengeTypeName, if new - creates'''
        response = s.get_challenge_types(sChallengeName)
        response += '\n\nEnter number of existing type (e.g. `1`)'
        response += '\nor create new type in format `unique_name display_name lower/higher multiplier`'
        response += ' - `lower/higher` = which score wins, `multiplier` = points multiplier'
        response += '\n||add optional `=` at the end, if points = points[score]. e.g for *higher_wins*, '
        response += 'and points system = [50, 40, 30, 20, 10], if score=`4` player gets `40` points||'
        response += '\n(e.g. `extra_x3 impossible lower 3.14`)'
        await s.send(message.channel, response)
        
        message = await s.wait_response(message, author_id=kwargs.get('author_id')) # first wait responce - add author_id in case start from reaction
        if not message:
            return
        
        temp = message.content.strip().split(' ')
        if len(temp) == 1:
            try:
                return s.json_data.j['aChallengeType'][int(temp[0])-1]['sName']
            except:
                await s.send(message.channel, 'wrong index')
                return
        elif len(temp) == 4:
            s.json_data.j['aChallengeType'].append({'sName':temp[0],
                                                    'sNick':temp[1],
                                                    'bHigherScore':temp[2][0] == 'h',
                                                    'fMultiplier':float(temp[3].replace(',','.'))})
            s.save_json()
            return temp[0]
        elif len(temp) == 5 and temp[4] == '=':
            s.json_data.j['aChallengeType'].append({'sName':temp[0],
                                                    'sNick':temp[1],
                                                    'bHigherScore':temp[2][0] == 'h',
                                                    'fMultiplier':float(temp[3].replace(',','.')),
                                                    'bSpecial':True})
            s.save_json()
            return temp[0]
        else:
            await s.send(message.channel, 'Wrong parameter count')
            return 

    async def ask_for_user_id(s, message, no_creation=False, **kwargs):
        '''returns user_id or None if failed, creates user if new'''
        await s.send(message.channel, 'Please enter user (e.g. @best_user) or user id:')
        
        message = await s.wait_response(message, author_id=kwargs.get('author_id')) # first wait_responce - if from react author_id supplied
        if not message:
            return
        
        try:
            user_id = s.get_int(message.content)
            user = await s.client.fetch_user(user_id)
            if user.bot:
                await s.send(message.channel, "No bots, please. *aborted*")
                return
            user_id = user.id
            player = s.json_data.find(s.json_data.j['aPlayer'], iID=user_id)
            if player:
                await s.send(message.channel,  'Existing user')
            else:
                if no_creation:
                    await s.send(message.channel, 'No user with this id found. Aborting')
                    return
                await s.send(message.channel, '**New** user, cool!')
                s.json_data.j['aPlayer'].append({'sName':user.name, 'iDiscriminator': user.discriminator,
                                                 'iID':user_id})
                s.save_json()
            return user_id
        except Exception as e:
            await s.send(message.channel, 'No user with this id found. Aborting')
            if DEBUG:
                raise e
            else:
                print(e)
            return

    async def get_points_for_channel(s, message):
        '''asks for points or saves new point systems. None if error'''
        response = 'Available scoring systems:'
        # get all points in challenges
        aPoints = set()
        aPoints.add(s.json_data.aPoint)
        for ch in s.json_data.j['aChallenge']:
            ap = ch.get('aPoints')
            if ap:
                aPoints.add(tuple(sorted(ap, reverse=True)))
        aPoints = sorted(aPoints, reverse=True)
        for i, a in enumerate(aPoints, 1):
            a = ['{:g}'.format(float(x)) for x in a]
            response += '\n{:4}: `'.format(i) + '` `'.join(a) + '`'
        response += '\nEnter number (e.g. `1`), or new point sequence (e.g. `10 6 4 3.14 1`)'
        await s.send(message.channel, response)
        message = await s.wait_response(message)
        if not message:
            return
        ar = message.content.strip().split(' ')
        if len(ar)==1:
            return aPoints[int(ar[0])-1]
        return sorted([float(x) for x in ar], reverse=True)
        


    async def set_challenge_channel(s, message, change_existing_channel=True, **kwargs):
        '''selection for challenge, and updating/creating of channel.'''
        '''Returns None in case of error or sChallengeName'''
        '''also defines points system & show/hide score in #winners channel'''
        # challenges list
        response = 'Past challenges: `' + '`, `'.join(s.json_data.list_of_challenges() or 'no challenges!')
        response += '`\nEnter challenge name (e.g. `42`)\n(if challenge not in the list, new challenge will be created)'
        await s.send(message.channel, response)
        # select challenge
        message = await s.wait_response(message, author_id=kwargs.get('author_id')) # first wait_responce, author_id should be sent in case of start from reaction
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
                return
            channel_id = s.get_int(message.content)
            channel = client.get_channel(channel_id)
            msg = await channel.send('Here will be winners published')
            message_id = msg.id
            
            await s.send(message.channel, 'Show score for this challenge in #winners? (yes/no)')
            message = await s.wait_response(message)
            if not message:
                return
            bShowScore = s.yes_no(message.content)
            
            if sChallengeName in s.json_data.list_of_challenges():
                sC = s.json_data.find(s.json_data.j['aChallenge'], sName=sChallengeName)
                sC['idChannel'] = channel_id
                sC['idMessage'] = message_id
                sC['bShowScore'] = bShowScore
            else:
                aPoints = await s.get_points_for_channel(message)
                if not aPoints:
                    return
                s.json_data.j['aChallenge'].append({'sName': sChallengeName,
                                                    'idChannel': channel_id,
                                                    'idMessage': message_id,
                                                    'bShowScore': bShowScore,
                                                    'aPoints': aPoints})
            s.save_json()
            await s.update_winners(sChallengeName=sChallengeName)
            return ('Done: ' if change_existing_channel else '') + sChallengeName 
        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            return None
        return

    async def add_submission(s, message, **kwargs):
        await s.send(message.channel, '__Type `cancel` at any time to... wait for it... *cancel*__\nFor which challenge is this submission?')

        # if started from react - author_id for wait_for
        author_id = kwargs.get('author_id')

        # select challenge
        if kwargs.get('sChallengeName'):
            sChallengeName = kwargs.get('sChallengeName')
            embed = discord.Embed()
            embed.add_field(name='Auto challenge name', value=f'Challenge **{sChallengeName}**')
            await message.channel.send(embed=embed)
        else:
            sChallengeName = await s.set_challenge_channel(message, change_existing_channel=False, author_id=author_id)
        if not sChallengeName:
            return 'unknown challenge name'
        # select user
        if kwargs.get('iID'):
            user_id = kwargs.get('iID')
            author_name = kwargs.get('author_name')
            embed = discord.Embed()
            embed.add_field(name='Auto user', value=f'**@{author_name}** id: **{user_id}**')
            await message.channel.send(embed=embed)
        else:
            user_id = await s.ask_for_user_id(message, author_id=author_id)
        if not user_id:
            return 'wrong id - aborted'
        # select challenge type
        sChallengeTypeName = await s.ask_for_challenge_type(message, sChallengeName, author_id=author_id)
        if not sChallengeTypeName:
            return 'wrong challenge type - aborted'
        # add score
        try:
            iSubmissionId = 0
            for ss in s.json_data.j['aSubmission']:
                if (ss.get('sChallengeName') == sChallengeName and
                        ss.get('sChallengeTypeName') == sChallengeTypeName and
                        ss.get('iUserID') == user_id):
                    iSubmissionId += 1
            
            embed = discord.Embed(title='Submissions for challenge **{}**'.format(sChallengeName))
            r_list = s.json_data.result_challenge_embed(sChallengeName, ignoreScore=False)
            for item in r_list:
                embed.add_field(name=item['name'],
                                value=item['value'],
                                inline=False)
            await message.channel.send(embed=embed)
            
            await s.send(message.channel, 'Enter score (e.g. `3.14`):')
            message = await s.wait_response(message, author_id=author_id)
            if not message:
                return 'aborted'
            fScore = float(message.content)
            s.json_data.j['aSubmission'].append({'iUserID':user_id,
                                                 'sChallengeName':sChallengeName,
                                                 'sChallengeTypeName':sChallengeTypeName,
                                                 'iSubmissionId':iSubmissionId,
                                                 'fScore':fScore})
            #s.json_data.calculate_rating()
            response = await s.update_all(message)
            return response
        except Exception as e:
            if DEBUG:
                raise e
            else:
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
            if DEBUG:
                raise e
            else:
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
            if DEBUG:
                raise e
            else:
                print(e)
            return "channel doesn't exist"
        else:
            await s.update_lb()
            return 'placeholder created'

    async def set_mention_ch(s, message):
        await s.send(message.channel, f'In which channel should be posted <@{client.user.id}> mentions?')
        msg = await s.wait_response(message)
        if not msg:
            return 'cancelled'
        try:
            channel_id = s.get_int(msg.content)
            channel = client.get_channel(channel_id)
            if channel:
                s.json_data.j['iMentionsChannel'] = channel.id
                
                text = ''
                await message.channel.send('Who should be mentioned? Enter `@users`, `@roles` or `*` for empty')
                msg = await s.wait_response(message)
                if msg.content != '*':
                    text = str(msg.content)
                s.json_data.j['iMentionsText'] = text
                
                text = ''
                await message.channel.send('In which channels bot should **react** to mentions (separate multiple with *space*)?\n' +
                                           'e.g. `miss test` for sub**miss**ion, **miss**ions and **test**\n' +
                                           'or `*` for no filter')
                msg = await s.wait_response(message)
                if msg.content != '*':
                    text = str(msg.content)
                s.json_data.j['iMentionsChIncluded'] = text
                
                text = ''
                await message.channel.send('In which channels bot should **ignore** mentions (separate multiple with *space*)?\n' +
                                           'e.g. `admin anno` for **admin** and **anno**ucements\n' +
                                           'or `*` for no filter')
                msg = await s.wait_response(message)
                if msg.content != '*':
                    text = str(msg.content)
                s.json_data.j['iMentionsChExcluded'] = text
                s.save_json()
            else:
                return "channel doesn't exist"
        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            return "channel doesn't exist"
        else:
            return 'Ok, saved'

    async def update_usernames(s, *args):
        for player in s.json_data.j['aPlayer']:
            try:
                user = await s.client.fetch_user(player.get('iID'))
                await s.get_avatar(user.id, update=True, user=user) # update avatar too
                player['sName'] = user.name
                player['iDiscriminator'] = user.discriminator
            except Exception as e:
                if DEBUG:
                    raise e
                else:
                    print(e)
        s.save_json()
        return

    async def update_winners_old(s, *args, sChallengeName=None):
        if sChallengeName:
            sub = [sChallengeName]
        else:
            sub = s.json_data.list_of_challenges()
        for sub in sub:
            try:
                challenge = s.json_data.find(s.json_data.j['aChallenge'], sName=sub)
                idChannel = challenge.get('idChannel')
                idMessage = challenge.get('idMessage')
                ignoreScore = not challenge.get('bShowScore', False)
                
                embed = discord.Embed()
                embed.add_field(name='Submissions for this challenge',
                    value=s.json_data.result_challenge(sub, ignoreScore=ignoreScore))
                
                if idChannel and idMessage:
                    msg = await s.get_message(idChannel, idMessage)
                    await msg.edit(content='', embed=embed)
            except Exception as e:
                if DEBUG:
                    raise e
                else:
                    print('update_winners\n', e)

    
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
                ignoreScore = not challenge.get('bShowScore', False)
                
                embed = discord.Embed(title='Submissions for challenge **{}**'.format(sub))
                r_list = s.json_data.result_challenge_embed(sub, ignoreScore=ignoreScore)
                for item in r_list:
                    embed.add_field(name=item['name'],
                                    value=item['value'],
                                    inline=False)
                
                if idChannel and idMessage:
                    msg = await s.get_message(idChannel, idMessage)
                    if msg:
                        await msg.edit(content='', embed=embed)
            except Exception as e:
                if DEBUG:
                    raise e
                else:
                    print('update_winners\n', e)
                    
    
    async def update_lb(s, *args):
        try:
            await s.update_usernames() # update usernames & avatars
            s.json_data.calculate_rating()
            s.save_json()
            await s.post()

            name, value = s.json_data.result_leaderboard().split('\n', 1)
            
            embed = discord.Embed()
            embed.add_field(name=name, value=value)
            
            msg = await s.get_message(s.leaderboard_channel_id, s.leaderboard_message_id)
            try:
                await msg.edit(content='', embed=embed)
                await s.update_lb_img()
                return 'updated'
            except Exception as e:
                if DEBUG:
                    raise e
                else:
                    print(e)
                return 'something wrong'
            
        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            return 'something wrong'

    async def update_all(s, message):
        await s.send(message.channel, '*updating...*')
        response = await s.update_lb()
        await s.update_winners()
        return response
            
    async def print_lb(s, msg):
        try:
            for sub in s.json_data.list_of_challenges():
                embed = discord.Embed(title='Submissions for challenge **{}**'.format(sub))
                r_list = s.json_data.result_challenge_embed(sub, ignoreScore=False)
                for item in r_list:
                    embed.add_field(name=item['name'],
                                    value=item['value'],
                                    inline=False)
                await msg.channel.send(embed=embed)
                
            name, value = s.json_data.result_leaderboard().split('\n', 1)
            embed = discord.Embed()
            embed.add_field(name=name, value=value)
            await msg.channel.send(embed=embed)                       
            return '*** Done ***'
        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
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
            if DEBUG:
                raise e
            else:
                print(e)
            name = 'user not found'
            response = 'maybe invite him?'
        embed = discord.Embed()
        embed.add_field(name=name, value=response)
        #embed.remove_author()
        await msg.channel.send(embed=embed)

    async def rank_img(s, msg):
        # find user.id and user
        message = msg.content.strip().split(' ')
        if len(message) == 1:
            user_id = msg.author.id
        else:
            user_id = s.get_int(message[1])
            
        try:
            user = await s.client.fetch_user(user_id)
        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            return 'User not found. Maybe invite him?'

##        guild = s.client.get_guild(s.guild_id)
##        print(guild)
##        member = guild.get_member(user_id)
##        print(member)

        # get player info from json
        player = s.json_data.find(s.json_data.j['aPlayer'], iID=user_id)
        if player:
            rank = player.get('iRank', None)
            points = player.get('iPoints', None)
        if not (player and rank and points):
            return 'You need to earn some points. Submit some challenges!'

        # find max points
        max_points = max(player.get('iPoints') for player in s.json_data.j['aPlayer'])

        #get avatar & channel icon
        user_avatar = await s.get_avatar(user_id, update=True, user=user)
            
        try:
            AVATAR_SIZE = 128
            avatar_asset = msg.guild.icon_url_as(format='png', size=AVATAR_SIZE)
            guild_avatar = io.BytesIO(await avatar_asset.read())
        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            guild_avatar = None

        buffer = rankDisplay.create_rank_card(user_avatar,
                                              guild_avatar,
                                              user.display_name,
                                              user.discriminator,
                                              points,
                                              max_points,
                                              rank,
                                              len(s.json_data.j['aPlayer']))
        await msg.channel.send(file=discord.File(buffer, 'rank.png'))
        return None

    async def activity_img(s, message):
        try:
            try:
                msg = await message.channel.send('Consulting Picasso...')
                buffer = await s.get_activity_img()
                await msg.delete(delay=3)
                message = await message.channel.send(content = 'Activity graph. One **column** per challenge, **brighter** => more points for this challenge', file=discord.File(buffer, 'activity.png'))
                return
            except Exception as e:
                if DEBUG:
                    raise e
                else:
                    print(e)
                return 'something wrong'

        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            return 'something wrong'

    async def get_activity_img(s, *args):
        s.json_data.calculate_rating()
        # get not disabled players with submissions
        players = sorted(s.json_data.j['aPlayer'], key=lambda x: float(x.get('iPoints')), reverse=True)
        players = list(filter(lambda x: (float(x.get('iPoints', 0)) - float(x.get('iStaticPoints', 0)) > 0) and not x.get('bDisabled', False), players))
        if not players:
            return
        lChallenges = list(s.json_data.list_of_challenges())
        dMaxPoints = {}
        players_prepared = []
        for p in players:
            # get submissions matrix
            pp = {}
            pp['aSubmissions'] = []
            pp['iRank'] = p.get('iRank')
            for ch in lChallenges:
                points = sum(float(x.get('iPoints', 0)) for x in s.json_data.j['aSubmission']
                             if x.get('iUserID') == p.get('iID') and x.get('sChallengeName') == ch)
                if dMaxPoints.get(ch, 0) < points:
                    dMaxPoints[ch] = points # max points for challenge
                pp['aSubmissions'].append((ch, points))

            #get avatar     
            pp['avatar'] = await s.get_avatar(p.get('iID', None))
            players_prepared.append(pp)
        buffer = rankDisplay.create_activity_card(players_prepared, dMaxPoints)
        return buffer
    
    
    async def update_lb_img(s, *args):
        try:
            s.json_data.calculate_rating()
            try:
                channel_id = s.leaderboard_channel_id
                if not channel_id:
                    return 'please configure `?set leaderboard`'
                channel = client.get_channel(channel_id)

                # leaderboard image
                message_id = s.json_data.j.get('iLeaderboardImage')
                if message_id:
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                    except:
                        ...
                buffer = await s.get_top_img(0)
                message = await channel.send(content = 'updated leaderboard', file=discord.File(buffer, 'lb.png'))
                s.json_data.j['iLeaderboardImage'] = message.id

                # activity image
                message_id = s.json_data.j.get('iActivityImage')
                if message_id:
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.delete()
                    except:
                        ...
                buffer = await s.get_activity_img()
                message = await channel.send(content = 'Activity graph. One **column** per challenge, **brighter** => more points for this challenge', file=discord.File(buffer, 'actual.png'))
                s.json_data.j['iActivityImage'] = message.id
                
                s.save_json()
                return 'updated'
            except Exception as e:
                if DEBUG:
                    raise e
                else:
                    print(e)
                return 'something wrong'

        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            return 'something wrong'

    async def get_top_img(s, limit):
        s.json_data.calculate_rating()
        players = sorted(s.json_data.j['aPlayer'], key=lambda x: float(x.get('iPoints')), reverse=True)
        if not players:
            return
        data = []

        for player in players:
            if player.get('bDisabled') or (limit == 0 and (float(player.get('iStaticPoints', 0)) - float(player.get('iPoints', 0))) == 0):
                continue
            if limit:
                if player.get('iRank') > limit:
                    break

            data.append({'iRank':player.get('iRank'),
                         'sName':player.get('sName'),
                         'iDiscriminator':player.get('iDiscriminator'),
                         'iPoints':player.get('iPoints'),
                         'avatar':await s.get_avatar(player.get('iID'))
                         })
            await s.get_avatar(player['iID'])
        buffer = rankDisplay.create_top_card(data)
        return buffer
        

    async def top_img(s, *msg, leaderboard=False, content=None):
        limit = 7
        if msg:
            msg = msg[0]
        if len(msg.content.strip().split(' ')) > 1:
            try:
                limit = int(msg.content.split(' ')[1])
            except:
                ...
        if leaderboard:
            limit = 0
            
        if not leaderboard and not content:
            content = f"Full leaderboard: <#{s.leaderboard_channel_id}>\n**Top {limit}**"
            if limit > 7:
                content += " (click to enlarge)"
        m = await msg.channel.send('Consulting Dali...')
        buffer = await s.get_top_img(limit)
        await m.delete(delay=3)
        if buffer:
            await msg.channel.send(content=content, file=discord.File(buffer, 'top.png'))
        else:
            return "no submissions found"
        return
        
        
    async def get_top(s, msg, full_list=False):
        limit = 7
        if len(msg.content.strip().split(' ')) > 1:
            try:
                limit = int(msg.content.split(' ')[1])
            except:
                ...
        if full_list:
            limit = 0
        response = s.json_data.get_top(limit)
        if s.leaderboard_channel_id:
            response += '\n\nFull list: <#' + str(s.leaderboard_channel_id) + '>'
        embed = discord.Embed()
        if not limit:
            limit = 'ALL'
        embed.add_field(name='TOP '+str(limit), value=response)
        await msg.channel.send(embed=embed)


    async def act_img(s, *msg):
        limit = 7
        if msg:
            msg = msg[0]
        if len(msg.content.strip().split(' ')) > 1:
            try:
                limit = int(msg.content.split(' ')[1])
            except:
                ...
        if limit == 0:
            return await s.activity_img(msg)
                
        m = await msg.channel.send('Consulting Alphonse Mucha...')
        buffer = await s.get_act_img(limit=limit)
        await m.delete(delay=3)
        content=(f'**Activity top {limit}**\n' +
                '*10 points for each submission in last 3 weeks, 5 points for older 3 weeks, additional points for multiple attempts*\n'+
                f"Full leaderboard: <#{s.leaderboard_channel_id}>")
        if buffer:
            await msg.channel.send(content=content, file=discord.File(buffer, 'activity_top.png'))
        else:
            return "no submissions found"
        return

    async def get_act_img(s, *args, limit=7):
        data = s.json_data.get_active(limit=limit)
        for item in data:
            user_id = item.get('iID', None)
            user = await s.client.fetch_user(user_id)
            #get avatar & channel icon    
            AVATAR_SIZE = 128
            try:
                avatar_asset = user.avatar_url_as(format='png', size=AVATAR_SIZE)
                user_avatar = io.BytesIO(await avatar_asset.read())
            except Exception as e:
                if DEBUG:
                    raise e
                else:
                    print(e)
                user_avatar = None

            item['avatar'] = user_avatar
        buffer = rankDisplay.create_top_card(data, color_scheme=1)
        return buffer

    async def post(s, *args):
        return '***'
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

    async def disable(s, msg):
        await s.get_top(msg, full_list=True)
        user_id = await s.ask_for_user_id(msg, no_creation=True)
        if not user_id:
            return 'aborted'
        s.json_data.find(s.json_data.j['aPlayer'], iID=user_id)['bDisabled']=True
        s.save_json()
        await msg.channel.send('Disabled.')
        return await s.update_all(msg)

    async def enable(s, msg):
        responce = 'Disabled players:'
        for p in s.json_data.j['aPlayer']:
            if p.get('bDisabled'):
                responce += f'\n<@{p.get("iID")}>'
        responce += '\n**Who should be reenabled?**'
        await msg.channel.send(responce)
        user_id = await s.ask_for_user_id(msg, no_creation=True)
        if not user_id:
            return 'aborted'
        s.json_data.find(s.json_data.j['aPlayer'], iID=user_id)['bDisabled']=False
        s.save_json()
        await msg.channel.send('Enabled.')
        return await s.update_all(msg)

    async def ksp(s, *args):
        if not s.ksp_hints:
            s.ksp_hints = open("ksp.txt").readlines()
        return random.choice(s.ksp_hints)[:-1]

    async def ping(s, *args):
        return 'Pong! {}ms'.format(int(s.client.latency*1000))

    async def mentioned(s, message):
        # will be supported in 1.6 await message.channel.send('Okay', reference=message)

        # check if channel exists
        channel_id = s.json_data.j.get('iMentionsChannel')
        text = s.json_data.j.get('iMentionsText')
        
        if channel_id:
            try:
                channel = client.get_channel(channel_id)
            except:
                return
            if not channel:
                return
        else:
            return


        inc_ch = s.json_data.j.get('iMentionsChIncluded', '').split()
        exc_ch = s.json_data.j.get('iMentionsChExcluded', '').split()

        chk_ch = message.channel.name
        
        if exc_ch and any(x in chk_ch for x in exc_ch):
            return
        if inc_ch and not any(x in chk_ch for x in inc_ch):
            return

        # send confirmation
        part_1 = ('submission written down',
                  'all logged',
                  'this is marked now',
                  'okay, noted',
                  'recorded this',
                  'evidence registered',
                  'submission reported',
                  'copy what',
                  'roger',
                  )
        part_2 = ('Kadmins will be notified ASAP! Or tomorrow...',
                  'Kadmins are on the Jool orbit with only Ion engines. They will be notified as soon they are back',
                  'Kadmins chilling on Eeloo. Your submission will be send with the next post-ship (ETA: 4 years 189 days)',
                  'Kadmins now tanning on Moho. Because of Kerbol activity message can be corrupte#12!$30<42< `C`R`C` eRr0r',
                  'Kadmins gone to Val. Or to Vall? As soon they are back, all be updated',
                  'Relax, read a book. Kadmins will update all soon',
                  '   .--. .-.. . .- ... . / .-- .- .. -',
                  "Kadmins are at meeting! Or sleeping. Don't know, but all be updated soon",
                  "Kadmins are stuck on Eve. Please send help. And snacks.",
                  "Kadmins installed RSS & RO. They are lost now.")
        user_id = message.author.id
        await message.channel.send(f'<@{user_id}> {random.choice(part_1)}. {random.choice(part_2)}')

        # try to find the challenge
        category_id = message.channel.category_id
        challenge = {}
        for ch in s.json_data.j.get('aChallenge'):
            ch_id = ch.get('idChannel')
            ch_comp = s.client.get_channel(ch_id)
            if ch_comp and category_id == ch_comp.category_id:
                if challenge:
                    challenge = {} # multiple challenges in this category found, can't decide
                    break
                else:
                    challenge = ch
                    
        ch_name = challenge.get('sName')
        ch_winners = challenge.get('idChannel')

        # add embed to channel
        embed = discord.Embed(title='New mention!')
        embed.add_field(name='user', value=f'<@{message.author.id}>')
        embed.add_field(name='user ID', value=f'{message.author.id}')
        embed.add_field(name='channel', value=f'<#{message.channel.id}>')
        embed.add_field(name='message', value=f'[jump]({message.jump_url})')

        if ch_name:
            embed.add_field(name='challenge', value=f'{ch_name}')
        if ch_winners:
            embed.add_field(name='#winners', value=f'<#{ch_winners}>')

            
        embed.add_field(name='message text', value=f'{message.content}', inline=False)
        
        msg = await channel.send(content=text, embed=embed)

        accept = '✅'
        decline = '❌'
        
        await msg.add_reaction(accept)
        await msg.add_reaction(decline)
        
        def check(reaction, user):
            return ((reaction.message.id == msg.id) and
                    (s.client.user == msg.author) and
                    (str(reaction.emoji) in (accept, decline)) and
                    (reaction.count > 1))
        
        try:
            reaction, user = await client.wait_for('reaction_add', check=check)
        except Exception as e:
            if DEBUG:
                raise (e)
            else:
                print(e)
                
        if str(reaction.emoji) == decline:
            await msg.clear_reactions()
            return
        await msg.clear_reactions()
                
        responce = await s.add_submission(msg,
                                          iID=message.author.id,
                                          author_name=message.author.display_name,
                                          sChallengeName=ch_name,
                                          author_id=user.id)

        if responce:
            await s.send(msg.channel, responce)

                
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

        # check if role or bot is mentioned
        if (((s.client.user in message.mentions) or
             (s.client.user in [member
                                for role in message.role_mentions
                                for member in role.members])
             )
                    and not message.mention_everyone):
            await s.mentioned(message)
            return

        # good bot
        if 'good' in message.content.lower() and 'bot' in message.content.lower():
            if len(message.content) == 8:
                await message.channel.send('Thanks!')
                return
            
        return
            
    def create_help (s, *args):

        s.user_commands = (
                              ('?help', 'prints this message', s.user_help),
                              ('?rank', 'your rank; `?rank @user` to get @user rank', s.rank_img),
                              ('?top', 'leaderboard; add number to limit positions `?top 3`', s.top_img),
                              ('?leaderboard', 'same as `?top`', s.top_img),
                              ('?activity', 'activity rank; add number to limit positions `?activity 3`', s.act_img),
                              ('?ksp', 'random ksp loading hint', s.ksp),
                          )
        
        s.commands = (('?help', 'prints this message', s.admin_help),
                      ('?ping', 'bot latency', s.ping),
                      ('?add', 'to add new submission', s.add_submission),
                      ('?static points', 'add points (e.g. giveaways)', s.add_points),
                      ('?update', 'force leaderboard update', s.update_all),
                      ('?print all', 'prints leaderboard for all challenges **can be slow because of discord**', s.print_lb),
                      ('?set leaderboard', 'set in which channel to post leaderboard', s.set_lb),
                      ('?set winners', 'set in which channel to post winners for challenge', s.set_challenge_channel),
                      ('?set mentions', f'set channel where <@{s.client.user.id}> mentions will be posted', s.set_mention_ch),
                      ('?export json', 'exports data in json', s.json_exp),
                      ('?import json', 'imports data from json', s.json_imp),
                      ('?delete json', 'clears all you data from server', s.json_del),
                      ('?post', 'send json over `post` request. e.g.`?post http://URL`', s.post),
                      ('?seturl', '`?seturl URL` - where will be JSON posted after each ranking update', s.seturl),
                      ('?disable user', 'to hide user from leaderboard', s.disable),
                      ('?enable user', 'to reenable user to leaderboard', s.enable),
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
print('client created')

leaderBot = {}

@client.event
async def on_ready():
    for guild in client.guilds:
        if DEBUG_CH:
            if guild.id != DEBUG_CH:
                continue
        leaderBot[guild.id] = leaderBot_class(client, guild.id)
        await leaderBot[guild.id].update_lb()
        await leaderBot[guild.id].update_winners()
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='your ?rank'))
        print(
            f'{client.user} is connected to the following guild:\n'
            f'{guild.name}(id: {guild.id})'
        )

@client.event
async def on_message(message):
    if DEBUG_CH:
        if message.guild.id != DEBUG_CH:
            return
    if message.author.bot:
        return
    if message.author == client.user:
        return
    await leaderBot[message.guild.id](message)

print('ready, steady, go')
client.run(TOKEN)

# maksoff - KSP leaderbot (automagically calculates the rating and etc.)
# ideas - graph of progress

import io
import os
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
TOKEN = os.getenv('DISCORD_TOKEN')
ROLE  = os.getenv('DISCORD_ROLE')
CHANNEL = os.getenv('DISCORD_CHANNEL')
DEBUG_CH = os.getenv('DISCORD_DEBUG_CH')
if DEBUG_CH:
    DEBUG_CH = int(DEBUG_CH)

DEBUG = os.getenv('DISCORD_TEST')


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


def deepcopy_nostring(temp):
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

class state_machine_class():
    guild_id = None
    leaderboard_channel_id = None
    leaderboard_message_id = None
    json_path = None
    json_data = None

    client = None

    ksp_hints = None
    
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

    async def wait_response(s, message, timeout=60):
        '''returns message or None if timeout'''
        try:
            def check(m):
                return (m.author.id == message.author.id) and (m.channel == message.channel)
            return await client.wait_for('message', timeout=timeout, check=check)
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
            if DEBUG:
                raise e
            else:
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
            await s.message.channel.send('aborted')
            return
        
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

    async def ask_for_user_id(s, message, no_creation=False):
        '''returns user_id or None if failed, creates user if new'''
        await s.send(message.channel, 'Please enter user (e.g. @best_user) or user id:')
        
        message = await s.wait_response(message)
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
        


    async def set_challenge_channel(s, message, change_existing_channel=True):
        '''selection for challenge, and updating/creating of channel.'''
        '''Returns None in case of error or sChallengeName'''
        '''also defines points system & show/hide score in #winners channel'''
        # challenges list
        response = 'Past challenges: `' + '`, `'.join(s.json_data.list_of_challenges() or 'no challenges!')
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
                await message.channel.send('aborted')
                return
            channel_id = s.get_int(message.content)
            channel = client.get_channel(channel_id)
            msg = await channel.send('Here will be winners published')
            message_id = msg.id
            
            await s.send(message.channel, 'Show score for this challenge in #winners? (yes/no)')
            message = await s.wait_response(message)
            if not message:
                await message.channel.send('aborted')
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

    async def update_usernames(s, *args):
        for player in s.json_data.j['aPlayer']:
            try:
                user = await s.client.fetch_user(player.get('iID'))
                player['sName'] = user.name
                player['iDiscriminator'] = user.discriminator
            except Exception as e:
                if DEBUG:
                    raise e
                else:
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
    
    async def update_lb(s, *args):
        try:
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
            
        try:
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
##                channel_id = s.leaderboard_channel_id
##                if not channel_id:
##                    return 'please configure `?set leaderboard`'
##                channel = client.get_channel(channel_id)
##                message_id = s.json_data.j.get('iLeaderboardImage')
##                if message_id:
##                    try:
##                        message = await channel.fetch_message(message_id)
##                        await message.delete()
##                    except:
##                        ...
                buffer = await s.get_activity_img()
                message = await message.channel.send(content = 'Activity graph. one **column** per challenge, **brighter** => more points for this challenge', file=discord.File(buffer, 'activity.png'))
                return
##                s.json_data.j['iLeaderboardImage'] = message.id
##                s.save_json()
##                return 'updated'
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
        players = deepcopy_nostring(players) # YES!
        lChallenges = list(s.json_data.list_of_challenges())
        dMaxPoints = {}
        for p in players:
            # get submissions matrix
            p['aSubmissions'] = []
            for ch in lChallenges:
                points = sum(float(x.get('iPoints', 0)) for x in s.json_data.j['aSubmission']
                             if x.get('iUserID') == p.get('iID') and x.get('sChallengeName') == ch)
                if dMaxPoints.get(ch, 0) < points:
                    dMaxPoints[ch] = points # max points for challenge
                p['aSubmissions'].append((ch, points))

            #get avatar     
            try:   
                user_id = p.get('iID', None)
                user = await s.client.fetch_user(user_id)
                AVATAR_SIZE = 128
                avatar_asset = user.avatar_url_as(format='png', size=AVATAR_SIZE)
                user_avatar = io.BytesIO(await avatar_asset.read())
            except Exception as e:
                if DEBUG:
                    raise e
                else:
                    print(e)
                user_avatar = None
            p['avatar'] = user_avatar
        buffer = rankDisplay.create_activity_card(players, dMaxPoints)
        return buffer
    
    
    async def update_lb_img(s, *args):
        try:
            s.json_data.calculate_rating()
            try:
                channel_id = s.leaderboard_channel_id
                if not channel_id:
                    return 'please configure `?set leaderboard`'
                channel = client.get_channel(channel_id)
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
            if player.get('bDisabled'):
                continue
            if limit:
                if player.get('iRank') > limit:
                    break
            user_id = player.get('iID', None)
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

            player = deepcopy(player)
            player['avatar'] = user_avatar
            data.append(player)
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
        buffer = await s.get_top_img(limit)
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
                              ('?rank', 'your rank; `?rank @user` to get @user rank', s.rank_img),
                              ('?top', 'leaderboard; add number to limit positions `?top 3`', s.top_img),
                              ('?leaderboard', 'same as `?top`', s.top_img),
                              ('?activity', 'displays activity of players', s.activity_img),
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

sm = {}

@client.event
async def on_ready():
    for guild in client.guilds:
        if DEBUG_CH:
            if guild.id != DEBUG_CH:
                continue
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
    if DEBUG_CH:
        if message.guild.id != DEBUG_CH:
            return
    if message.author.bot:
        return
    if message.author == client.user:
        return
    await sm[message.guild.id](message)

print('ready, steady, go')
client.run(TOKEN)

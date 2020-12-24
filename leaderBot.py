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

from jsonReader import json_class, beautify
import rankDisplay

import json

check_role = False
check_channel = True

load_dotenv()
TOKEN   = os.getenv('DISCORD_TOKEN')
ROLE    = os.getenv('DISCORD_ROLE')
CHANNEL = os.getenv('DISCORD_CHANNEL')
DEBUG_CH = os.getenv('DISCORD_DEBUG_CH')
ADMIN = os.getenv('DISCORD_ADMIN')
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

class Mutex:
    ''' returns False if lock is free '''
    def __init__(s, *args):
        s.__lock = False
        
    @property
    def lock(s):
        ''' returns False if lock is free '''
        if s.__lock:
            return True
        else:
            s.__lock = True
            return False
        
    @lock.setter
    def lock(s, _):
        s.__lock = False

class leaderBot_class():
    guild_id = None
    leaderboard_channel_id = None
    leaderboard_message_id = None
    json_path = None
    json_data = None

    json_lock = Mutex()

    client = None

    ksp_hints = None
    avatar_cache={}
    
    ## assistant functions

    @staticmethod
    def get_int (string):
        try:
            return int(''.join(filter(str.isdigit, string)))
        except:
            return None
    
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
        
    async def ask_for_reaction(s, message, **kwargs):
        '''kwargs: mode ('yn' or 'ynd'), timeout, return_user (True/False)'''
        '''returns None if timeout, 'yes', 'no', 'delete' '''
        yes = '✅'
        stop = '⛔'
        x = '❌'

        mode = kwargs.get('mode', 'yn')
        timeout = kwargs.get('timeout')
        author_id = kwargs.get('author_id')
        
        if mode == 'ynd':
            arr = {yes:'yes', stop:'no', x:'delete'}
        else:
            arr = {yes:'yes', x:'no'}

        for i in arr:
            await message.add_reaction(i)
        
        def check(reaction, user):
            return ((reaction.message.id == message.id) and
                    (s.client.user == message.author) and
                    (str(reaction.emoji) in arr) and
                    (reaction.count > 1) and
                    ((not author_id) or (author_id == user.id)))
        
        try:
            reaction, user = await client.wait_for('reaction_add', check=check, timeout=timeout)
        except asyncio.TimeoutError:
            await message.clear_reactions()
            await message.channel.send(f'`timeout {timeout}s`')
            return (None, None)
        except Exception as e:
            await message.clear_reactions()
            if DEBUG:
                raise (e)
            else:
                print(e)
                return (None, None)
                
        await message.clear_reactions()
        return arr[reaction.emoji], user

                    
    async def get_message(s, ch_id, m_id):
        try:
            channel = s.client.get_channel(ch_id)
            return await channel.fetch_message(m_id)
        except Exception as e:
            if DEBUG:
                print(e)
            return

    async def get_avatar(s, user_id, update=False, user = None):

        if user:
            user_id = user.id

        if not update and user_id in s.avatar_cache:
            avatar_asset = s.avatar_cache[user_id].get('avatar_asset')
            if avatar_asset:
                return avatar_asset

        if not user:
            user = await s.client.fetch_user(user_id)

        # if in cache and hash not changed return saved thingy
        if user_id in s.avatar_cache:
            if user.avatar == s.avatar_cache[user_id].get('hash'):
                avatar_asset = s.avatar_cache[user_id].get('avatar_asset')
                if avatar_asset:
                    return avatar_asset
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
        msg = None
        while content:
            msg = await channel.send(content[:2000])
            content = content[2000:]
        return msg
        
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
        if s.json_lock.lock:
            await message.channel.send('`json locked. Retry later`')
            return
        await message.channel.send('Please send me your json!')

        message = await s.wait_response(message)
        if not message:
            s.json_lock.lock = None
            return
        if message.attachments:
            test = message.attachments[0].filename
            try:
                await message.attachments[0].save(fp=s.json_path)
                s.open_json()
                await s.update_all(message, ignore_lock=True)
                s.json_lock.lock = None
            except Exception as e:
                s.json_lock.lock = None
                if DEBUG:
                    raise e
                else:
                    print(e)
                return 'failed to save'
            s.json_lock.lock = None
            return test + ' received and saved'
        s.json_lock.lock = None
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

    def get_used_challenges(s, sChallengeName):
        active_challenges = 3
        last_challenges = []
        last_challenge_types = set()
        used_challenge_types = set()
        
        for submission in s.json_data.j.get('aSubmission', [])[::-1]:
            last_challenges.append(submission['sChallengeName'])
            if len(last_challenges) > active_challenges:
                break
            last_challenge_types.add(submission['sChallengeTypeName'])

        for submission in s.json_data.j.get('aSubmission', []):
            if submission['sChallengeName'] == sChallengeName:
                used_challenge_types.add(submission['sChallengeTypeName'])
        return last_challenge_types, used_challenge_types

    async def ask_for_challenge_type(s, message, sChallengeName, save_json = False, **kwargs):
        ''' returns sChallengeTypeName, if new - creates'''
        if s.json_data.j.get('aChallengeType'):
            last, used = s.get_used_challenges(sChallengeName)
            # at first, short version of list
            if last | used: # maybe list is empty (fresh json?)
                accept_list = []
                response = 'Last active types (`>` = used in this challenge):'
                def create_list(full = False):
                    response = '```'
                    wide = 3, 15, 15, 10
                    response += f"\n {'#':>{wide[0]}} {'MODUS':<{wide[1]}}{'SCORE WINS':<{wide[2]}}{'MULTIPLIER':<{wide[3]}}```"
                    for i, chl in enumerate(s.json_data.j.get('aChallengeType', []), 1):
                        if full or (chl.get('sName') in (last | used)):
                            accept_list.append(str(i))
                            response += (f"```\n{'>' if (chl.get('sName') in used) else ' '}" +
                                         f"{i:>{wide[0]}} {chl.get('sNick', chl.get('sName')):<{wide[1]}}" +
                                         f"{('*higher*' if chl.get('bHigherScore') else 'lower'):<{wide[2]}}" +
                                         f"{beautify(chl.get('fMultiplier', 1)):<{wide[3]}}" +
                                         ('   place=score' if chl.get('bSpecial') else '') + '```')
                    return response
                    
                response += create_list()
                response += 'Enter number of existing type (e.g. `1`) or `0` to view all types / create new'

                await s.send(message.channel, response)
                message = await s.wait_response(message, author_id=kwargs.get('author_id')) # first wait response - add author_id in case start from reaction
                if not message:
                    return
                
                if message.content.strip() in accept_list:
                    try:
                        return s.json_data.j['aChallengeType'][int(message.content.strip())-1]['sName']
                    except:
                        await s.send(message.channel, '`wrong index`')
                
            # short list too short, try full list now
            response = 'All types (`>` = used in this challenge):'
            response += create_list(full = True)
            response += 'Enter number of existing type (e.g. `1`) or `0` to create new'
            
            await s.send(message.channel, response)
            message = await s.wait_response(message, author_id=kwargs.get('author_id'))
            if not message:
                return

            if message.content.strip() in accept_list:
                try:
                    return s.json_data.j['aChallengeType'][int(message.content.strip())-1]['sName']
                except:
                    await s.send(message.channel, '`wrong index`')
                     
        # new challenge type creation
        response = 'Create new type in format `modus_name lower/higher multiplier`'
        response += '\n `lower/higher` = which score wins, `multiplier` = points multiplier'
        response += '\n(e.g. `hard lower 3.14`)'
        response += '\n> *add optional parameter `=` at the end, for `place = score`*'  
        response += '\n> e.g for `higher` & points system `30`, `20`, `10`, score=`3`: player gets `30 x multiplier` points'
        await s.send(message.channel, response)
        while True:
            message = await s.wait_response(message, author_id=kwargs.get('author_id')) # first wait response - add author_id in case start from reaction
            if not message:
                return
            
            temp = message.content.strip().split(' ')
            sName = str(len(s.json_data.j.get('aChallengeType'))) + '_' + str(random.randint(1000, 9999))
            if len(temp) == 3:
                s.json_data.j['aChallengeType'].append({'sName':sName,
                                                        'sNick':temp[0],
                                                        'bHigherScore':temp[1][0] == 'h',
                                                        'fMultiplier':float(temp[2].replace(',','.'))})
                if save_json:
                    s.save_json()
                return sName
            elif (len(temp) == 4) and (temp[4] == '='):
                s.json_data.j['aChallengeType'].append({'sName':sName,
                                                        'sNick':temp[0],
                                                        'bHigherScore':temp[1][0] == 'h',
                                                        'fMultiplier':float(temp[2].replace(',','.')),
                                                        'bSpecial':True})
                if save_json:
                    s.save_json()
                return sName
            else:
                await s.send(message.channel, 'Wrong parameter count, try again or `cancel`')
                continue

    async def ask_for_user_id(s, message, no_creation=False, **kwargs):
        '''returns user_id or None if failed, creates user if new'''

        user_id = kwargs.get('user_id')
        while True:
            if not user_id:
                await s.send(message.channel, 'Please enter user (e.g. @best_user) or user id:')
                message = await s.wait_response(message, author_id=kwargs.get('author_id')) # first wait_response - if from react author_id supplied
                if not message:
                    return
            
            try:
                if not user_id:
                    user_id = s.get_int(message.content)
                user = await s.client.fetch_user(user_id)
                if user.bot:
                    await s.send(message.channel, "`No bots, please`")
                    if kwargs.get('ignore_bots'):
                        return
                    user_id = None
                    continue
                user_id = user.id
                player = s.json_data.find(s.json_data.j.get('aPlayer', []), iID=user_id)
                if player:
                    await s.send(message.channel,  '> Existing user')
                else:
                    if no_creation:
                        await s.send(message.channel, 'No submissions from user with this id found. Try again or `cancel`')
                        user_id = None
                        continue
                    await s.send(message.channel, '**New** user, cool!')
                    s.json_data.j['aPlayer'].append({'sName':user.name, 'iDiscriminator': user.discriminator,
                                                     'iID':user_id})
                return user_id
            except Exception as e:
                if kwargs.get('ignore_bots'):
                    return None
                await s.send(message.channel, 'No user with this id found. Try again or `cancel`')
##                if DEBUG:
##                    raise e
##                else:
##                    print(e)
                continue
        return

    async def get_points_for_channel(s, message):
        '''asks for points or saves new point systems. None if error'''
        while True:
            response = 'Available scoring systems:'
            # get all points in challenges
            aPoints = set()
            aPoints.add(s.json_data.aPoint)
            for ch in s.json_data.j.get('aChallenge', []):
                ap = ch.get('aPoints')
                if ap:
                    aPoints.add(tuple(sorted(ap, reverse=True)))
            aPoints = sorted(aPoints, reverse=True)
            for i, a in enumerate(aPoints, 1):
                a = ['{:g}'.format(float(x)) for x in a]
                response += '\n{:4}: `'.format(i) + '` `'.join(a) + '`'
            response += '\nEnter number (e.g. `1`), or new point sequence (e.g. `10 6 4 3.14 1`)'
            response += '\n> Enter `* 10` if all submissions should get `10` points'
            await s.send(message.channel, response)
            msg = await s.wait_response(message)
            if not msg:
                return
            ar = msg.content.strip().split(' ')
            if len(ar) == 1:
                try:
                    return aPoints[int(ar[0])-1]
                except:
                    await s.send(message.channel, '**Wrong index.** Try again or `cancel`')
                    continue
            try:
                if (len(ar) == 2) and (ar[0] == '*'):
                    return [float(ar[1])]
                return sorted([float(x) for x in ar], reverse=True)
            except Exception as e:
                await s.send(message.channel, '**Should be numbers!** like `20 10 3.14 2.71 1.41 1`')
                continue
        return

    async def set_challenge_channel(s, message, change_existing_channel=True, **kwargs):
        '''selection for challenge, and updating/creating of channel.'''
        '''Returns None in case of error or sChallengeName'''
        '''also defines points system & show/hide score in #winners channel'''
        if change_existing_channel:
            if s.json_lock.lock:
                await message.channel.send('`json locked. try again later`')
                return
        # challenges list
        if s.json_data.list_of_challenges():
            response = 'Past challenges: `' + '`, `'.join(s.json_data.list_of_challenges()) + '`'
        else:
            response = '**Time to create new challenge!**'
        response += '\nEnter challenge name (e.g. `42`)\n(if challenge not in the list, new challenge will be created)'
        await s.send(message.channel, response)
        # select challenge
        message = await s.wait_response(message, author_id=kwargs.get('author_id')) # first wait_response, author_id should be sent in case of start from reaction
        if not message:
            if change_existing_channel: s.json_lock.lock = None
            return
        sChallengeName = message.content
        if sChallengeName in s.json_data.list_of_challenges():
            await s.send(message.channel, '> Existing challenge')
            if not change_existing_channel:
                return sChallengeName 
        else:
            await s.send(message.channel, '**New** challenge, cool!')
            
        try:
            await s.send(message.channel, 'Select channel to post winners (e.g. `#winners-42`) or `*` for none')
            while True:
                msg_r = await s.wait_response(message)
                if not msg_r:
                    if change_existing_channel: s.json_lock.lock = None
                    return
                if msg_r.content != '*':
                    channel_id = s.get_int(msg_r.content)
                    channel = client.get_channel(channel_id)
                    if not channel:
                        await message.channel.send('wrong id, try again or `cancel`')
                        continue
                    msg = await channel.send('Here will be winners published')
                    message_id = msg.id
                    break
                else:
                    channel_id = 0
                    message_id = 0
                    break

            if not (sChallengeName in s.json_data.list_of_challenges()):
                aPoints = await s.get_points_for_channel(message)
                if not aPoints:
                    if change_existing_channel: s.json_lock.lock = None
                    return
            else:
                aPoints = s.json_data.find(s.json_data.j.get('aChallenge'), sName=sChallengeName).get('aPoints', [])
            if (len(aPoints) == 1) or (channel_id == 0):
                bShowScore = False
            else:
                msg = await message.channel.send('Show score for this challenge in `#winners`?')
                react, _ = await s.ask_for_reaction(msg, mode='yn', timeout=120, author_id=kwargs.get('author_id'))
                if not react:
                    if change_existing_channel: s.json_lock.lock = None
                    return
                bShowScore = react == 'yes'
                await message.channel.send('> show' if bShowScore else '> hide')
            
            if sChallengeName in s.json_data.list_of_challenges():
                sC = s.json_data.find(s.json_data.j['aChallenge'], sName=sChallengeName)
                sC['idChannel'] = channel_id
                sC['idMessage'] = message_id
                sC['bShowScore'] = bShowScore
            else:
                s.json_data.j['aChallenge'].append({'sName': sChallengeName,
                                                    'idChannel': channel_id,
                                                    'idMessage': message_id,
                                                    'bShowScore': bShowScore,
                                                    'aPoints': aPoints})
            await s.update_winners(sChallengeName=sChallengeName)
            if change_existing_channel:
                s.save_json()
                s.json_lock.lock = None
            return ('Done: ' if change_existing_channel else '') + sChallengeName 
        except Exception as e:
            s.json_lock.lock = None
            if DEBUG:
                raise e
            else:
                print(e)
            return None
        return

    async def add_submission(s, message, **kwargs):
        if s.json_lock.lock:
            await s.send(message.channel, '`json is locked. try again later`')
            return
        await s.send(message.channel, '__Type `cancel` at any time to... wait for it... *cancel*__\nFor which challenge is this submission?')

        # if started from react - author_id for wait_for
        author_id = kwargs.get('author_id')
        ret_points = kwargs.get('ret_points')

        # select challenge
        sChallengeName = kwargs.get('sChallengeName')
        if sChallengeName:
            embed = discord.Embed()
            embed.add_field(name='Auto challenge name', value=f'Challenge **{sChallengeName}**')
            msg = await message.channel.send(content='Correct?', embed=embed)
            react, _ = await s.ask_for_reaction(msg, mode='yn', timeout=120, author_id=author_id)
            if react is None:
                await message.channel.send('`changes reverted`')
                s.open_json()
                s.json_lock.lock = None
                return
            if react != 'yes':
                sChallengeName = None
                     
        if (not sChallengeName) or (not (sChallengeName in s.json_data.list_of_challenges())):
            sChallengeName = await s.set_challenge_channel(message, change_existing_channel=False, author_id=author_id)
            if not sChallengeName:
                await message.channel.send('`changes reverted`')
                s.open_json()
                s.json_lock.lock = None
                return
            
        # select user
        user_id = kwargs.get('iID')
        if user_id:
            author_name = kwargs.get('author_name')
            embed = discord.Embed()
            embed.add_field(name='Auto user', value=f'**@{author_name}** id: **{user_id}**')
            msg = await message.channel.send(content='Correct?', embed=embed)
            react, _ = await s.ask_for_reaction(msg, mode='yn', timeout=120, author_id=author_id)
            if react is None:
                await message.channel.send('`changes reverted`')
                s.open_json()
                s.json_lock.lock = None
                return
            
            if react != 'yes':
                user_id = None
    
        if not (user_id and s.json_data.find(s.json_data.j.get('aPlayer', []), iID=user_id)):
            user_id = await s.ask_for_user_id(message, author_id=author_id, user_id=user_id)
            if not user_id:
                await message.channel.send('`changes reverted`')
                s.open_json()
                s.json_lock.lock = None
                return
            
        # select challenge type
        sChallengeTypeName = await s.ask_for_challenge_type(message, sChallengeName, author_id=author_id)
        if not sChallengeTypeName:
            await message.channel.send('`changes reverted`')
            s.open_json()
            s.json_lock.lock = None
            return
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

            all_gets_same_score = len(s.json_data.find(s.json_data.j.get('aChallenge'), sName=sChallengeName).get('aPoints', [])) == 1
                
            if not all_gets_same_score:
                await s.send(message.channel, 'Enter score (e.g. `3.14`):')
                msg = await s.wait_response(message, author_id=author_id)
                if not message:
                    await message.channel.send('`changes reverted`')
                    s.open_json()
                    s.json_lock.lock = None
                    return
                fScore = float(msg.content)
            else:
                fScore = 1.0


            # we are ready! last confirmation
            author_name = kwargs.get('author_name')
            if (not author_name) or (user_id != kwargs.get('iID')):
                author_name = (await s.client.fetch_user(user_id)).name

            newPlayer = (0 == len([1 for x in s.json_data.j['aSubmission'] if x.get('iUserID') == user_id]))
            sTypeName = s.json_data.find(s.json_data.j['aChallengeType'], sName=sChallengeTypeName).get('sNick')
                
            embed = discord.Embed(title='Last check')
            embed.add_field(name=('__NEW__ ' if newPlayer else '') + 'Player', value=f"**@{author_name}**\nid: {user_id}", inline=False)
            embed.add_field(name='Challenge', value=sChallengeName)
            embed.add_field(name='Modus', value=sTypeName)
            if not all_gets_same_score:
                embed.add_field(name='Score', value='**' + beautify(fScore) + '**; ' + beautify(iSubmissionId + 1) + '. try')
                
            message_c = await message.channel.send(embed=embed)
            react, _ = await s.ask_for_reaction(message_c, mode='yn', timeout=120, author_id=author_id)
            if react != 'yes':
                await message.channel.send('`changes reverted`')
                s.open_json()
                s.json_lock.lock = None
                return
            
            # green light, let's add submission!    
            s.json_data.j['aSubmission'].append({'iUserID':user_id,
                                                 'sChallengeName':sChallengeName,
                                                 'sChallengeTypeName':sChallengeTypeName,
                                                 'iSubmissionId':iSubmissionId,
                                                 'fScore':fScore})

            response = await s.update_all(message, ignore_lock=True)
            s.json_lock.lock = None
            await s.send(message.channel, response)
            if ret_points:
                rSubmission = s.json_data.find(s.json_data.j['aSubmission'], {'iUserID':user_id,
                                                                              'sChallengeName':sChallengeName,
                                                                              'sChallengeTypeName':sChallengeTypeName,
                                                                              'iSubmissionId':iSubmissionId,
                                                                              'fScore':fScore})
                return rSubmission, newPlayer, sTypeName
            return
        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            await s.send(message.channel, 'Something really wrong')
            await message.channel.send('`changes reverted`')
            s.open_json()
            s.json_lock.lock = None
            return
        
        s.json_lock.lock = None
        return
    
    async def add_points(s, message):
        if s.json_lock.lock:
            await s.send(message.channel, '`json locked. try again later`')
            return
        await message.channel.send('Enter users (@best_player) or id, separate multiple users with *space*')
        msg = await s.wait_response(message)
        if not msg:
            s.json_lock.lock = None
            return
        user_ids = msg.content.strip().split()
        user_ids = set([s.get_int(x) for x in user_ids])
        user_ids.discard(None)
        
        user_id_s = set([(await s.ask_for_user_id(message, user_id = u, ignore_bots=True)) for u in user_ids])
        user_id_s.discard(None)
        
        if not user_id_s:
            await s.send(message.channel, 'No valid @users found')
            s.json_lock.lock = None
            return
        await s.send(message.channel, 'How many points? (e.g. `2.5`)')
        while True:
            msg_r = await s.wait_response(message)
            if not msg_r:
                await message.channel.send('`reverted changes`')
                s.open_json()
                s.json_lock.lock = None
                return
            try:
                points = float(msg_r.content)
                break
            except:
                await message.channel.send('Please enter valid number or `cancel`')
                continue
        try:
            for user_id in user_id_s:
                player = s.json_data.find(s.json_data.j.get('aPlayer', []), iID=user_id)
                player['iStaticPoints'] = player.get('iStaticPoints', 0) + points
            await message.channel.send('*updating...*')
            response = await s.update_lb()
            s.save_json()
            s.json_lock.lock = None
            return response
        except Exception as e:
            await message.channel.send('`reverted changes`')
            s.open_json()
            s.json_lock.lock = None
            if DEBUG:
                raise e
            else:
                print(e)
            return 'something wrong'

    async def set_lb(s, message):
        if s.json_lock.lock:
            await s.send(message.channel, '`json locked. try again later`')
            return
        await s.send(message.channel, 'In which channel should be posted leaderboard?')
        while True:
            message_r = await s.wait_response(message)
            if not message_r:
                s.json_lock.lock = None
                return
            try:
                channel_id = s.get_int(message_r.content)
                channel = client.get_channel(channel_id)
                msg = await channel.send('Here will be published leaderboard')
            except:
                await s.send(message.channel, 'channel not found. Try again or `cancel`')
                continue
                
            s.leaderboard_channel_id = channel.id
            s.leaderboard_message_id = msg.id
            s.json_data.set_lb_message(s.leaderboard_channel_id, s.leaderboard_message_id)
            await s.update_lb()
            s.save_json()
            s.json_lock.lock = None
            return 'placeholder created'

    async def set_mention_ch(s, message):
        if s.json_lock.lock:
            await s.send(message.channel, '`json locked. try again later`')
            return
        await s.send(message.channel, f'In which channel should be posted <@{client.user.id}> mentions?')
        while True:
            msg = await s.wait_response(message)
            if not msg:
                s.json_lock.lock = None
                return
            try:
                channel_id = s.get_int(msg.content)
                channel = client.get_channel(channel_id)
                if not channel:
                    await s.send(message.channel, 'wrong channel. try again or `cancel`')
                    continue
            except:
                await s.send(message.channel, 'wrong channel. try again or `cancel`')
                continue
            
            if channel:
                s.json_data.j['iMentionsChannel'] = channel.id
                
                text = ''
                await message.channel.send('Who should be mentioned? Enter `@users`, `@roles` or `*` for empty')
                msg = await s.wait_response(message)
                if not msg:
                    s.json_lock.lock = None
                    return
                if msg.content != '*':
                    text = str(msg.content)
                s.json_data.j['iMentionsText'] = text
                
                text = ''
                await message.channel.send('In which channels bot should **react** to mentions (separate multiple with *space*)?\n' +
                                           'e.g. `miss test` for sub**miss**ion, **miss**ions and **test**\n' +
                                           'or `*` for no filter')
                msg = await s.wait_response(message)
                if not msg:
                    s.json_lock.lock = None
                    return
                if msg.content != '*':
                    text = str(msg.content)
                s.json_data.j['iMentionsChIncluded'] = text
                
                text = ''
                await message.channel.send('In which channels bot should **ignore** mentions (separate multiple with *space*)?\n' +
                                           'e.g. `admin anno` for **admin** and **anno**ucements\n' +
                                           'or `*` for no filter')
                msg = await s.wait_response(message)
                if not msg:
                    s.json_lock.lock = None
                    return
                if msg.content != '*':
                    text = str(msg.content)
                s.json_data.j['iMentionsChExcluded'] = text
                s.save_json()
                s.json_lock.lock = None
            else:
                s.json_lock.lock = None
                return "channel doesn't exist"
            
        s.json_lock.lock = None
        return


    async def update_usernames(s, *args):
        async def update_player(player):
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
        await asyncio.gather(*(asyncio.ensure_future(update_player(player)) for player in s.json_data.j.get('aPlayer', [])))
        s.save_json()
        return

    
    async def update_winners(s, *args, sChallengeName=None):
        if sChallengeName:
            sub = [sChallengeName]
        else:
            sub = s.json_data.list_of_challenges()

        async def update_win(sub):
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

                # remove entries with empty idChannel
                if (not (idChannel is None)) and (not idChannel):
                    del challenge['idChannel']
                    del challenge['idMessage']
                    
                if idChannel and idMessage:
                    msg = await s.get_message(idChannel, idMessage)
                    if msg:
                        await msg.edit(content='', embed=embed)
                    else:
                        del challenge['idChannel']
                        del challenge['idMessage']
            except Exception as e:
                if DEBUG:
                    raise e
                else:
                    print('update_winners\n', e)
                    
        await asyncio.gather(*(asyncio.ensure_future(update_win(sub)) for sub in sub))
        return
                    
    
    async def update_lb(s, *args):
        try:
            await s.update_usernames() # update usernames & avatars
            s.json_data.calculate_rating()
            await s.post()

            name, value = s.json_data.result_leaderboard().split('\n', 1)
            
            embed = discord.Embed()
            embed.add_field(name=name, value=value)
            if not (s.leaderboard_channel_id and s.leaderboard_message_id):
                return '`?set leaderboard` required'
            msg = await s.get_message(s.leaderboard_channel_id, s.leaderboard_message_id)
            if not msg:
                return '`?set leaderboard` required'
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

    async def update_all(s, message, ignore_lock=False):
        if not ignore_lock:
            if s.json_lock.lock:
                await s.send(message.channel, '`json locked. try again later`')
                return
        await s.send(message.channel, '*updating...*')
        await s.update_roles(message)
        response = await s.update_lb()
        await s.update_winners()
        s.save_json()
        if not ignore_lock:
            s.json_lock.lock = None
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

    async def rank_img(s, msg, **kwargs):
        user_id = kwargs.get('user_id')
        # find user.id and user
        if not user_id:
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
        player = s.json_data.find(s.json_data.j.get('aPlayer', []), iID=user_id)
        if player:
            rank = player.get('iRank', None)
            points = player.get('iPoints', None)
        if not (player and rank and points):
            if kwargs.get('user_id'):
                return
            return 'You need to earn some points. Submit some challenges!'

        # find max points
        max_points = max(player.get('iPoints') for player in s.json_data.j.get('aPlayer', []))

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
                                              len(s.json_data.j.get('aPlayer', [])))
        if kwargs.get('user_id'):
            return buffer
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
        players = sorted(s.json_data.j.get('aPlayer', []), key=lambda x: float(x.get('iPoints')), reverse=True)
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
                if not buffer:
                    return
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
                if not buffer:
                    return
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
        players = sorted(s.json_data.j.get('aPlayer', []), key=lambda x: float(x.get('iPoints')), reverse=True)
        if not players:
            return
        data = []

        for player in players:
            if player.get('bDisabled') or (limit == 0 and (float(player.get('iStaticPoints', 0)) - float(player.get('iPoints', 0))) == 0):
                continue
            if limit:
                if player.get('iRank') > limit:
                    break

            avatar = await s.get_avatar(player['iID'])

            data.append({'iRank':player.get('iRank'),
                         'sName':player.get('sName'),
                         'iDiscriminator':player.get('iDiscriminator'),
                         'iPoints':player.get('iPoints'),
                         'avatar':avatar
                         })
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
            item['avatar'] = await s.get_avatar(item.get('iID'))
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
        if s.json_lock.lock:
            await msg.channel.send('`json locked. try again later`')
            return
        data = msg.content.strip().split(' ')
        if len(data) == 1:
            try:
                del s.json_data.j['sPOSTURL']
            except:
                s.json_lock.lock = None
                return 'No Auto-POST URL found'
            s.json_lock.lock = None
            return 'Auto-POST URL deleted'
        else:
            s.json_data.j['sPOSTURL'] = data[1]
            s.save_json()
            s.json_lock.lock = None
            return 'Auto-POST URL updated'

    async def disable(s, msg):
        if s.json_lock.lock:
            await msg.channel.send('`json locked. try again later`')
            return
        await s.get_top(msg, full_list=True)
        user_id = await s.ask_for_user_id(msg, no_creation=True)
        if not user_id:
            s.json_lock.lock = None
            return
        s.json_data.find(s.json_data.j.get('aPlayer', []), iID=user_id)['bDisabled']=True
        response =  await s.update_all(msg, ignore_lock = True)
        s.json_lock.lock = None
        await msg.channel.send('Disabled. If needed `?update all`')

    async def enable(s, msg):
        if s.json_lock.lock:
            await msg.channel.send('`json locked. try again later`')
            return
        response = 'Disabled players:'
        for p in s.json_data.j.get('aPlayer', []):
            if p.get('bDisabled'):
                response += f'\n<@{p.get("iID")}>'
        response += '\n**Who should be reenabled?**'
        await msg.channel.send(response)
        user_id = await s.ask_for_user_id(msg, no_creation=True)
        if not user_id:
            s.json_lock.lock = None
            return
        s.json_data.find(s.json_data.j.get('aPlayer', []), iID=user_id)['bDisabled']=False
        response =  await s.update_all(msg, ignore_lock = True)
        s.json_lock.lock = None
        await msg.channel.send('Enabled')

    async def ksp(s, *args):
        if not s.ksp_hints:
            s.ksp_hints = open("ksp.txt").readlines()
        return random.choice(s.ksp_hints)[:-1]

    async def ping(s, *args):
        return 'Pong! {}ms'.format(int(s.client.latency*1000))

    async def unlock(s, *args):
        response = 'Locked -> Unlocked' if s.json_lock.lock else 'Unlocked -> Unlocked'
        s.json_lock.lock = None
        return response

    async def voting(s, message):
        create_new_vote = 'voting-new' in message.content.lower().strip()
        new_message = []
        emojis = []
        special_emojis={':coolrocket:':'732098507137220718 '}
        for a in message.content.split(maxsplit=1)[1].splitlines():
            if a.split()[0] in special_emojis:
                a = a.replace(a.split()[0], special_emojis[a.split()[0]])
            if a:
                code = a.split()[0].split('>', 1)[0].split(':')[-1]
                if code.isdecimal():
                    try:
                        emoji = s.client.get_emoji(int(code))
                        if emoji:
                            create_new_vote = create_new_vote or emoji.animated
                            a = a.replace(a.split()[0], f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>")
                            new_message.append(a)
                            emojis.append(emoji)
                            continue
                    except:
                        ...
                emojis.append(a[0])
            new_message.append(a)
            
        if create_new_vote:
            msg = await message.channel.send('\n'.join(new_message))

            # it is not visible in audit, so...
            if True:
                # check if channel exists
                channel_id = s.json_data.j.get('iMentionsChannel')
                if channel_id:
                    try:
                        channel = client.get_channel(channel_id)
                        if not channel:
                            raise
                        embed = discord.Embed(title='New anonimised voting!')
                        embed.add_field(name='user', value=f"<@{message.author.id}>")
                        embed.add_field(name='voting', value=f"[jump]({msg.jump_url})")
                        embed.add_field(name='original text', value=f"{message.content}")
                        await channel.send(embed = embed)
                    except Exception as e:
                        ...

            try:
                await message.delete()
            except:
                ...
            message = msg
            
        for emoji in emojis:
            try:
                await message.add_reaction(emoji)
            except:
                ...
        return

    async def update_roles(s, message):
        try:
            role_int = s.json_data.j['aRole']['iRole']
            act_int = s.json_data.j['aRole']['iActive']
            old_role_int = s.json_data.j['aRole'].get('iOldRole')
            mem_list = s.json_data.j['aRole']['aMembers']
            role = message.guild.get_role(role_int)
            if not old_role_int:
                old_role = message.guild.get_role(old_role_int)
            else:
                old_role = None
            if not role: raise
        except Exception as e:
            if DEBUG:
                raise e
            else:
                print(e)
            return

        active_challenges = [ch.get('sName') for ch in s.json_data.j.get('aChallenge', [])[:-act_int-1:-1]]
        active_members = set([sub.get('iUserID') for sub in s.json_data.j.get('aSubmission') if sub.get('sChallengeName') in active_challenges])
        active_members.discard(None)

        # get list to clean roles
        if old_role and old_role != role:
            rem_set = set(mem_list[::])
        else:
            old_role = role
            rem_set = set([mem for mem in mem_list if (not (mem in active_members))])
        try:
            del s.json_data.j['aRole']['iOldRole']
        except:
            ...
            
        # get list to set role
        add_set = active_members - (set(mem_list) - rem_set)
        s.json_data.j['aRole']['aMembers'] = list(active_members)
        
        # async update roles
        async def update_role(message, user_id, role, add_rem):
            member = await message.guild.fetch_member(user_id)
            try:
                if add_rem:
                    await member.add_roles(role)
                else:
                    await member.remove_roles(role)
            except Exception as e:
                if DEBUG:
                    raise e
                else:
                    print(e)
            
        await asyncio.gather(*(*(asyncio.ensure_future(update_role(message, user_id, role, True)) for user_id in add_set),
                               *(asyncio.ensure_future(update_role(message, user_id, old_role, False)) for user_id in rem_set)))
        return

        
        

    async def set_role(s, message):
        if s.json_lock.lock:
            await message.channel.send('`json locked. try again later`')
            return
        await message.channel.send('How many last challenges counted as active?')
        while True:
            msg_c = await s.wait_response(message)
            if not msg_c:
                s.json_lock.lock = None
                return
            try:
                act_int = int(msg_c.content)
                if act_int == 0:
                    break
                if not act_int:
                    raise
                break
            except:
                await message.channel.send('Please enter number, like `3`')
                continue
        
        await message.channel.send('Enter the @role or role_id which will be assigned to active players')
        while True:
            msg_c = await s.wait_response(message)
            if not msg_c:
                s.json_lock.lock = None
                return
            try:
                role_int = s.get_int(msg_c.content)
                role = message.guild.get_role(role_int)
                if not role:
                    raise
                break
            except:
                await message.channel.send('Wrong id or @role. Try again or `cancel`')
                continue
        # we have a role!
        await message.channel.send('*updating...*')
        if not s.json_data.j.get('aRole'):
            s.json_data.j['aRole'] = {}
            s.json_data.j['aRole']['aMembers'] = []
        s.json_data.j['aRole']['iOldRole'] = s.json_data.j['aRole'].get('iRole')
        s.json_data.j['aRole']['iRole'] = role_int
        s.json_data.j['aRole']['iActive'] = act_int
        await s.update_roles(message)
        s.save_json()
        await message.channel.send('Role saved.')
        s.json_lock.lock = None
        return

    async def mentioned(s, message):
        # will be supported in 1.6 await message.channel.send('Okay', reference=message)

        # check if channel exists
        channel_id = s.json_data.j.get('iMentionsChannel')
        text = s.json_data.j.get('iMentionsText', '')
        
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
        msg_confirmation = await message.channel.send(f'<@{user_id}> {random.choice(part_1)}. {random.choice(part_2)}')

        # try to find the challenge
        category_id = message.channel.category_id
        challenge = {}
        for ch in s.json_data.j.get('aChallenge', []):
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
        await msg.pin(reason='new challenge submission')
        
        while True:   
            response = None
            reaction, user = await s.ask_for_reaction(msg, mode='ynd')

            if reaction == 'delete':
                message_r = await channel.send('Really delete this and confirmation message?')
                reaction, user = await s.ask_for_reaction(message_r, mode='yn', timeout=30, author_id=user.id)
                await message_r.delete()
                if reaction == 'yes':
                    await msg.unpin(reason='new challenge submission - ready')
                    await msg_confirmation.delete()
                    await msg.delete()
                    response = '`deleted`'
                    break
                else:
                    continue
            elif reaction == 'yes':
                try:
                    rSubmission, newPlayer, sTypeName = await s.add_submission(msg,
                                                                               iID=message.author.id,
                                                                               author_name=message.author.display_name,
                                                                               sChallengeName=ch_name,
                                                                               author_id=user.id,
                                                                               ret_points=True)
                    await msg.unpin(reason='new challenge submission - ready')
                except:
                    continue
                
                modus = s.json_data.find(s.json_data.j['aChallengeType'], sName=rSubmission.get('sChallengeTypeName')).get('sNick')
                win_ch_id = s.json_data.find(s.json_data.j['aChallenge'], sName=rSubmission.get('sChallengeName')).get('idChannel')

                user_id = rSubmission.get('iUserID')

                leaderboard_ch = f"<#{s.leaderboard_channel_id}>" if s.leaderboard_channel_id else 'leaderboard'
                winners_ch = f"<#{win_ch_id}>" if win_ch_id else 'challenge winners'
                newPlayerWelcome = '\n:tada: **Welcome to the challenges by the way! :tada:**' if newPlayer else ''
                iPoints = rSubmission.get('iPoints')
                if iPoints and iPoints > 0:
                    buffer = await s.rank_img(msg, user_id=user_id)
                    message_r = await message.channel.send(f"<@{user_id}>, **yay!** You got " +
                                                           f"**{beautify(iPoints)}** points " +
                                                           f"and the **{rSubmission.get('iRank')}**{s.json_data.suffix(rSubmission.get('iRank'))} place "+
                                                           f"in modus **{modus}**." +
                                                           f"\n{winners_ch} and {leaderboard_ch} are updated" +
                                                           newPlayerWelcome +
                                                           f"\nYour actual rank:", file=discord.File(buffer, 'rank.png'))
                else:
                    message_r = await message.channel.send(f"<@{user_id}> your submission counted, but you got no points :pensive: " +
                                                           f"\nCheck {winners_ch} and {leaderboard_ch}" +
                                                           newPlayerWelcome)
                embed = discord.Embed()
                embed.add_field(name='Accept message sent', value=f'[jump]({message_r.jump_url})')
                await channel.send(embed=embed)
                break
            elif reaction == 'no':
                message_r = await channel.send('Please enter the reason, why this submission is declined, or `*` for no message')
                message_r = await s.wait_response(message_r, timeout=120, author_id=user.id)
                if message_r is None:
                    await channel.send('Timeout.. Try again!')
                    continue
                await msg.unpin(reason='new challenge submission - ready')
                if message_r.content == '*':
                    response = 'Okay, no message sent'
                    break
                message_r = await message.channel.send(f'<@{message.author.id}>, *sorry, your submission is declined*\n{message_r.content}')
                embed = discord.Embed()
                embed.add_field(name='Decline message sent', value=f'[jump]({message_r.jump_url})')
                await channel.send(embed=embed)
                break
            else:
                print('mentioned - None reaction')
                await msg.unpin(reason='new challenge submission - ready')
                return  # sommething went really bad here

        if response:
            await s.send(msg.channel, response)
            
        return

                
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

    @staticmethod
    async def dm(client, message):
        try:
            admin_id = int(ADMIN)
            admin = await client.fetch_user(admin_id)
            if not admin_id:
                raise
        except:
            return
        async def get_files(message):
            if not message.attachments:
                return
            files = []
            for m in message.attachments:
                buffer = io.BytesIO(await m.read())
                buffer.seek(0)
                files.append(discord.File(buffer, m.filename))
            return files
                
        if (message.author != admin) or ('super!mega!test' in message.content):
            await admin.send(f"<@{message.author.id}>\n" + message.content, files=(await get_files(message)))
            await message.channel.send('`message sent`')
        else:
            try:
                user_id = leaderBot_class.get_int(message.content.split()[0])
                user = await client.fetch_user(user_id)
                if not user:
                    raise Exception('no user')
            except Exception as e:
                await message.channel.send('Message should start with @user or id!')
                return
            try:
                try:
                    content = message.content.split(maxsplit=1)[1]
                except:
                    content = '*'
                await user.send(content, files=(await get_files(message)))
                await message.channel.send(f'`message sent` to <@{user.id}>')
            except Exception as e:
                await message.channel.send('> ' + str(e))
        return
            
    def create_help (s, *args):
        s.user_commands = (
                              ('?help', 'prints this message', s.user_help),
                              ('?rank', 'your rank; `?rank @user` to get @user rank', s.rank_img),
                              ('?top', 'leaderboard; add number to limit positions `?top 3`', s.top_img),
                              ('?leaderboard', 'same as `?top`', s.top_img),
                              ('?activity', 'activity rank; add number to limit positions `?activity 3`', s.act_img),
                              ('?ksp', 'random ksp loading hint', s.ksp),
                              ('?voting', "all emojis at line start added as reactions *`voting-new` to replace your message*", s.voting),
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
                      ('?unlock', "don't use! debug feature", s.unlock),
                      ('?set role', 'set @role for active winners', s.set_role),
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
            s.save_json()
            print('no json found - empty created')

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
    
    if message.guild:
        await leaderBot[message.guild.id](message)
    else:
        #dm message
        await leaderBot_class.dm(client, message)

print('ready, steady, go')
client.run(TOKEN)

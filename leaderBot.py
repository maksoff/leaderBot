# maksoff - KSP leaderbot (automagically calculates the rating and etc.)

# TODO: #
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
from blueLetters import replace_letters
import rankDisplay

import json

import traceback

scanned_messages = 0
scanned_reactions = 0
start_time = None

check_role = False
check_channel = True

load_dotenv()
TOKEN   = os.getenv('DISCORD_TOKEN')
ROLE    = os.getenv('DISCORD_ROLE')
CHANNEL = os.getenv('DISCORD_CHANNEL')
DEBUG_CH = os.getenv('DISCORD_DEBUG_CH')
ADMIN = os.getenv('DISCORD_ADMIN')
KSP_GUILDS = os.getenv('DISCORD_KSP_GUILDS')
try:
    ksp_guilds = KSP_GUILDS.split()
    ksp_guilds = [int(k) for k in ksp_guilds]
except:
    ksp_guilds = []
    
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
    elif type(temp) is bool:
        return temp
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

def dfind(dicts, *key_val, **kwargs):
    if len(key_val) == 1 or kwargs:
        if key_val: key_val = key_val[0]
        else: key_val = kwargs
        for item in dicts:
            for k, v in key_val.items():
                if item.get(k, None) != v:
                    break
            else:
                return item
        return None        
    else:
        key, val = key_val
        return next((item for item in dicts if item[key] == val), None)

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

    prefix = 'lb?'

    last_lb_users = []

    
    special_emojis = {':coolrocket:':'732098507137220718'}
    special_emojis_full = {':coolrocket:':'<a:CoolChallengeAccepted:732098507137220718>'}
    
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
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('wait response:', e)
            return

    @staticmethod
    async def add_ynd_reactions(message, **kwargs):
        '''kwargs: mode ('yn' or 'ynd')'''
        yes = '✅'
        stop = '⛔'
        x = '❌'

        mode = kwargs.get('mode', 'yn')
        
        if mode == 'ynd':
            arr = {yes:'yes', stop:'no', x:'delete'}
        else:
            arr = {yes:'yes', x:'no'}

        for i in arr:
            await message.add_reaction(i)
        return

    @staticmethod
    def check_reaction(emoji, **kwargs):
        '''kwargs: mode ('yn' or 'ynd')'''
        yes = '✅'
        stop = '⛔'
        x = '❌'

        mode = kwargs.get('mode', 'yn')
        
        if mode == 'ynd':
            arr = {yes:'yes', stop:'no', x:'delete'}
        else:
            arr = {yes:'yes', x:'no'}
        return arr.get(emoji.name)
        
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
            traceback.print_exc()
            if DEBUG:
                raise (e)
            else:
                print('ask for reaction:', e)
                return (None, None)
                
        await message.clear_reactions()
        return arr.get(reaction.emoji), user

                    
    async def get_message(s, ch_id, m_id):
        try:
            channel = await s.client.fetch_channel(ch_id)
            return await channel.fetch_message(m_id)
        except Exception as e:
            if DEBUG:
                traceback.print_exc()
                print('get_messsage:', e)
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
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('get_avatar:', e)
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
                traceback.print_exc()
                if DEBUG:
                    raise e
                else:
                    print('open json:', e)
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
        
        if not message.attachments:
            await message.channel.send('Please send me your json! Or `cancel`')

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
                traceback.print_exc()
                if DEBUG:
                    raise e
                else:
                    print('json imp:', e)
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
    
    async def help(s, message):
        if message.channel.name == CHANNEL:
            embed = discord.Embed(title = 'Hello! This bot helps to update the leaderboard.')
            value = ''
            limit = 1000
            first = True
            for n, t, _ in s.commands:
                if value:
                    value += '\n'
                add_val = f'`{n}` - {t}'
                if len(value + add_val) > limit:
                    if first:
                        name = f'Use these commands (in `#{CHANNEL}` channel!)'
                        first = False
                    else:
                        name = '\u200b'
                    embed.add_field(name = name,
                                    value = value,
                                    inline=False)
                    value = ''
                else:
                    value += add_val

            if value:
                if first:
                    name = f'Use these commands (in `#{CHANNEL}` channel!)'
                else:
                    name = '\u200b'
                embed.add_field(name = name,
                                value = value,
                                inline=False)
                    
            embed.add_field(name = 'User commands',
                            value = '\n'.join([f'`{n}` - {t}' for n, t, _ in s.user_commands]),
                            inline=False)
            if 'help-hidden' in message.content:
                embed.add_field(name = 'Hidden commands',
                                value = '\n'.join([f'`{n}` - {t}' for n, t, _ in s.hidden_commands]),
                                inline=False)
                embed.add_field(name = 'Hidden commands, use with care! (only in `#leaderboard`)',
                                value = '\n'.join([f'`{n}` - {t}' for n, t, _ in s.hidden_admin_commands]),
                                inline=False)
                if message.guild.id in ksp_guilds:
                    embed.add_field(name = 'Special emoji', value='For `voting`, `text`, `say` you can use `:coolrocket:`')
            try:
                admin_id = int(ADMIN)
                admin = await s.client.fetch_user(admin_id)
                embed.set_footer(text = f'{admin.name}#{admin.discriminator}',
                                 icon_url=admin.avatar_url)
            except:
                ...
            await message.channel.send(embed = embed)
            return
        else:
            embed = discord.Embed()
            embed.add_field(name = 'Available commands',
                            value = '\n'.join([f'`{n}` - {t}' for n, t, _ in s.user_commands]),
                            inline=False)
            await message.channel.send(embed = embed)
            return

    def get_used_challenges(s, sChallengeName):
        active_challenges = 6
        last_challenges = set()
        last_challenge_types = set()
        used_challenge_types = set()
        
        for submission in s.json_data.j.get('aSubmission', [])[::-1]:
            last_challenges.add(submission['sChallengeName'])
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
                            response += (f"```\n{'>' if (chl.get('sName') in used) else (('|' if (chl.get('sName') in last) else ' ') if full else ' ')}" +
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
                        ...
                
            # short list too short, try full list now
            response = 'All types (`>` = used in this challenge, `|` = used in last challenges):'
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
                    ...
                     
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
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('set challenge channel:', e)
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
            embed.add_field(name='Auto user', value=f'**{author_name}** id: **{user_id}**')
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
                await s.send(message.channel, 'Enter score (e.g. `31415.93`), [`.` - decimal separator]:')
                while True:
                    try:
                        msg = await s.wait_response(message, author_id=author_id)
                        if not msg:
                            await message.channel.send('`changes reverted`')
                            s.open_json()
                            s.json_lock.lock = None
                            return
                        fScore = float(msg.content.strip().replace(',', '').replace(' ', ''))
                        break
                    except:
                        await message.channel.send('Number must be int or float, like `31415` or `2.7183`\nTry again or `cancel`')
            else:
                fScore = 1.0


            # we are ready! last confirmation
            author_name = kwargs.get('author_name')
            if (not author_name) or (user_id != kwargs.get('iID')):
                author_name = (await s.client.fetch_user(user_id)).name

            newPlayer = (0 == len([1 for x in s.json_data.j['aSubmission'] if x.get('iUserID') == user_id]))
            sTypeName = s.json_data.find(s.json_data.j['aChallengeType'], sName=sChallengeTypeName).get('sNick')
                
            embed = discord.Embed(title='Last check')
            embed.add_field(name=('__NEW__ ' if newPlayer else '') + 'Player', value=f"**{author_name}**\nid: {user_id}", inline=False)
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
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('add submission:', e)
            await s.send(message.channel, 'Something really wrong')
            await message.channel.send('`changes reverted`')
            s.open_json()
            s.json_lock.lock = None
            return
        
        s.json_lock.lock = None
        return
    
    async def add_points(s, message, **kwargs):
        if s.json_lock.lock:
            await s.send(message.channel, '`json locked. try again later`')
            return
        if (kwargs.get('winners') is None) or (kwargs.get('points') is None):
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
        else:
            user_ids = kwargs.get('winners')
            user_id_s = set([(await s.ask_for_user_id(message, user_id = u, ignore_bots=True)) for u in user_ids])
            user_id_s.discard(None)
            points = kwargs.get('points')
            
        try:
            embed = discord.Embed()
            player_text = ''
            for user_id in user_id_s:
                player = s.json_data.find(s.json_data.j.get('aPlayer', []), iID=user_id)
                player['iStaticPoints'] = player.get('iStaticPoints', 0) + points
                player_text += f"\n<@{player.get('iID')}> **@{player.get('sName')}#{player.get('iDiscriminator')}** {player.get('iID')}"
            embed.add_field(name='Updating players', value=player_text)
            await message.channel.send(embed=embed)
            response = await s.update_lb()
            s.save_json()
            s.json_lock.lock = None
            return response
        except Exception as e:
            await message.channel.send('`reverted changes`')
            s.open_json()
            s.json_lock.lock = None
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('add points:', e)
            return

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

    async def lb_settings(s, message):
        if s.json_lock.lock:
            await s.send(message.channel, '`json locked. try again later`')
            return
        await message.channel.send('You can choose between default appearance (embed with full leaderboard + ranking img + activity img)\n'+
                                   'or shortened one (link to site with full ranking + top 10 / top last challenges)\n'+
                                   'enter `default` or `top`. You can `cancel` at any time')
    
        message_r = await s.wait_response(message)
        if not message_r:
            s.json_lock.lock = None
            return
        if message_r.content == 'top':
            s.json_data.j['bShortLB'] = True
            await message.channel.send('Please enter the `http://link` for website with full leaderboard, or `*` for no link')
            message_r = await s.wait_response(message)
            if not message_r:
                s.json_lock.lock = None
                return
            if message_r.content == '*':
                s.json_data.j['sLBurl'] = ''
            else:
                s.json_data.j['sLBurl'] = message_r.content
                
            await message.channel.send('How many *places* to show in rating?')
            while True:
                message_r = await s.wait_response(message)
                if not message_r:
                    s.json_lock.lock = None
                    return
                try:
                    num = s.get_int(message_r.content)
                    if not num:
                        raise
                except:
                    await message.channel.send('Please enter number, like `10`')
                    continue
                s.json_data.j['iLBplaces'] = num
                break
                
            await message.channel.send('How many *challenges* to count in **last top**?')
            while True:
                message_r = await s.wait_response(message)
                if not message_r:
                    s.json_lock.lock = None
                    return
                try:
                    num = s.get_int(message_r.content)
                    if not num:
                        raise
                except:
                    await message.channel.send('Please enter number, like `10`')
                    continue
                s.json_data.j['iLBchallenges'] = num
                break 

        else:
            # standart leaderboard thingy
            try:
                del s.json_data.j['bShortLB']
            except:
                ...
        s.save_json()
        s.json_lock.lock = None
        await message.channel.send('Done')
        return

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
            
            s.json_data.j['iMentionsChannel'] = channel.id
            break

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

        await message.channel.send('`done`')
        
        s.save_json()
        s.json_lock.lock = None
        return


    async def update_usernames(s, *args):
        async def update_player(player):
            try:
                
                # try to get member from guild
                try:
                    guild = s.client.get_guild(s.guild_id)
                    user = await guild.fetch_member(player.get('iID'))
                    if not user: raise
                except:
                    user = await s.client.fetch_user(player.get('iID'))
                await s.get_avatar(user.id, update=True, user=user) # update avatar too
                player['sName'] = user.display_name
                player['iDiscriminator'] = user.discriminator
                player['sAvatarURL'] = str(user.avatar_url)
            except Exception as e:
                traceback.print_exc()
                if DEBUG:
                    raise e
                else:
                    print('update usernames:', e)
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
                traceback.print_exc()
                if DEBUG:
                    raise e
                else:
                    print('update_winners:', e)
                    
        await asyncio.gather(*(asyncio.ensure_future(update_win(sub)) for sub in sub))
        return

    def generate_lb_embed(s):
        first = True
        limit = 5900
        fields = s.json_data.result_leaderboard_for_embed() or []
        embed = discord.Embed()
        for field in fields:
            if len(embed) + len(field) > limit:
                embed.add_field(name='and some more', value='...', inline=False)
                break
            name = 'Actual ranking' if first else '\u200b'
            first = False
            embed.add_field(name=name, value=field, inline=False)

        return embed          
    
    async def update_lb(s, *args):
        try:
            await s.update_usernames() # update usernames & avatars
            s.json_data.calculate_rating()
            await s.post()
            await s.post_img()
            
            if not (s.leaderboard_channel_id and s.leaderboard_message_id):
                return f'`{s.prefix}set leaderboard` required'
            msg = await s.get_message(s.leaderboard_channel_id, s.leaderboard_message_id)
            if not msg:
                channel = await s.client.fetch_channel(s.leaderboard_channel_id)
                msg = await channel.send('Here will be leaderboard published')
                s.leaderboard_channel_id, s.leaderboard_message_id = msg.channel.id, msg.id
                s.json_data.set_lb_message(s.leaderboard_channel_id, s.leaderboard_message_id)
            if s.json_data.j.get('bShortLB', False):
                try:
                    if s.json_data.j.get('sLBurl', ''):
                        embed = discord.Embed()
                        embed.add_field(name='Full leaderboard can be found', value=f'[HERE (official "{msg.guild.name}" leaderboard)]({s.json_data.j.get("sLBurl")})')
                        await msg.edit(content='', embed=embed)
                    else:
                        try:
                            await msg.delete()
                        except:
                            ...
                    await s.update_lb_img(short_rank=True,
                                          places=s.json_data.j.get('iLBplaces'),
                                          challenges=s.json_data.j.get('iLBchallenges'))
                    return 'updated'
                except:
                    traceback.print_exc()
                    return 'something wrong'  
            else:
                try:
                    embed = s.generate_lb_embed()
                    await msg.edit(embed=embed)
                    await s.update_lb_img()
                    return 'updated'
                except Exception as e:
                    traceback.print_exc()
                    if DEBUG:
                        raise e
                    else:
                        print('update_lb:', e)
                    return 'something wrong'
            
        except Exception as e:
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('update_lb2:', e)
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
                
            embed = s.generate_lb_embed()
            await msg.channel.send(embed=embed)                       
            return '*** Done ***'
        except Exception as e:
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('print lb:', e)
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
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('get rank:', e)
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
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('rank_img:', e)
            return 'User not found. Maybe invite him?'

        # try to get member from guild
        try:
            guild = s.client.get_guild(s.guild_id)
            member = await guild.fetch_member(user_id)
            if member:
                user = member
        except:
            ...

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
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('rank img:', e)
            guild_avatar = None

        if s.json_data.j.get('bShortLB'):
            lt_challenges = s.json_data.j.get('iLBchallenges', 5)
            players = s.json_data.get_last_top(lt_challenges)
            player = dfind(players, iID=user_id)
            lt_members = len(players)
            lt_max_points = max([x.get('iPoints') for x in players])
            if not player:
                lt_user_points = 0
                lt_rank = lt_members
            else:
                lt_user_points = player.get('iPoints', 0)
                lt_rank = player.get('iRank', lt_members)
            
            
            buffer = rankDisplay.create_rank_card(user_avatar,
                                                  guild_avatar,
                                                  user.display_name,
                                                  user.discriminator,
                                                  points,
                                                  max_points,
                                                  rank,
                                                  len(s.json_data.j.get('aPlayer', [])),
                                                  last_top=True,
                                                  lt_user_points = lt_user_points,
                                                  lt_max_points = lt_max_points,
                                                  lt_rank = lt_rank,
                                                  lt_members = lt_members,
                                                  lt_challenges = lt_challenges)
        else:
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
                traceback.print_exc()
                if DEBUG:
                    raise e
                else:
                    print('activity img:', e)
                return 'something wrong'

        except Exception as e:
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('activity_img 2:', e)
            return 'something wrong'

    async def get_activity_img(s, *args, **kwargs):
        s.json_data.calculate_rating()
        # get not disabled players with submissions
        players = sorted(s.json_data.j.get('aPlayer', []), key=lambda x: float(x.get('iPoints')), reverse=True)
        players = list(filter(lambda x: not x.get('bDisabled', False), players))
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
                if not any(not (x.get('iPoints') is None) for x in s.json_data.j['aSubmission']
                             if x.get('iUserID') == p.get('iID') and x.get('sChallengeName') == ch):
                    points = None
                pp['aSubmissions'].append((ch, points))

            #get avatar     
            pp['avatar'] = await s.get_avatar(p.get('iID', None))
            players_prepared.append(pp)
        website = kwargs.get('website', False)
        buffer = rankDisplay.create_activity_card(players_prepared, dMaxPoints, website)
        return buffer
    
    
    async def update_lb_img(s, *args, **kwargs):
        try:
            s.json_data.calculate_rating()
            try:
                channel_id = s.leaderboard_channel_id
                if not channel_id:
                    return f'please configure `{s.prefix}set leaderboard`'
                channel = client.get_channel(channel_id)

                
                if kwargs.get('short_rank', False):# leaderboard image
                    places = kwargs.get('places', 10)
                    challenges = kwargs.get('challenges', 10)
                    message_id = s.json_data.j.get('iLeaderboardImage')
                    if message_id:
                        try:
                            message = await channel.fetch_message(message_id)
                            await message.delete()
                        except:
                            ...
                    buffer = await s.get_top_img(places)
                    if not buffer:
                        return
                    message = await channel.send(content = f'Top **{places}** absolute leaders', file=discord.File(buffer, 'lb_top.png'))
                    s.json_data.j['iLeaderboardImage'] = message.id

                    # activity image
                    message_id = s.json_data.j.get('iActivityImage')
                    if message_id:
                        try:
                            message = await channel.fetch_message(message_id)
                            await message.delete()
                        except:
                            ...
                    buffer = await s.get_last_top_img(places, challenges)
                    if not buffer:
                        return
                    message = await channel.send(content = f'Top **{places}** for last **{challenges}** challenges', file=discord.File(buffer, 'actual.png'))
                    s.json_data.j['iActivityImage'] = message.id
                else:
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
                traceback.print_exc()
                if DEBUG:
                    raise e
                else:
                    print('update lb img:', e)
                return 'something wrong'

        except Exception as e:
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('update lb img 2:', e)
            return 'something wrong'

    async def get_top_img(s, limit, **kwargs):
        s.json_data.calculate_rating()
        players = sorted(s.json_data.j.get('aPlayer', []), key=lambda x: float(x.get('iPoints')), reverse=True)
        if not players:
            return
        data = []

        for player in players:
            if player.get('bDisabled') or (limit == 0 and (float(player.get('iStaticPoints', 0)) - float(player.get('iPoints', 0))) == 0):
                continue
            if limit > 0:
                if player.get('iRank') > limit:
                    break

            avatar = await s.get_avatar(player['iID'])

            data.append({'iRank':player.get('iRank'),
                         'sName':player.get('sName'),
                         'iDiscriminator':player.get('iDiscriminator'),
                         'iPoints':player.get('iPoints'),
                         'avatar':avatar
                         })
        website = kwargs.get('website', False)
        buffer = rankDisplay.create_top_card(data, 0, website=website)
        return buffer
        

    async def top_img(s, *msg, leaderboard=False, content=None):
        limit = s.json_data.j.get('iLBplaces', 10)
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

    async def get_last_top_img(s, limit, ch_limit):
        # now let's do some calculations for players
        players = s.json_data.get_last_top(ch_limit)
        
        if not players:
            return
        data = []

        for player in players:
            if limit > 0:
                if player.get('iRank') > limit:
                    break

            avatar = await s.get_avatar(player['iID'])

            data.append({'iRank':player.get('iRank'),
                         'sName':player.get('sName'),
                         'iDiscriminator':player.get('iDiscriminator'),
                         'iPoints':player.get('iPoints'),
                         'avatar':avatar
                         })
        buffer = rankDisplay.create_top_card(data, color_scheme=2)
        return buffer
        

    async def last_top_img(s, *msg, limit=None, ch_limit=None, content=None):
        if msg:
            msg = msg[0]
        if limit is None:
            limit = s.json_data.j.get('iLBplaces', 10)
            if len(msg.content.strip().split(' ')) > 1:
                try:
                    limit = int(msg.content.split(' ')[1])
                except:
                    ...
                    
        if ch_limit is None:
            ch_limit = s.json_data.j.get('iLBchallenges', 5)
            if len(msg.content.strip().split(' ')) > 2:
                try:
                    ch_limit = int(msg.content.split(' ')[2])
                except:
                    ...
            
        if content is None:
            content = f"Full leaderboard: <#{s.leaderboard_channel_id}>\n**Top {limit}**"
            content += f' for last **{ch_limit}** challenges'
        m = await msg.channel.send('Consulting Malevitch...')
        buffer = await s.get_last_top_img(limit, ch_limit)
        await m.delete(delay=3)
        if buffer:
            await msg.channel.send(content=content, file=discord.File(buffer, 'last_top.png'))
        else:
            return "no submissions found"
        return

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
        data = None
        if len(args) == 0:
            try:
                url = s.json_data.j.get('sPOSTURL')
                if not url:
                    return
            except Exception as e:
                traceback.print_exc()
                print('post', str(e))
                return
        else:
            try:
                if len(args[0].content.strip().split(' ')) == 1:
                    url = s.json_data.j.get('sPOSTURL')
                    if not url:
                        raise
                else:
                    url = args[0].content.strip().split(' ')[1]
            except Exception as e:
                return f'Specify URL `{s.prefix}post URL`'
 
        payload = deepcopy(s.json_data.j)            
        payload['iGuildID'] = s.guild_id
        data = json.dumps(payload)
            
        headers = {'content-type': 'application/json'}
        try:

            r = requests.post(url, data=data, headers=headers) 
            response = '\nstatus: `{}` \ntext: `{}`'.format(
                        r.status_code, r.text)
        except Exception as e:
            traceback.print_exc()
            return f'Exception: ```{e}```'
        return 'Done: ' + str(response)

    async def post_img(s, *args):
        if len(args) == 0:
            try:
                url = s.json_data.j.get('sPOSTURL_IMG')
                if not url:
                    return
            except Exception as e:
                traceback.print_exc()
                print('post', str(e))
                return
        else:
            try:
                if len(args[0].content.strip().split(' ')) == 1:
                    url = s.json_data.j.get('sPOSTURL_IMG')
                    if not url:
                        raise
                else:
                    url = args[0].content.strip().split(' ')[1]
            except Exception as e:
                return f'Specify URL `{s.prefix}post_img URL`'
        try:
            r = requests.post(url, files={'top.png':(await s.get_top_img(-1, website=True)), 'activity.png':(await s.get_activity_img(website=True))})   
            response = '\nstatus: `{}` \ntext: `{}`'.format(
                        r.status_code, r.text)
        except Exception as e:
            traceback.print_exc()
            return f'Exception: ```{e}```'
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

        
    async def seturl_img(s, msg):
        if s.json_lock.lock:
            await msg.channel.send('`json locked. try again later`')
            return
        data = msg.content.strip().split(' ')
        if len(data) == 1:
            try:
                del s.json_data.j['sPOSTURL_IMG']
            except:
                s.json_lock.lock = None
                return 'No Auto-POST-IMG URL found'
            s.json_lock.lock = None
            return 'Auto-POST-IMG URL deleted'
        else:
            s.json_data.j['sPOSTURL_IMG'] = data[1]
            s.save_json()
            s.json_lock.lock = None
            return 'Auto-POST-IMG URL updated'

    async def disable(s, msg):
        if s.json_lock.lock:
            await msg.channel.send('`json locked. try again later`')
            return
        await msg.channel.send(embed=s.generate_lb_embed())
        user_id = await s.ask_for_user_id(msg, no_creation=True)
        if not user_id:
            s.json_lock.lock = None
            return
        s.json_data.find(s.json_data.j.get('aPlayer', []), iID=user_id)['bDisabled']=True
        response =  await s.update_all(msg, ignore_lock = True)
        s.json_lock.lock = None
        await msg.channel.send(f'Disabled. If needed `{s.prefix}update all`')

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
        global scanned_messages
        global scanned_reactions
        global start_time
        time_d = int(time.time() - start_time)
        weeks = time_d // (7 * 24 * 3600)
        time_d = (time_d % (7 * 24 * 3600))
        days = time_d // (24 * 3600)
        time_d = (time_d % (24 * 3600))
        h = time_d //3600
        m = (time_d % 3600)//60
        ss = time_d % 60
        hms = f"{h:02}:{m:02}:{ss:02}"

        uptime = ''
        if weeks:
            uptime += f"{weeks} week{'s' if weeks > 1 else ''}, "
        if days:
            uptime += f"{days} day{'s' if days > 1 else ''}, "
        uptime += hms
        
        return f'Pong! **{int(s.client.latency*1000)}** ms\nUptime: {uptime}\nSince last restart scanned: {beautify(scanned_messages)} messages & {beautify(scanned_reactions)} reactions'

    async def unlock(s, *args):
        response = 'Locked -> Unlocked' if s.json_lock.lock else 'Unlocked -> Unlocked'
        s.json_lock.lock = None
        return response

    async def voting(s, message):
        create_new_list = 'voting-list' in message.content.lower().strip()
        create_new_vote = 'voting-new' in message.content.lower().strip() or create_new_list
        new_message = []

        # emoji list
        if message.guild.id in ksp_guilds:
            emoji_list = iter((
                                '<:1_:737600854957359125>',
                                '<:2_:737600868865540178>',
                                '<:3_:737600883516506114>',
                                '<:4_:737600898934636574>',
                                '<:5_:737600913249927209>',
                                '<:6_:737600928009682984>',
                                '<:7_:737600942488420415>',
                                '<:8_:737600960855277608>',
                                '<:9_:737600974360936471>',
                                ))

        else:
            emoji_list = iter((
                                '\u0030\uFE0F\u20E3',
                                '\u0031\uFE0F\u20E3',
                                '\u0032\uFE0F\u20E3',
                                '\u0033\uFE0F\u20E3',
                                '\u0034\uFE0F\u20E3',
                                '\u0035\uFE0F\u20E3',
                                '\u0036\uFE0F\u20E3',
                                '\u0037\uFE0F\u20E3',
                                '\u0038\uFE0F\u20E3',
                                '\u0039\uFE0F\u20E3',
                              ))

        message_text = message.content

        if message.guild.id in ksp_guilds:
            for se, code in s.special_emojis.items():
                try:
                    emoji = s.client.get_emoji(int(code))
                    if emoji and (message_text.find(se) != -1):
                        create_new_vote = create_new_vote or emoji.animated
                        message_text = message_text.replace(se, f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>")
                        continue
                except:
                    ...
                

        # replace integers with animated emojis
        emojis = []
        if create_new_list:
            first_item_in_list = len(message_text.splitlines()[0].split()) > 1
        try:
            for a in message_text.split(maxsplit=1)[1].splitlines():
                if create_new_list:
                    if a:
                        if first_item_in_list:
                            new_message.append(a)
                        else:
                            emo = next(emoji_list, '')
                            new_message.append(emo + (' ' if emo else '') + a)
                            emojis.append(emo)
                    first_item_in_list = False
                    continue
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
                    else:
                        emojis.append(a.split()[0])
                new_message.append(a)
        except Exception as e:
            return # no text in message
            
        if create_new_vote:
            msg = await message.channel.send('\n'.join(new_message))
            s.add_lb_user(message.author, msg)

            # it is not visible in audit, so...
            if False: # disabled this check
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
##                print('\\u' + '\\u'.join(hex(ord(e))[2:] for e in emoji))
##                print(emoji)
            except Exception as e:
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
            traceback.print_exc()
            if DEBUG:
                raise e
            else:
                print('update roles', e)
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
                traceback.print_exc()
                if DEBUG:
                    raise e
                else:
                    print('update role:', e)
            
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

    @staticmethod
    def can_send(member, channel):
        return member.permissions_in(channel).send_messages

    async def get_message_from_id(s, message, ch_m_id):
        ''' ch_m_id in format channel_id-message_id '''
        ''' or if only message_id, channel_id taken from message '''
        try:
            ch_m_id = ch_m_id.split('-')
            msg_id = s.get_int(ch_m_id[-1])
            if len(ch_m_id) == 1:
                return (await message.channel.fetch_message(msg_id))
            else:
                channel_id = s.get_int(ch_m_id[0])
                return (await s.get_message(channel_id, msg_id))
        except:
            if DEBUG: traceback.print_exc()
            return
        return

    async def give_rocket(s, message):
        try:
            try:
                msg = await s.get_message_from_id(message, message.content.split()[1])
            except:
                msg = (await message.channel.history(limit=2).flatten())[-1]
            if message.guild.id in ksp_guilds:
                await msg.add_reaction(s.client.get_emoji(732098507137220718))
            else:
                await msg.add_reaction('\U0001F680')
            await message.delete()
        except Exception as e:
            if DEBUG: traceback.print_exc()
            print('give_rocket', e)

    async def give_text(s, message):
        add_reaction = True
        msg = await s.get_message_from_id(message, message.content.split()[1])
        if msg is None:
            add_reaction = False
            msg = message
        text = message.content.split(maxsplit = 1 + int(add_reaction))[-1]
        emojis, unique = replace_letters(text, special_emojis=s.special_emojis_full)
        if not unique:
            add_reaction = False

        if add_reaction:
            try:
                await message.delete()
            except Exception as e:
                ...
            for e in emojis:
                try:
                    await msg.add_reaction(e)
                except Exception as e:
                    ...
        else:
            try:
                if s.can_send(message.author, msg.channel):
                    msg = await msg.channel.send(' '.join(emojis).replace('\n ', '\n'))
                    s.add_lb_user(message.author, msg)
                    await message.delete()
                else:
                    await message.channel.send('nope')
            except Exception as e:
                if DEBUG: traceback.print_exc()

    
    async def say(s, message):
        try:
            message_text = message.content.split(maxsplit=1)[-1]
        except:
            return

        try:
            channel = await s.client.fetch_channel(s.get_int(message.content.split()[1]))
            if not channel:
                raise
            message_text = message.content.split(maxsplit=2)[-1]
        except:
            channel = message.channel

        if not s.can_send(message.author, channel):
            await message.channel.send('nope')
            return
   
        if message.guild.id in ksp_guilds:
            for se, code in s.special_emojis.items():
                try:
                    emoji = s.client.get_emoji(int(code))
                    if emoji and (message_text.find(se) != -1):
                        message_text = message_text.replace(se, f"<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>")
                        continue
                except:
                    ...
        try:
            if message.attachments and len(message.content.split()) == 1:
                message_text = ''
            msg = await channel.send(message_text, files=(await s.get_files(message)))
            s.add_lb_user(message.author, msg)
            await message.delete()
        except:
            if DEBUG: traceback.print_exc()

    async def init_message(s):
        # check if mentions channel exists
        channel_id = s.json_data.j.get('iMentionsChannel')
        #text = s.json_data.j.get('iMentionsText', '')
        
        if channel_id:
            try:
                channel = client.get_channel(channel_id)
                if not channel:
                    return
                global start_time
                text = 'reconnected'
                if time.time() - start_time < 300:
                    text = 'restarted'
                await channel.send(f"<@{s.client.user.id}> just {text}. `{s.prefix}help`")
            except:
                return
        else:
            return


    async def mentioned(s, message):
        # will be supported in 1.6 await message.channel.send('Okay', reference=message)

        # check if channel exists
        channel_id = s.json_data.j.get('iMentionsChannel')
        text = s.json_data.j.get('iMentionsText', '')
        
        if channel_id:
            try:
                channel = await s.client.fetch_channel(channel_id)
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

        if message.guild.id in ksp_guilds:
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
        else:
            part_2 = ('',)
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
        embed = discord.Embed(title=':new: mention')
        embed.add_field(name='user', value=f'<@{message.author.id}>')
        embed.add_field(name='user name', value=f'@{message.author.display_name}#{message.author.discriminator}')
        embed.add_field(name='user ID', value=f'{message.author.id}')
        embed.add_field(name='channel', value=f'<#{message.channel.id}>')
        embed.add_field(name='message', value=f'[jump]({message.jump_url})')
        embed.add_field(name='confirmation', value=f'[jump]({msg_confirmation.jump_url})')

        if ch_name:
            embed.add_field(name='challenge', value=f'{ch_name}')
        if ch_winners:
            embed.add_field(name='#winners', value=f'<#{ch_winners}>')

            
        embed.add_field(name='message text', value=f'{message.content[:500] or "*"}', inline=False)
        msg = await channel.send(content=text, embed=embed)
        await msg.pin(reason='new challenge submission')

        await s.add_ynd_reactions(msg, mode='ynd')
        return

    def add_lb_user(s, user, message):
        s.last_lb_users.append({'user':user, 'message':message})
        if len(s.last_lb_users) > 20:
            s.last_lb_users.pop(0)

    async def print_lb_user(s, message):
        if len(s.last_lb_users) == 0:
            await message.channel.send('No one used hidden features since last restart')
        embed = discord.Embed()
        for u in s.last_lb_users:
            msg = u['message']
            if msg.content:
                text = msg.content[:500]
            else:
                text = '`empty`'
            user = u['user']
            embed.add_field(name=f'@{user.display_name}#{user.discriminator} {user.id}', value=f'[{text}]({message.jump_url})', inline=False)
        await message.channel.send(embed=embed)
            

    async def raw_react(s, payload):
        if payload.user_id == s.client.user.id or payload.member.bot:
            return # ignore own & bot reactions
        msg = await s.get_message(payload.channel_id, payload.message_id)
        if not msg:
            return
        if msg.author.id == s.client.user.id:
            if msg.embeds:
                embed_dict = msg.embeds[0].to_dict()
                # seems to be new mention from player
                if ':new: mention' == embed_dict.get('title'):
                    try:
                        ch_id, msg_id = [s.get_int(x) for x in
                                                      dfind(embed_dict.get('fields'),
                                                             name='message')['value'].split('/')[-2:]]
                        message = await s.get_message(ch_id, msg_id)
                    except:
                        ...
                    try:
                        conf_ch_id, conf_msg_id = [s.get_int(x) for x in
                                                                dfind(embed_dict.get('fields'),
                                                                      name='confirmation')['value'].split('/')[-2:]]
                        msg_confirmation = await s.get_message(conf_ch_id, conf_msg_id)
                    except:
                        ...
                    try:
                        ch_name = dfind(embed_dict.get('fields'), name='challenge').get('value')
                    except:
                        ch_name = None
                        
                        
                    # check reactions
                    reaction = s.check_reaction(payload.emoji, mode='ynd')
                    if reaction is None:
                        await s.add_ynd_reactions(msg, mode='ynd')
                        return # unexpected reaction
                    await msg.clear_reactions()
                    if reaction == 'delete':
                        message_r = await msg.channel.send('Really delete this and confirmation message?')
                        reaction, user = await s.ask_for_reaction(message_r, mode='yn', timeout=30, author_id=payload.user_id)
                        await message_r.delete()
                        if reaction == 'yes':
                            await msg.unpin(reason='new challenge submission - ready')
                            try:
                                await msg_confirmation.delete()
                            except:
                                ...
                            await msg.channel.send('`deleted`')
                            try:
                                await msg.delete()
                            except:
                                ...
                            return
                        else:
                            await s.add_ynd_reactions(msg, mode='ynd')
                            return
                    elif reaction == 'yes':
                        try:
                            author_name = dfind(embed_dict.get('fields'), name='user name')['value']
                            iID = s.get_int(dfind(embed_dict.get('fields'), name='user ID')['value'])
                            rSubmission, newPlayer, sTypeName = await s.add_submission(msg,
                                                                                       iID=iID,
                                                                                       author_name=author_name,
                                                                                       sChallengeName=ch_name,
                                                                                       author_id=payload.user_id,
                                                                                       ret_points=True)
                            await msg.unpin(reason='new challenge submission - ready')
                        except Exception as e:
                            await s.add_ynd_reactions(msg, mode='ynd')
                            return
                        
                        modus = s.json_data.find(s.json_data.j['aChallengeType'], sName=rSubmission.get('sChallengeTypeName')).get('sNick')
                        win_ch_id = s.json_data.find(s.json_data.j['aChallenge'], sName=rSubmission.get('sChallengeName')).get('idChannel')

                        user_id = rSubmission.get('iUserID')

                        leaderboard_ch = f"<#{s.leaderboard_channel_id}>" if s.leaderboard_channel_id else 'leaderboard'
                        winners_ch = f"<#{win_ch_id}>" if win_ch_id else 'Challenge winners'
                        newPlayerWelcome = '\n:tada: **Welcome to the challenges by the way! :tada:**' if newPlayer else ''
                        iPoints = rSubmission.get('iPoints')
                        if iPoints and iPoints > 0:
                            if len(s.json_data.find(s.json_data.j.get('aChallenge'), sName=rSubmission.get('sChallengeName')).get('aPoints', [])) == 1:
                                place = ''
                            else:
                                place = f"and ranked **{rSubmission.get('iRank')}**{s.json_data.suffix(rSubmission.get('iRank'))} "
                            buffer = await s.rank_img(msg, user_id=user_id)
                            message_r = await message.channel.send(f"<@{user_id}>, **yay!** You got " +
                                                                   f"**{beautify(iPoints)}** points " +
                                                                   place +
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
                        embed.add_field(name='Accepted by', value=f'<@{payload.user_id}>')
                        await msg.channel.send(embed=embed)
                        try:
                            embed_dict['title'] = ':white_check_mark: submission accepted'
                            embed_dict['fields'].append({'name':'accept', 'value':f'[jump]({message_r.jump_url})'})
                            embed_dict['fields'].append({'name':'by', 'value':f'<@{payload.user_id}>'})
                            await msg.edit(embed = discord.Embed.from_dict(embed_dict))
                        except Exception as e:
                            traceback.print_exc()
                            if DEBUG: raise e
                        return
                    elif reaction == 'no':
                        message_r = await msg.channel.send('Please enter the reason, why this submission is declined, or `*` for no message')
                        message_r = await s.wait_response(message_r, timeout=120, author_id=payload.user_id)
                        if message_r is None:
                            await msg.channel.send('`reverted`')
                            await s.add_ynd_reactions(msg, mode='ynd')
                            return
                        await msg.unpin(reason='new challenge submission - ready')
                        if message_r.content == '*':
                            await msg.channel.send('Okay, no message sent')
                            try:
                                embed_dict['title'] = ':no_entry: submission declined'
                                embed_dict['fields'].append({'name':'decline', 'value':'without message'})
                                embed_dict['fields'].append({'name':'by', 'value':f'<@{payload.user_id}>'})
                                await msg.edit(embed = discord.Embed.from_dict(embed_dict))
                            except Exception as e:
                                traceback.print_exc()
                                if DEBUG: raise e
                            await msg.unpin(reason='new challenge submission - declined')
                            return
                        message_r = await message.channel.send(f'<@{message.author.id}>, *sorry, your submission is declined*\n{message_r.content}')
                        embed = discord.Embed()
                        embed.add_field(name='Decline message sent', value=f'[jump]({message_r.jump_url})')
                        embed.add_field(name='Declined by', value=f'<@{payload.user_id}>')
                        try:
                            embed_dict['title'] = ':no_entry: submission declined'
                            embed_dict['fields'].append({'name':'decline', 'value':f'[jump]({message_r.jump_url})'})
                            embed_dict['fields'].append({'name':'by', 'value':f'<@{payload.user_id}>'})
                            await msg.edit(embed = discord.Embed.from_dict(embed_dict))
                        except Exception as e:
                            traceback.print_exc()
                            if DEBUG: raise e
                        await msg.channel.send(embed=embed)
                        await msg.unpin(reason='new challenge submission - declined')
                        return
                    else:
                        print('mentioned - None reaction')
                        await s.add_ynd_reactions(msg, mode='ynd')
                        return  # sommething went really bad here
                ## giveaway bot
                elif ':new: giveaway winners' ==  embed_dict.get('title'):
                    # check reactions
                    reaction = s.check_reaction(payload.emoji, mode='yn')
                    await msg.clear_reactions()
                    if reaction is None:
                        await s.add_ynd_reactions(msg, mode='yn')
                        return # unexpected reaction
                    try:
                        ch_id, msg_id = [s.get_int(x) for x in
                                                      dfind(embed_dict.get('fields'),
                                                             name='Message')['value'].split('/')[-2:]]
                        message = await s.get_message(ch_id, msg_id)
                    except Exception as e:
                        traceback.print_exc()
                        if DEBUG: raise e

                    if reaction != 'yes':
                        await msg.channel.send(f'`canceled` try `{s.prefix}static points`')
                        await msg.unpin()
                        try:
                            embed_dict['title'] = ':x: giveaway declined'
                            await msg.edit(embed = discord.Embed.from_dict(embed_dict))
                        except:
                            ...
                        return
                    try:
                        try:
                            winners = dfind(embed_dict.get('fields'), name='Winners').get('value')
                            winners_list = [s.get_int(x.split()[0]) for x in winners.splitlines()]
                        except:
                            await s.add_ynd_reactions(msg, mode='yn')
                            await msg.channel.send('`reverted`')
                            return
                        try:
                            points = float(dfind(embed_dict.get('fields'), name='Points').get('value'))
                        except:
                            await s.add_ynd_reactions(msg, mode='yn')
                            await msg.channel.send('`reverted`')
                            return
                        msg_a = await s.add_points(msg, winners=winners_list, points=points)
                        if msg_a is None:
                            await s.add_ynd_reactions(msg, mode='yn')
                            await msg.channel.send('`reverted`')
                            return
                        leaderboard_ch = f"<#{s.leaderboard_channel_id}>" if s.leaderboard_channel_id else 'leaderboard'
                        msg_c = await message.channel.send(f'\U0001F389 Congratulations! {leaderboard_ch} updated! \U0001F389')
                        await msg.unpin()
                        embed = discord.Embed()
                        embed.add_field(name='confirmed', value=f'[jump]({msg_c.jump_url})')
                        await msg.channel.send(embed=embed)
                        try:
                            embed_dict['title'] = ':white_check_mark: giveaway accepted'
                            embed_dict['fields'].append({'name':'accept', 'value':f'[jump]({msg_c.jump_url})'})
                            await msg.edit(embed = discord.Embed.from_dict(embed_dict))
                        except:
                            ...
                        return
                    except Exception as e:
                        traceback.print_exc()
                        if DEBUG: raise e
                        await msg.channel.send('`reverted`')
                        await s.add_ynd_reactions(msg, mode='yn')
                        return
                    await msg.channel.send('`reverted`')
                    await s.add_ynd_reactions(msg, mode='yn')
                    return
        elif 0: #let's disable reaction removal
            try:
                await msg.remove_reaction(payload.emoji, s.client.user)
            except:
                if DEBUG: traceback.print_exc()
        return

    async def change_prefix(s, message):
        if s.json_lock.lock:
            await message.channel.send('`json locked. try again later`')
            return
        await message.channel.send('Enter new prefix or `cancel`')
        msg_r = await s.wait_response(message)
        if not msg_r:
            s.json_lock.lock = None
            return
        s.prefix = msg_r.content.lower()
        s.json_data.j['sPrefix'] = s.prefix
        #await s.client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f'your rank'))
        s.save_json()
        s.json_lock.lock = None
        s.create_help()
        await message.channel.send(f'New prefix `{s.prefix}` saved')
        return

    async def ext_bot(s, message):
        if message.author.id == 294882584201003009:
            ## giveaway bot ##
            # check if mentions channel exists
            channel_id = s.json_data.j.get('iMentionsChannel')
            text = s.json_data.j.get('iMentionsText', '')
            
            if channel_id:
                try:
                    channel = await s.client.fetch_channel(channel_id)
                except:
                    return
                if not channel:
                    return
            else:
                return
            # check if mentions #
            members = message.mentions
            if not members:
                return

            # prepare data & list
            winners_list = [m.id for m in members]
            # I should learn regular expressions!
            points_text = message.content[message.content.find('You won'):]
            points_text = points_text[:points_text.find('!')].replace('*', '')
            # lets try to find the number!
            points = 0
            for pt in points_text.split():
                try:
                    points = float(pt)
                    # success!
                    break
                except Exception as e:
                    ...
            # nothing found
            if not points:
                return
            winners = '\n'.join([f"<@{m.id}> **@{m.display_name}#{m.discriminator}** {m.id}" for m in members])
            embed = discord.Embed(title=':new: giveaway winners')
            embed.add_field(name='Winners', value=winners, inline=False)
            embed.add_field(name='Points', value=str(points))
            embed.add_field(name='Message', value=f"[jump]({message.jump_url})")
            msg = await channel.send(content=text + '\n**All correct?**', embed=embed)
            await msg.pin(reason='new giveaway')

            await s.add_ynd_reactions(msg, mode='yn')
            return
            
        elif message.author.id == 771433825754021888:
            ## KSP Weekly Challenges
            try:
                if message.content and (message.content.split()[0] == f"{s.prefix}giveaway"):
                    try:
                        points = float(message.content.split()[1])
                        winners_list = [int(m) for m in message.content.split()[2:]]
                    except:
                        points = 0
                        winners_list = []
                    # check if mentions channel exists
                    channel_id = s.json_data.j.get('iMentionsChannel')
                    text = s.json_data.j.get('iMentionsText', '')
                    try:
                        channel = await s.client.fetch_channel(channel_id)
                        if not channel:
                            raise
                    except:
                        channel = message.channel
                    embed = discord.Embed(title='Automagically adding static points')
                    embed.add_field(name='Players', value='\n'.join(f'<@{i}>' for i in winners_list) or 'no one found')
                    embed.add_field(name='Points', value=f'**{points}**')
                    msg = await channel.send(embed=embed)
                    if not winners_list:
                        await channel.send('`No winners, aborted`')
                        return
                    if not points:
                        await channel.send('`0 points, aborted`')
                        return
                    max_try = 3
                    for xxx in range(1, max_try + 1):
                        try:
                            msg_a = await s.add_points(msg, winners=winners_list, points=points)
                            if msg_a is None:
                                rand_time = random.randint(4, 18)*10*xxx
                                await channel.send(f'`something went wrong` I will try again in **{rand_time}** seconds. (Try {xxx}/{max_try})')
                                await asyncio.sleep(rand_time)
                                continue
                            else:
                                await channel.send('`done`')
                                break
                        except Exception as e:
                            traceback.print_exc()
                            print('ext_bot:', e)
                    else:
                        embed = discord.Embed(title=f'!!! something went wrong, use {s.prefix}static points !!!')
                        embed.add_field(name='Players', value='\n'.join(f'<@{i}>' for i in winners_list) or 'no one found')
                        embed.add_field(name='Points', value=f'**{points}**')
                        msg_x = await channel.send(content=text, embed=embed)
                        await msg_x.pin(reason='something wrong')
                        
            except Exception as e:
                traceback.print_exc()
                print('ext_bot2:', e)
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
            for n, _, f in s.hidden_admin_commands:
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
            
        for n, _, f in s.hidden_commands:
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
    async def get_files(message):
        if not message.attachments:
            return
        files = []
        for m in message.attachments:
            buffer = io.BytesIO(await m.read())
            buffer.seek(0)
            files.append(discord.File(buffer, m.filename))
        return files

    @staticmethod
    async def dm(client, message):
        if not hasattr(leaderBot_class.dm, "last_user"):
            leaderBot_class.dm.last_user = None  # it doesn't exist yet, so initialize it
        try:
            admin_id = int(ADMIN)
            admin = await client.fetch_user(admin_id)
            if not admin_id:
                raise
        except:
            return

        # normal user
        if (message.author != admin) or ('super!mega!test' in message.content):
            await admin.send(f"> from <@{message.author.id}> @{message.author.name}#{message.author.discriminator} {message.author.id}\n" +
                             message.content, files=(await s.get_files(message)))
            await message.channel.send('`message sent`')
            leaderBot_class.dm.last_user = message.author
        # admin user
        else:
            try:
                # check if starts with user_id
                user = None
                user_id = leaderBot_class.get_int(message.content.split()[0])
                try:
                    user = await client.fetch_user(user_id)
                except:
                    ...
                if user:
                    try:
                        content = message.content.split(maxsplit=1)[1]
                    except:
                        content = '*'
                else:
                    # check if message referenced
                    if message.reference:
                        try:
                            channel = client.get_channel(message.reference.channel_id)
                            msg_ref = await channel.fetch_message(message.reference.message_id)
                        except Exception as e:
                            if DEBUG: raise e
                            msg_ref = None
                        user_id = leaderBot_class.get_int(msg_ref.content.split()[2])
                        try:
                            user = await client.fetch_user(user_id)
                        except:
                            ...
                    if user:
                        content = message.content or '*'
                    elif leaderBot_class.dm.last_user:
                        # use last known user
                        user = leaderBot_class.dm.last_user
                        content = message.content or '*'
                    if not user:
                        raise Exception('no user')
                
            except Exception as e:
                # if DEBUG: raise e
                await message.channel.send('Message should start with @user or id; referenced to `| from` or `| to` or it will be sent to last user')
                return
            try:
                await user.send(content, files=(await s.get_files(message)))
                await message.channel.send(f'> to <@{user.id}> @{user.name}#{user.discriminator} {user.id}')
                leaderBot_class.dm.last_user = user
            except Exception as e:
                await message.channel.send('> ' + str(e))
        return
            
    def create_help (s, *args):
        s.user_commands = (
                                (f'{s.prefix}help', 'prints this message', s.help),
                                (f'{s.prefix}rank', f'your rank; `{s.prefix}rank @user` to get *@user* rank', s.rank_img),
                                (f'{s.prefix}top', f'top for last 5 challenges; add number to limit positions; add second to limit challenges `{s.prefix}top 3 10`', s.last_top_img),
                                (f'{s.prefix}leaderboard', f'absolute leaderboard; add number to limit positions', s.top_img),
                                (f'{s.prefix}activity', f'activity rank; add number to limit positions `{s.prefix}activity 3`', s.act_img),
                                (f'{s.prefix}ksp', 'random ksp loading hint', s.ksp),
                                (f'{s.prefix}voting', "all emojis at line start added as reactions. *at least I'll try*. `-new`, `-list`", s.voting),
                          )
        
        s.commands = (
                                (f'{s.prefix}ping', 'bot latency', s.ping),
                                (f'{s.prefix}add', 'to add new submission', s.add_submission),
                                (f'{s.prefix}static points', 'add points (e.g. giveaways)', s.add_points),
                                (f'{s.prefix}update', 'force leaderboard update', s.update_all),
                                (f'{s.prefix}print all', 'prints leaderboard for all challenges *can be slow because of discord*', s.print_lb),
                                (f'{s.prefix}set leaderboard', 'set in which channel to post leaderboard', s.set_lb),
                                (f'{s.prefix}set winners', 'set in which channel to post winners for challenge', s.set_challenge_channel),
                                (f'{s.prefix}set mentions', f'set channel where <@{s.client.user.id}> mentions will be posted', s.set_mention_ch),
                                (f'{s.prefix}set role', 'set @role for active winners', s.set_role),
                                (f'{s.prefix}export json', 'exports data in json', s.json_exp),
                                (f'{s.prefix}post_img', f'send leaderboard images over `post` request. e.g.`{s.prefix}post_img http://URL`', s.post_img),
                                (f'{s.prefix}seturl_img', f'`{s.prefix}seturl_img URL` - where will be IMG `post`ed after each ranking update', s.seturl_img),
                                (f'{s.prefix}post', f'send leaderboard json over `post` request. e.g.`{s.prefix}post http://URL`', s.post),
                                (f'{s.prefix}seturl', f'`{s.prefix}seturl URL` - where will be JSON `post`ed after each ranking update', s.seturl),
                                (f'{s.prefix}disable user', 'to hide user from leaderboard', s.disable),
                                (f'{s.prefix}enable user', 'to reenable user to leaderboard', s.enable),
                                (f'{s.prefix}change prefix', 'to change the prefix', s.change_prefix),
                      )

        s.hidden_commands = (
                                (f'{s.prefix}give', 'give cool rocket reaction. `channel_id-message_id`  or `message_id` or `#channel-message_id`', s.give_rocket),
                                (f'{s.prefix}text', f'give text reaction `message_id text`. if no `message_id` or not all letters are unique, creates new message. Add `channel_id-message_id` to send to another #channel', s.give_text),
                                (f'{s.prefix}say', f'posts text from the name of <@{s.client.user.id}>. Add `{s.prefix}say #channel TEXT` to post in another channel', s.say),
                                (f'{s.prefix}last', f'last users who used hidden features', s.print_lb_user),       
                            )
        s.hidden_admin_commands = (
                                (f'{s.prefix}unlock', "removes `json lock`. don't use! debug feature", s.unlock),
                                (f'{s.prefix}import json', 'imports data from json', s.json_imp),
                                (f'{s.prefix}delete json', 'clears all you data from server', s.json_del),
                                (f'{s.prefix}lb settings', 'changes appearance settings for leaderboard', s.lb_settings),
                                )
            
    
    def __init__(s, client, guild_id):
        global start_time
        if start_time is None:
            start_time = time.time()
        s.guild_id = guild_id
        s.client = client
        s.json_data = json_class()
        
        s.json_path = str(guild_id)+'.txt'
        if(os.path.isfile(s.json_path)):
            s.open_json()
            print ('json loaded')
        else:
            s.save_json()
            print('no json found - empty created')
        pref = s.json_data.j.get('sPrefix')
        if not (pref is None):
            s.prefix = pref
        s.create_help()

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
        await leaderBot[guild.id].init_message()
        await client.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name=f'your rank'))
        print(
            f'{client.user} is connected to the following guild:\n'
            f'{guild.name}(id: {guild.id})'
        )

@client.event
async def on_message(message):
    if DEBUG_CH:
        if message.guild.id != DEBUG_CH:
            return
    if message.author == client.user:
        return
    global scanned_messages
    scanned_messages += 1
    if message.author.bot:
        await leaderBot[message.guild.id].ext_bot(message)
        return
    
    if message.guild:
        await leaderBot[message.guild.id](message)
    else:
        #dm message
        await leaderBot_class.dm(client, message)

@client.event
async def on_raw_reaction_add(payload):
    try:
        global scanned_reactions
        scanned_reactions += 1
        await leaderBot[payload.guild_id].raw_react(payload)
    except Exception as e:
        print('on_raw_reaction_add:', e)
        traceback.print_exc()
    return

print('ready, steady, go')
client.run(TOKEN)

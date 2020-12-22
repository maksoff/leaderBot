import json

def beautify(tmp):
    if type(tmp) != str:
        tmp = f'{tmp:.3f}'
    tmp = tmp.split('.')
    tmp[0] = ''.join([x if (i%3 or i == 0) else x + '\u202F' for i, x in enumerate(tmp[0][::-1])][::-1])
    if len(tmp) == 2:
        while tmp[1] and tmp[1][-1] == '0':
            tmp[1] = tmp[1][:-1]
        if not tmp[1]:
            del tmp[1]
    return '.'.join(tmp)

class json_class():
    j = {}
    j['aChallenge'] = []
    j['aChallengeType'] = []
    j['aPlayer'] = []
    j['aSubmission'] = []
    iVersion = 11
    aPoint = (10.0, 6.0, 4.0, 2.0, 1.0)
    oRankByChallenge = {}

    @staticmethod
    def find(dicts, *key_val, **kwargs):
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
    
    def getPoints(s, n, points=None):
        if not points:
            points = s.aPoint
        if len(points) == 1:
            return points[0]
        return points[n] if n < len(points) else 0
    
    def get_lb_message(s):
        return s.j.get('iLeaderboardChannel'), s.j.get('iLeaderboardMessage')
    
    def set_lb_message(s, ch, msg):
        s.j['iLeaderboardChannel'] = ch
        s.j['iLeaderboardMessage'] = msg
        
    def dump(s):
        s.j['iVersion'] = s.iVersion
        return json.dumps(s.j, indent=4, sort_keys=False)
    
    def load(s, f):
        j = json.load(f)
        if j['iVersion'] < s.iVersion: return
        s.j = j
        s.calculate_rating()
        
    def result_leaderboard(s):
        response = '**Actual ranking**\n'
        if not s.j.get('aPlayer'):
            return response + 'no submissions'
        for p in sorted(s.j.get('aPlayer', []), key = lambda i: i['iPoints'], reverse = True):
            if p.get('bDisabled'):
                continue
            user = p.get('iID', None)
            if user:
                user = '<@{}>'.format(user)
            else:
                user = '@' + p.get('sName')
            response += '{}. {} with **{}** points\n'.format(p['iRank'], user, p['iPoints'])
        return response[:-1]

    def list_of_challenges(s):
        if not s.j.get('aChallenge'):
            return []
        try:
            return (i['sName'] for i in s.j['aChallenge'])
        except:
            return []
    
    def result_challenge(s, ChallengeName, ignoreScore=True):
        '''depreciated'''
        response = ''
        resp = []
        if not ChallengeName in s.oRankByChallenge:
            return 'Still no submissions in challenge **{}**'.format(ChallengeName)
        for key, value in s.oRankByChallenge[ChallengeName].items():
            modus = s.find(s.j['aChallengeType'], sName=key).get('sNick', key)
            response += 'Challenge **{}** in modus **{}**\n'.format(ChallengeName, modus)
            value.sort(key=lambda x: x['iRank'])
            for val in value:
                p = s.find(s.j.get('aPlayer', []), iID=val['iUserID'])
                user = p.get('iID', None)
                if user:
                    user = '<@{}>'.format(user)
                else:
                    user = '@' + p.get('sName')
                if ignoreScore:
                    response += '{:4}. {} at the {}{} try => **{}** points\n'.format(val['iRank'],
                                                                                    user,
                                                                                    val['iSubmissionId'] + 1,
                                                                                    s.suffix(val['iSubmissionId'] + 1),
                                                                                    beautify(val['iPoints']))
                else:
                    response += '{:4}. {} with {} at the {}{} try => **{}** points\n'.format(val['iRank'],
                                                                                            user,
                                                                                            beautify(val['fScore']),
                                                                                            val['iSubmissionId'] + 1,
                                                                                            s.suffix(val['iSubmissionId'] + 1),
                                                                                            beautify(val['iPoints']))
        return response[:-1]
    
    def result_challenge_embed(s, ChallengeName, ignoreScore=True):
        r_list = []
        if not ChallengeName in s.oRankByChallenge:
            return [{'name':f'Challenge {ChallengeName}',
                     'value':'Still no submissions'}]
        for key, value in s.oRankByChallenge[ChallengeName].items():
            challengeType = s.find(s.j['aChallengeType'], sName=key)
            response = ''
            not_same = len(s.find(s.j.get('aChallenge'), sName=ChallengeName).get('aPoints', [])) != 1
            value.sort(key=lambda x: x['iRank'])
            for val in value:
                user = f"<@{val['iUserID']}>"
                if not_same:
                    response += f"{val['iRank']}. "
                response += f"{user}"
                if not ignoreScore:
                    response += f" with {beautify(val['fScore'])}"
                if not_same:
                    response += f" at the {val['iSubmissionId'] + 1}{s.suffix(val['iSubmissionId'] + 1)} try"
                response += f" => **{beautify(val['iPoints'])}** points\n"
                
            r_list.append({'name':'Modus **{}**'.format(challengeType.get('sNick', key)),
                           'value':response,
                           'index':s.j['aChallengeType'].index(challengeType),
                           'fMultiplier':float(challengeType.get('fMultiplier', 1))})
            
        r_list.sort(key = lambda x: (x['fMultiplier'], x['index']))
        return r_list

    def print_all(s):
        result = ''
        for i in s.list_of_challenges():
            if s.result_challenge(i):
                result += s.result_challenge(i, ignoreScore=False) + '\n'
        result += s.result_leaderboard()
        return result

    @staticmethod
    def suffix(n):
        if 10 <= n <= 20:
            return 'th'
        elif n%10 == 1:
            return 'st'
        elif n%10 == 2:
            return 'nd'
        elif n%10 == 3:
            return 'rd'
        else:
            return 'th'

    def get_rank(s, user_id):
        player = s.find(s.j.get('aPlayer', []), iID=user_id)
        if player:
            rank = player.get('iRank', None)
            points = player.get('iPoints', None)
        if player and rank and points:    
            return 'Ranked **{}**{} (out of {} members) with **{}** points'.format(rank, s.suffix(rank), len(s.j.get('aPlayer', [])), points)
        else:
            return 'Still no points. Submit some challenges!'

        
    def get_top(s, limit = 10):
        response = ''
        players = sorted(s.j.get('aPlayer', []), key=lambda x: float(x.get('iPoints')), reverse=True)
        if not players:
            return 'no submissions'
        for player in players:
            if player.get('bDisabled'):
                continue
            user = player.get('iID', None)
            if user:
                user = '<@{}>'.format(user)
            else:
                user = '@' + player.get('sName')
            rank = player.get('iRank')
            points = player.get('iPoints')
            if limit:
                if rank > limit:
                    break
            if player and rank and points:
                response += '\n**{:4}.** {} with **{}** points'.format(rank, user, points)
        return response

    def get_active(s, limit=7):
        response = []
        full_ch = 3 #how many challenges with full score
        half_ch = 3
        full_points = 10 #how many points for full score challenge
        half_points = 5
        full_list = list(s.list_of_challenges())[-full_ch:]
        half_list = list(s.list_of_challenges())[-full_ch-half_ch:-full_ch]
        for sub in s.j.get('aSubmission', []):
            player = s.find(s.j.get('aPlayer'), iID=sub.get('iUserID'))
            if player.get('bDisabled', False):
                continue
            points = 0
            if sub.get('sChallengeName') in full_list:
                points = full_points
            if sub.get('sChallengeName') in half_list:
                points = half_points
            if not points:
                continue
            points += sub.get('iSubmissionId', 0) * 2
            item = s.find(response, iID=sub.get('iUserID'))
            if item:
                item['iPoints'] = item.get('iPoints', 0) + points
            else:
                response.append({'iID':sub.get('iUserID'),
                                 'iPoints':points,
                                 'iDiscriminator':player.get('iDiscriminator'),
                                 'sName':player.get('sName')})
        response.sort(key=lambda x: x.get('iPoints', 0), reverse=True)
        last_rank = 0
        last_points = None
        for i, item in enumerate(response, 1):
            if item['iPoints'] != last_points:
                last_rank = i
            item['iRank'] = last_rank

        response = [x for x in response if x.get('iRank') <= limit]
        return response
            
        
        
    
    def calculate_rating(s):
        s.oRankByChallenge = {}
        for sub in s.j.get('aSubmission', []):
            if not sub['sChallengeName'] in s.oRankByChallenge:
                s.oRankByChallenge[sub['sChallengeName']] = {}
            if not sub['sChallengeTypeName'] in s.oRankByChallenge[sub['sChallengeName']]:
                s.oRankByChallenge[sub['sChallengeName']][sub['sChallengeTypeName']] = []
            oRCT = s.oRankByChallenge[sub['sChallengeName']][sub['sChallengeTypeName']]
            bHigh = s.find(s.j['aChallengeType'], 'sName', sub['sChallengeTypeName'])['bHigherScore']
            oP = s.find(oRCT, iUserID=sub['iUserID'])
            if (oP):
                if (((oP['fScore'] > sub['fScore']) and not bHigh) or ((oP['fScore'] < sub['fScore']) and bHigh)):
                    oP['fScore'] = sub['fScore']
                    oP['iSubmissionId'] = sub['iSubmissionId']
            else:
                oRCT.append(sub.copy())
                
        for cc in s.j.get('aSubmission', []):
            try:
                del cc['iRank']
                del cc['iPoints']
            except:
                pass
            
        for rbc, o in s.oRankByChallenge.items():
            for ct, c in o.items():
                bD = s.find(s.j['aChallengeType'], 'sName', ct)['bHigherScore']
                bSpecial = s.find(s.j['aChallengeType'], 'sName', ct).get('bSpecial', False)
                c.sort(key=lambda x: float(x['fScore']), reverse=bD)
                
                iRank = None
                lastScore = None
                for i, cc in enumerate(c, 1):
                    if lastScore != cc['fScore']:
                        lastScore = cc['fScore']
                        iRank = i
                    cc['iRank'] = iRank
                    challenge = s.find(s.j['aChallenge'], 'sName', rbc)
                    if bSpecial: # special counting
                        iScore = int(cc['fScore']) # expected 1, 2, 3, ...
                        aPoints = challenge.get('aPoints', s.aPoint)
                        if bD:
                            iScore = len(aPoints) - iScore # transform to index 
                        else:
                            iScore -= 1 # transform to index
                        if iScore < 0: iScore = 0
                        cc['iPoints'] = aPoints[iScore] if iScore < len(aPoints) else 0
                    else:
                        cc['iPoints'] = s.getPoints(iRank - 1, points=challenge.get('aPoints'))*float(s.find(s.j['aChallengeType'], 'sName', ct).get('fMultiplier', 1))
                    oS = s.find(s.j.get('aSubmission', []), sChallengeName=rbc, sChallengeTypeName=ct, iUserID=cc['iUserID'], fScore=cc['fScore'])
                    oS['iRank'] = iRank
                    oS['iPoints'] = cc['iPoints']

        for p in s.j.get('aPlayer', []):
            p['iPoints'] = p.get('iStaticPoints', 0) + sum(x.get('iPoints', 0) for x in s.j.get('aSubmission', []) if x['iUserID'] == p['iID'])
            if p['iPoints'] == int(p['iPoints']): p['iPoints'] = int(p['iPoints'])
            
        if not s.j.get('aPlayer'):
            return
        
        s.j['aPlayer'].sort(key=lambda x: float(x['iPoints']), reverse=True)
        
        curRank = None
        lastPoints = None
        i = 0
        for p in s.j.get('aPlayer', []):
            if p.get('bDisabled'):
                continue
            i += 1
            if p['iPoints'] != lastPoints:
                lastPoints = p['iPoints']
                curRank = i
            p['iRank'] = curRank
            
        return
       
if __name__ == '__main__':

    j = json_class()

    with open("715549991212548216.txt", 'r') as f:
        j.load(f)

    #print(j.dump())
    print(j.print_all())

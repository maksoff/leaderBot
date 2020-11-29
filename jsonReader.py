import json

class json_class():
    j = None
    iVersion = 10
    aPoint = (10, 6, 4, 2, 1)
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
    
    def getPoints(s, n):
        return s.aPoint[n] if n < len(s.aPoint) else 0
    
    def get_lb_message(s):
        return s.j['iLeaderboardChannel'], s.j['iLeaderboardMessage']
    
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
        responce = '**Actual ranking**\n'
        for p in sorted(s.j['aPlayer'], key = lambda i: i['iPoints'], reverse = True):
            user = p.get('iID', None)
            if user:
                user = '<@{}>'.format(user)
            else:
                user = '@' + p.get('sName')
            responce += '{:4}. {} with **{}** points\n'.format(p['iRank'], user, p['iPoints'])
        return responce[:-1]

    def list_of_challenges(s):
        try:
            return (i['sName'] for i in s.j['aChallenge'])
        except:
            return []
    
    def result_challenge(s, ChallengeName, ignoreScore=True):
        responce = ''
        if not ChallengeName in s.oRankByChallenge:
            return 'Still no submissions in challenge **{}**'.format(ChallengeName)
        for key, value in s.oRankByChallenge[ChallengeName].items():
            modus = s.find(s.j['aChallengeType'], sName=key).get('sNick', key)
            responce += 'Challenge **{}** in modus **{}**\n'.format(ChallengeName, modus)
            value.sort(key=lambda x: x['iRank'])
            for val in value:
                p = s.find(s.j['aPlayer'], sName=val['sPlayerName'])
                user = p.get('iID', None)
                if user:
                    user = '<@{}>'.format(user)
                else:
                    user = '@' + p.get('sName')
                if val['iPoints'] == int(val['iPoints']):
                    val['iPoints'] = int(val['iPoints'])
                if ignoreScore:
                    responce += '{:4}. {} at the {}. try => **{}** points\n'.format(val['iRank'], user, val['iSubmissionId'] + 1, val['iPoints'])
                else:
                    responce += '{:4}. {} with {} at the {}. try => **{}** points\n'.format(val['iRank'], user, val['fScore'], val['iSubmissionId'] + 1, val['iPoints'])
        return responce[:-1]

    def print_all(s):
        result = ''
        for i in s.list_of_challenges():
            if s.result_challenge(i):
                result += s.result_challenge(i, ignoreScore=False) + '\n'
        result += s.result_leaderboard()
        return result

    def get_rank(s, user_id):
        player = s.find(s.j['aPlayer'], iID=user_id)
        if player:
            rank = player.get('iRank', None)
            points = player.get('iPoints', None)
        if player and rank and points:
            return '**{}.** place (from {}) with **{}** points'.format(rank, len(s.j['aPlayer']), points)
        else:
            return 'You need to earn some points. Submit some challenges!'

        
    def get_top(s, limit = 10):
        responce = ''
        players = sorted(s.j['aPlayer'], key=lambda x: float(x.get('iPoints')), reverse=True)
        if not players:
            return 'no submissions'
        for player in players:
            user = player.get('iID', None)
            if user:
                user = '<@{}>'.format(user)
            else:
                user = '@' + player.get('sName')
            rank = player.get('iRank')
            points = player.get('iPoints')
            if rank > limit: break
            if player and rank and points:
                responce += '\n**{:4}.** {} with **{}** points'.format(rank, user, points)
        return responce
        
    
    def calculate_rating(s):
        s.oRankByChallenge = {}
        for sub in s.j['aSubmission']:
            if not sub['sChallengeName'] in s.oRankByChallenge:
                s.oRankByChallenge[sub['sChallengeName']] = {}
            if not sub['sChallengeTypeName'] in s.oRankByChallenge[sub['sChallengeName']]:
                s.oRankByChallenge[sub['sChallengeName']][sub['sChallengeTypeName']] = []
            oRCT = s.oRankByChallenge[sub['sChallengeName']][sub['sChallengeTypeName']]
            bHigh = s.find(s.j['aChallengeType'], 'sName', sub['sChallengeTypeName'])['bHigherScore']
            oP = s.find(oRCT, 'sPlayerName', sub['sPlayerName'])
            if (oP):
                if (((oP['fScore'] > sub['fScore']) and not bHigh) or ((oP['fScore'] < sub['fScore']) and bHigh)):
                    oP['fScore'] = sub['fScore']
                    oP['iSubmissionId'] = sub['iSubmissionId']
            else:
                oRCT.append(sub.copy())
                
        for cc in s.j['aSubmission']:
            try:
                del cc['iRank']
                del cc['iPoints']
            except:
                pass
            
        for rbc, o in s.oRankByChallenge.items():
            for ct, c in o.items():
                bD = s.find(s.j['aChallengeType'], 'sName', ct)['bHigherScore']
                c.sort(key=lambda x: float(x['fScore']), reverse=bD)
                
                iRank = None
                lastScore = None
                for i, cc in enumerate(c, 1):
                    if lastScore != cc['fScore']:
                        lastScore = cc['fScore']
                        iRank = i
                    cc['iRank'] = iRank
                    cc['iPoints'] = s.getPoints(iRank - 1)*float(s.find(s.j['aChallengeType'], 'sName', ct).get('fMultiplier', 1))
                    oS = s.find(s.j['aSubmission'], sChallengeName=rbc, sChallengeTypeName=ct, sPlayerName=cc['sPlayerName'], fScore=cc['fScore'])
                    oS['iRank'] = iRank
                    oS['iPoints'] = cc['iPoints']

        for p in s.j['aPlayer']:
            p['iPoints'] = p.get('iStaticPoints', 0) + sum(x.get('iPoints', 0) for x in s.j['aSubmission'] if x['sPlayerName'] == p['sName'])
            if p['iPoints'] == int(p['iPoints']): p['iPoints'] = int(p['iPoints'])
                
        s.j['aPlayer'].sort(key=lambda x: float(x['iPoints']), reverse=True)
        
        curRank = None
        lastPoints = None
        for i, p in enumerate(s.j['aPlayer'], 1):
            if p['iPoints'] != lastPoints:
                lastPoints = p['iPoints']
                curRank = i
            p['iRank'] = curRank
            
        return
       
if __name__ == '__main__':

    j = json_class()

    with open("message.txt", 'r') as f:
        j.load(f)

    #print(j.dump())
    print(j.print_all())

# character archive
blue_square = '\U0001f7e6'

blue_letters = (
                '\U0001f1e6',
                '\U0001f1e7',
                '\U0001f1e8',
                '\U0001f1e9',
                '\U0001f1ea',
                '\U0001f1eb',
                '\U0001f1ec',
                '\U0001f1ed',
                '\U0001f1ee',
                '\U0001f1ef',
                '\U0001f1f0',
                '\U0001f1f1',
                '\U0001f1f2',
                '\U0001f1f3',
                '\U0001f1f4',
                '\U0001f1f5',
                '\U0001f1f6',
                '\U0001f1f7',
                '\U0001f1f8',
                '\U0001f1f9',
                '\U0001f1fa',
                '\U0001f1fb',
                '\U0001f1fc',
                '\U0001f1fd',
                '\U0001f1fe',
                '\U0001f1ff',
                )

blue_digits = (
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
                )

cr_name = ':coolrocket:'

def replace_letters(word):
    ''' returns emoji list as first argument '''
    ''' and second argumnet True if all letters are unique '''
    if word is None: return
    cool_rocket = (word.find(cr_name) != -1)*(len(cr_name) - 1)
    word = word.replace(cr_name, '<a:CoolChallengeAccepted:732098507137220718>')
    w = list(word.lower())
    emoji = []
    bEm = 0
    lEm = []
    for i, c in enumerate(w):
        # try to recognize special emoji
        if (c == '<') and ('>' in w[i:]):
            bEm = 1
            lEm.append(c)
        elif bEm:
            if (bEm == 1) and (c == ':'):
                bEm = 2
                lEm.append(c)
            elif (bEm == 1) and (c == 'a'):
                lEm.append(c)
            elif (bEm == 2) and (c == '>') and (len(lEm) > 20):
                # looks good, I suppose
                lEm.append(c)
                emoji.append(''.join(lEm))
                lEm = []
                bEm = 0
            elif (bEm == 2) and (c != ' '):
                lEm.append(c)
            else:
                #something wrong, cancel!
                lEm.append(c)
                bEm = 0
                emoji += lEm
                lEm = []
            
        # nothing special, just do the usual work
        elif c == ' ':
            emoji.append(blue_square)
        elif '0' <= c <= '9':
            emoji.append(blue_digits[ord(c) - ord('0')])
        elif c == '\n':
            emoji.append('\n')
        elif 'a' <= c <= 'z':
            try:
                emoji.append(blue_letters[ord(c) - ord('a')])
            except Exception as e:
                ...
        elif c == '!':
            emoji.append('\u2757')
        elif c == '?':
            emoji.append('\u2753')
        else:
            try:
                emoji.append(c)
            except:
                ...
            
    print(emoji)
    print(len(w), cool_rocket, len(set(emoji)), w)
    return emoji, (len(w) - cool_rocket) == len(set(emoji))

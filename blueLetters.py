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

def replace_letters(word):
    ''' returns emoji list as first argument '''
    ''' and second argumnet True if all letters are unique '''
    if word is None: return
    w = list(word.lower())
    emoji = []
    for c in w:
        if c == ' ':
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
        else:
            try:
                emoji.append(c)
            except:
                ...
            

    return emoji, len(w) == len(set(emoji))

import itertools


with open('san_strings.txt', 'r') as f:
    san_strings = f.read().splitlines()


spoken_san_strings = set()

for i, san_string in enumerate(san_strings):
    words = []

    idx = 0
    while idx < len(san_string):
        c = san_string[idx]

        if c.isupper():
            if c == 'N':
                words.append('knight')
            elif c == 'B':
                words.append('bishop')
            elif c == 'R':
                words.append('rook')
            elif c == 'Q':
                words.append('queen')
            elif c == 'K':
                words.append('king')
        elif c == 'x':
            if san_string[0].islower():
                # Pawn captures only
                # Ex. 'e takes d 5' or 'e d 5'
                assert len(words) == 1
                file = words.pop()
                words.append((f'{file} takes', 'takes'))
            else:
                # Non-pawn caputures
                if len(words) == 1:
                    piece = words.pop()
                    words.append((f'{piece} takes', 'takes'))
                else:
                    words.append('takes')

            # Destination of capture
            file, rank = san_string[idx+1: idx+3]
            assert file in 'abcdefgh'
            assert rank in '12345678'
            idx += 3

            # Ex. 'rook takes' or 'rook takes e 4' or 'rook takes rook'
            words.append(('', f'{file} {rank}', 'pawn', 'knight', 'bishop', 'rook', 'queen'))
        elif c == '=':
            words.append(('', 'equals'))
            # break
        else:
            words.append(c)

        idx += 1

    if all(isinstance(w, str) for w in words):
        spoken_san_strings.add(' '.join(words))
        continue

    # Enumerate every combination of different ways of saying each phrase
    for phrase_combo in list(list(e) for e in itertools.product(*(w for w in words if not isinstance(w, str)))):
        phrase_words = []
        for word in words:
            if isinstance(word, str):
                phrase_words.append(word)
                continue
            
            phrase_words.append(phrase_combo.pop(0))

        assert not phrase_combo

        spoken_san_strings.add(' '.join(w for w in phrase_words if w))


with open('spoken_san_strings.txt', 'w') as f:
    # f.write('\n'.join(spoken_san_strings))
    f.write('\n'.join(sorted(spoken_san_strings, key=lambda s: (len(s), s))))

print(f'({len(spoken_san_strings)}) Done!')

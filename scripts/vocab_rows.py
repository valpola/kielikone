import re, glob, os

S = '/private/tmp/claude-501/-Users-harri-hobby-language-learning/6f55ed4d-cbf5-41d3-b03b-5b91370cb103/scratchpad'
DOT = '̇'   # combining dot above


def fold(s):
    """Normalise Turkish text for matching.

    pdftotext renders capital 'İ' as a dotless i (or I) plus a combining dot,
    sometimes with a space after it, so 'İŞÇİ' arrives as 'ı' + U+0307 + ' şçi'.
    Strip the dot and close the gap, then fold ı->i so the repaired 'ışçi' and
    the query 'işçi' meet. Circumflexes fold as they do in the app's matcher.
    """
    s = s.replace('İ', 'i').lower()          # before lower(): it expands İ to i+dot
    s = re.sub('[Iıi]' + DOT + r'\s*', 'i', s)
    s = s.replace(DOT, '')
    for a, b in (('â', 'a'), ('î', 'i'), ('û', 'u'), ('ı', 'i')):
        s = s.replace(a, b)
    return s


POS = {'isim', 'sifat', 'fiil', 'zarf', 'edat', 'baglac', 'bağlaç', 'zamir',
       'ünlem', 'unlem', 'kelime', 'anlami'}


def rowlike(l):
    """Is this line a vocabulary-table row rather than prose?"""
    t = l.strip()
    if not t:
        return True                     # blanks are fine inside a list
    if fold(t) in POS:
        return True
    if len(t) > 46:
        return False                    # prose
    if re.search(r'[:;]|\)\s*$|\.\s*$|\?|!', t):
        return False
    return True


SUBS = [f"{u}{c}" for u in '123456' for c in 'ABC']


def rows():
    """subunit -> set of folded vocabulary rows.

    The per-subunit PDFs are pure vocabulary lists (title, 'KELİME LİSTESİ',
    then POS-grouped rows), covering A1-0A..6C and A2-1A..2B. The A2 master
    coursebook supplies 2C..6C via its 18 'KELİME LİSTESİ' blocks, which occur
    in unit order.
    """
    out = {}
    for p in sorted(glob.glob(f'{S}/units/*.txt')):
        b = os.path.basename(p)[:-4]
        key = f"{b[:2].upper()}-{b[2:].upper()}"
        out.setdefault(key, set()).update(
            fold(l.strip()) for l in open(p, encoding='utf-8') if l.strip())
    raw = open(f'{S}/A2_coursebook.txt', encoding='utf-8').read().split('\n')
    heads = [i for i, l in enumerate(raw)
             if i > 200 and re.search(r'KEL[İIı]ME L[İIı]STES[İIı]', fold(l), re.I)]
    assert len(heads) == len(SUBS), f"{len(heads)} lists, expected {len(SUBS)}"
    for h, sub in zip(heads, SUBS):
        key, bad, i = f"A2-{sub}", 0, h + 1
        while i < len(raw) and bad < 3:
            if rowlike(raw[i]):
                bad = 0
                if raw[i].strip():
                    out.setdefault(key, set()).add(fold(raw[i].strip()))
            else:
                bad += 1
            i += 1
    return out

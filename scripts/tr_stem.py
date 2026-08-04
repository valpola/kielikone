"""A deliberately rough Turkish stemmer, for sweep dedup only.

Not linguistics: the job is to stop conjugations of known verbs from showing up
as new vocabulary. It over-strips happily — a false "already known" is cheaper
here than a list too noisy to read, and everything surviving is reviewed by hand.
"""
import re

VOWELS = "aeıioöuü"

# longest first, so -iyorum goes before -im
SUFFIXES = [
    "abilirim","ebilirim","abilir","ebilir","abil","ebil",
    "iyorum","ıyorum","uyorum","üyorum","iyorsun","ıyorsun","uyorsun","üyorsun",
    "iyoruz","ıyoruz","uyoruz","üyoruz","iyorlar","ıyorlar","uyorlar","üyorlar",
    "iyor","ıyor","uyor","üyor",
    "acağım","eceğim","acaksın","eceksin","acak","ecek",
    "malıyım","meliyim","malı","meli",
    "mışım","mişim","muşum","müşüm","mış","miş","muş","müş",
    "dım","dim","dum","düm","tım","tim","tum","tüm",
    "dın","din","dun","dün","tın","tin","tun","tün",
    "dık","dik","duk","dük","tık","tik","tuk","tük",
    "dı","di","du","dü","tı","ti","tu","tü",
    "alım","elim","ayım","eyim","sın","sin","sun","sün",
    "arım","erim","irim","ırım","urum","ürüm",
    "mak","mek","ması","mesi","ma","me",
    "lar","ler","ları","leri","lık","lik","luk","lük","lı","li","lu","lü",
    "sız","siz","suz","süz","cı","ci","cu","cü","çı","çi","çu","çü",
    "ında","inde","unda","ünde","dan","den","tan","ten","da","de","ta","te",
    "ını","ini","unu","ünü","nın","nin","nun","nün",
    "ım","im","um","üm","ın","in","un","ün","ı","i","u","ü",
    "ya","ye","a","e","la","le","yla","yle","ile","ki",
    "ar","er","ir","ır","ur","ür",
]

# Turkish roots go down to two letters (al-, et-, ye-), so the floor must too.
def strip_suffixes(word: str, floor: int = 2) -> str:
    changed = True
    while changed and len(word) > floor:
        changed = False
        for s in SUFFIXES:
            if word.endswith(s) and len(word) - len(s) >= floor:
                word = word[: -len(s)]
                changed = True
                break
    return word

SOFT = {"b": "p", "c": "ç", "d": "t", "ğ": "k"}

def key(word: str) -> str:
    """Comparison key: stemmed, with the vowel alternations Turkish inflection
    causes folded together, and final softening undone."""
    w = word.lower()
    w = strip_suffixes(w)
    if w and w[-1] in SOFT:
        w = w[:-1] + SOFT[w[-1]]
    for a, b in (("â", "a"), ("î", "i"), ("û", "u")):
        w = w.replace(a, b)
    # e/i, a/ı, o/u, ö/ü alternate under raising and harmony
    for group, rep in (("eiîı", "e"), ("aâ", "a"), ("ou", "o"), ("öü", "ö")):
        for ch in group:
            w = w.replace(ch, rep)
    return w

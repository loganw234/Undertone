"""Seeds built so that a chosen word comes out at a chosen place, and a generator that is wrong on purpose.

WHY. A table's far entries are reached about once in 2^63 draws: no seed that
is drawn will ever show that the source's search reaches its last entry. But
SplitMix64's mix can be undone, so for any word W and any word index i there
is exactly one seed whose word i is W. `seed_for` finds it. A bench then
ASSERTS THROUGH THE MODEL, not through this file, that the model's word there
is W: this code is a way of searching, and the model is what says the search
succeeded.

`boundary_words` gives, for every magnitude a table can yield, the words on
each side of its span with both signs, as tests/test_mod_a_tails.py does for
the model's own stream.

`wrong_words` is SplitMix64 with constants handed in, for the bench's controls
on the model side: a generator with one bit of one constant changed.

WHAT THIS IS NOT: an authority. Nothing here decides what a word or a sample
should be.
"""
MASK = (1 << 64) - 1
GAMMA = 0x9E3779B97F4A7C15
MIX1 = 0xBF58476D1CE4E5B9
MIX2 = 0x94D049BB133111EB


def _undo_shift(z, by):
    """The x with x ^ (x >> by) == z, for a 64-bit z."""
    x = z
    for _ in range(64 // by + 1):
        x = z ^ (x >> by)
    return x


def unmix(word):
    """The 64-bit sum the mix was given to make this word."""
    z = _undo_shift(word, 31)
    z = (z * pow(MIX2, -1, 1 << 64)) & MASK
    z = _undo_shift(z, 27)
    z = (z * pow(MIX1, -1, 1 << 64)) & MASK
    return _undo_shift(z, 30)


def seed_for(word, i):
    """The seed whose word number i is `word`."""
    return (unmix(word) - GAMMA * (i + 1)) & MASK


def boundary_words(table):
    """[(word, sample, magnitude)] for every magnitude the table can yield: the lowest and the highest
    63-bit number that give it, each with both signs."""
    out = []
    for m, h in enumerate(table):
        below = table[m - 1] if m else 0
        if h > below:
            for u in (below, h - 1):
                for sign in (0, 1):
                    out.append(((u << 1) | sign, -m if sign else m, m))
    return out


def wrong_words(seed, count, gamma=GAMMA, mix1=MIX1, mix2=MIX2):
    """The first `count` words of a generator with these constants. With the defaults it is SplitMix64."""
    out = []
    for i in range(1, count + 1):
        z = (seed + gamma * i) & MASK
        z = ((z ^ (z >> 30)) * mix1) & MASK
        z = ((z ^ (z >> 27)) * mix2) & MASK
        out.append(z ^ (z >> 31))
    return out

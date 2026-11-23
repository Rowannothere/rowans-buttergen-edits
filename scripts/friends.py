"""BUTTERGEN: friendships. Friends and best friends from the relationship numbers, what friends do for
each other, falling out and making up. Runs from feelings.on_skip at the full moon. Texts:
events/friends.json. Design: Notes\\Buttergen friendships and families (design draft).txt"""

from random import choice, choices as weighted_choice, random

from scripts.cat.cats import Cat
from scripts.cat.enums import CatAge, CatRank
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource

FRIEND_LIKE, FRIEND_COMFORT = 40, 20
BEST_LIKE, BEST_COMFORT = 70, 50
BEST_KEEP_LIKE, BEST_KEEP_COMFORT = 60, 40
DRIFT_AT = 25
DROP, DROP_MOONS, FALL_OUT_CHANCE = 15, 2, 0.05
FALL_OUT_HIT = 10
MAKE_UP_CHANCE, FELL_OUT_MOONS = 1 / 6, 24
EVENT_CHANCE, BEST_EVENT_CHANCE, EVENTS_MAX = 1 / 6, 1 / 3, 2
BEST_GRIEF = 4
PATROL_BONUS, BEST_PATROL_BONUS = 4, 6  # +3% and +5% of the patrol roll, which is out of 120
PATROL_WEIGHT, BEST_PATROL_WEIGHT = 2, 4
COVER_KEEP, COVER_REPORT = 2, 0.5
SENIOR_AGES = (CatAge.ADULT, CatAge.SENIOR_ADULT, CatAge.SENIOR)
MAKE_UP = "makeup"


def texts() -> dict:
    return load_lang_resource("events/friends.json")


def _record() -> dict:
    from scripts.feelings import _record as rec

    r = rec()
    r.setdefault("fell_out", {})
    r.setdefault("like_hist", {})
    return r


def key(a, b) -> str:
    return "|".join(sorted((a.ID, b.ID)))


def _cats(k):
    return [Cat.fetch_cat(i) for i in k.split("|")]


def _can_have_friends(cat) -> bool:
    from scripts.feelings import _alive_in_clan, _grown

    return _alive_in_clan(cat) and _grown(cat)


def is_friend(a, b) -> bool:
    if not a or not b or a is b or not game.clan:
        return False
    return key(a, b) in _record().get("friends", [])


def is_best(a, b) -> bool:
    if not a or not b or a is b or not game.clan:
        return False
    return key(a, b) in _record().get("best", [])


def fell_out(a, b) -> bool:
    return bool(a and b and a is not b and game.clan) and key(a, b) in _record()["fell_out"]


def friends_of(cat) -> list:
    out = []
    for k in _record().get("friends", []):
        ids = k.split("|")
        if cat.ID in ids:
            other = Cat.fetch_cat(ids[0] if ids[1] == cat.ID else ids[1])
            if other:
                out.append(other)
    return out


def best_friend_of(cat):
    for k in _record().get("best", []):
        ids = k.split("|")
        if cat.ID in ids:
            return Cat.fetch_cat(ids[0] if ids[1] == cat.ID else ids[1])
    return None


def _both(a, b, stat) -> int:
    from scripts.feelings import _stat

    return min(_stat(a, b, stat), _stat(b, a, stat))


def _qualifies(a, b, like, comfort) -> bool:
    return _both(a, b, "like") >= like and _both(a, b, "comfort") >= comfort


def _post(text_key, a, b, force=False):
    from scripts import feelings

    t = texts()[text_key]
    # feelings._post reads its own texts, so render here and hand over the finished line
    return feelings._post_text(choice(t) if isinstance(t, list) else t, a, b, force=force)


# what friends do

def patrol_bonus(cats) -> int:
    cats = [c for c in cats if c]
    bonus = 0
    for i, a in enumerate(cats):
        for b in cats[i + 1:]:
            if is_best(a, b):
                return BEST_PATROL_BONUS
            if is_friend(a, b):
                bonus = PATROL_BONUS
    return bonus


def pick_for_patrol(pool, k, current) -> list:
    """the game's random picks, leaning toward cats who are friends with the ones already going"""
    pool = [c for c in pool if c not in current]
    picked = []
    for _ in range(min(k, len(pool))):
        group = list(current) + picked
        weights = [1 + sum(BEST_PATROL_WEIGHT if is_best(c, g) else PATROL_WEIGHT if is_friend(c, g) else 0
                           for g in group) for c in pool]
        cat = weighted_choice(pool, weights)[0]
        picked.append(cat)
        pool.remove(cat)
    return picked


def senior_friend(cat) -> bool:
    """a friend who's a senior warrior speaks up for mercy"""
    return any(f.status.rank == CatRank.WARRIOR and f.age in SENIOR_AGES and not f.status.is_shunned()
               for f in friends_of(cat) if _can_have_friends(f))


def cover_scores(witness, offender, scores):
    """friends keep a friend's misdeed quiet more often"""
    if is_friend(witness, offender):
        scores["keep"] *= COVER_KEEP
        if "report" in scores:
            scores["report"] *= COVER_REPORT


def grieving_for(cat):
    """a best friend's death is grieved for longer"""
    from scripts.feelings import data

    d = data(cat)
    dead = Cat.fetch_cat(d.get("remembers"))
    if dead and dead.dead and game.clan.age - d.get("lost_at", -99) <= BEST_GRIEF:
        return dead
    return None


def remembers(cat):
    from scripts.feelings import data

    dead = Cat.fetch_cat(data(cat).get("remembers"))
    return dead if dead and dead.dead else None


# falling out and making up

def fall_out(a, b):
    from scripts.feelings import _nudge

    rec = _record()
    k = key(a, b)
    if k in rec.get("friends", []):
        rec["friends"].remove(k)
    if k in rec.get("best", []):
        rec["best"].remove(k)
    rec["fell_out"][k] = game.clan.age
    rec["like_hist"].pop(k, None)
    for x, y in ((a, b), (b, a)):
        _nudge(x, y, like=-FALL_OUT_HIT, trust=-FALL_OUT_HIT)
    _post("fall_out", a, b)


def reported(offender, witness):
    """a friend who reports a friend's misdeed: they fall out"""
    if is_friend(offender, witness):
        fall_out(offender, witness)


def make_up_target(cat):
    """the cat this one fell out with, if they're still around"""
    rec = _record()
    for k in rec["fell_out"]:
        ids = k.split("|")
        if cat.ID in ids:
            other = Cat.fetch_cat(ids[0] if ids[1] == cat.ID else ids[1])
            if _can_have_friends(other):
                return other
    return None


def _make_up(a, b):
    rec = _record()
    k = key(a, b)
    rec["fell_out"].pop(k, None)
    if k not in rec.setdefault("friends", []):
        rec["friends"].append(k)
    _post("make_up", a, b)


def _make_ups():
    from scripts.feelings import want_of

    for cat in _clanmates():
        want = want_of(cat)
        if not want or want["kind"] != MAKE_UP:
            continue
        other = Cat.fetch_cat(want.get("cat"))
        if _can_have_friends(other) and fell_out(cat, other) and random() < MAKE_UP_CHANCE:
            _make_up(cat, other)
    rec = _record()
    for k, moon in list(rec["fell_out"].items()):
        a, b = _cats(k)
        if not a or not b or a.dead or b.dead or game.clan.age - moon >= FELL_OUT_MOONS:
            del rec["fell_out"][k]


# the full moon

def _clanmates() -> list:
    return [c for c in (Cat.fetch_cat(i) for i in game.clan.clan_cats) if _can_have_friends(c)]


def _lost(k, rec):
    """a friendship ended because a cat died or left. A best friend is remembered"""
    from scripts.feelings import data

    a, b = _cats(k)
    if k not in rec.get("best", []):
        return
    for alive, gone in ((a, b), (b, a)):
        if _can_have_friends(alive) and gone and gone.dead:
            d = data(alive)
            d["remembers"], d["lost_at"] = gone.ID, game.clan.age


def _mates_seen(cats):
    """a best friend's new mate takes up their time"""
    from scripts.feelings import _maybe_jealous, data

    for cat in cats:
        d = data(cat)
        had = "mates_seen" in d
        before = set(d.get("mates_seen", []))
        now = set(cat.mate)
        d["mates_seen"] = sorted(now)
        if not had or not now - before:
            continue
        best = best_friend_of(cat)
        if not best:
            continue
        for mate_id in now - before:
            mate = Cat.fetch_cat(mate_id)
            if mate and mate is not best:
                _maybe_jealous(best, mate, "friend", cat.ID)


def on_moon():
    from scripts.feelings import _maybe_jealous, data

    rec = _record()
    seeding = "friends" not in rec
    friends = rec.setdefault("friends", [])
    best = rec.setdefault("best", [])
    cats = _clanmates()
    in_clan = {c.ID for c in cats}
    events = 0

    # friends who died or left
    for k in list(friends):
        if not set(k.split("|")) <= in_clan:
            _lost(k, rec)
            friends.remove(k)
            if k in best:
                best.remove(k)
            rec["like_hist"].pop(k, None)

    # drifting apart, and falling out after a bad stretch
    for k in list(friends):
        a, b = _cats(k)
        like = _both(a, b, "like")
        hist = rec["like_hist"].setdefault(k, [])
        hist.insert(0, like)
        del hist[DROP_MOONS + 1:]
        if like < DRIFT_AT:
            friends.remove(k)
            if k in best:
                best.remove(k)
            rec["like_hist"].pop(k, None)
            if not seeding:
                _post("drift", a, b)
            continue
        if len(hist) > DROP_MOONS and hist[DROP_MOONS] - like >= DROP and random() < FALL_OUT_CHANCE:
            fall_out(a, b)

    # new friends
    for i, a in enumerate(cats):
        for b in cats[i + 1:]:
            k = key(a, b)
            if k in friends or k in rec["fell_out"] or not _qualifies(a, b, FRIEND_LIKE, FRIEND_COMFORT):
                continue
            friends.append(k)
            if not seeding:
                _post("friends", a, b)

    # best friends: one at a time, the closest pairs first
    for k in list(best):
        a, b = _cats(k)
        if k not in friends or not _qualifies(a, b, BEST_KEEP_LIKE, BEST_KEEP_COMFORT):
            best.remove(k)
    taken = {i for k in best for i in k.split("|")}
    candidates = []
    for k in friends:
        a, b = _cats(k)
        if a.ID in taken or b.ID in taken or not _qualifies(a, b, BEST_LIKE, BEST_COMFORT):
            continue
        candidates.append((_both(a, b, "like") + _both(a, b, "comfort"), k))
    for _score, k in sorted(candidates, reverse=True):
        a, b = _cats(k)
        if a.ID in taken or b.ID in taken:
            continue
        best.append(k)
        taken |= {a.ID, b.ID}
        if seeding:
            continue
        _post("best", a, b)
        # the one they used to be closest to may feel left out
        for cat, new in ((a, b), (b, a)):
            was = Cat.fetch_cat(data(cat).get("best_was"))
            if _can_have_friends(was) and was is not new and best_friend_of(was) is None:
                _maybe_jealous(was, new, "friend", cat.ID)
    for k in best:
        a, b = _cats(k)
        data(a)["best_was"], data(b)["best_was"] = b.ID, a.ID

    if not seeding:
        _mates_seen(cats)
    else:
        for cat in cats:
            data(cat)["mates_seen"] = sorted(cat.mate)
    _make_ups()

    # time together
    if seeding:
        return
    you = game.clan.your_cat
    # at most 2 a moon, the player's cat's friends first
    pairs = sorted(friends, key=lambda k: you is None or you.ID not in k.split("|"))
    for k in pairs:
        a, b = _cats(k)
        if events >= EVENTS_MAX or random() >= (BEST_EVENT_CHANCE if k in best else EVENT_CHANCE):
            continue
        events += 1
        both_warriors = all(c.status.rank in (CatRank.WARRIOR, CatRank.DEPUTY) for c in (a, b))
        lines = texts()["together"] + (texts()["together_warriors"] if both_warriors else [])
        from scripts import feelings

        a, b = (a, b) if random() < 0.5 else (b, a)
        feelings._post_text(choice(lines), a, b, force=you in (a, b))


def profile_lines(cat) -> str:
    t = texts()["profile"]
    out = ""
    best = best_friend_of(cat)
    if best:
        out += t["best"].replace("%{cat}", str(best.name)) + "\n"
    others = [f for f in friends_of(cat) if f is not best]
    if others:
        names = [str(f.name) for f in others[:4]]
        line = ", ".join(names) + (t["more"] if len(others) > 4 else "")
        out += t["friends"].replace("%{cats}", line) + "\n"
    gone = remembers(cat)
    if gone:
        out += t["remembers"].replace("%{cat}", str(gone.name)) + "\n"
    return out

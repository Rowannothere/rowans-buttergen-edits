"""BUTTERGEN: families. How close parents, kits and littermates are, proud and worried parents, sibling
rivals, growing apart, estranged families, family in other Clans and grandparents' stories. Runs from
feelings.on_skip at the full moon, after friends. Texts: events/families.json. Design: Notes\\Buttergen
friendships and families (design draft).txt"""

from random import choice, random

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource

CLOSE, ORDINARY, DISTANT, ESTRANGED = "close", "ordinary", "distant", "estranged"
CLOSE_AT, DISTANT_UNDER, ESTRANGED_UNDER = 50, 10, -20
PROUD, PROUD_LINE = 5, 1 / 2
WORRY_CHANCE = 1 / 2
PROTECT = 3
LITTERMATE_LIKE = 1
RIVAL_CHANCE, RIVAL_LIKE, RIVAL_LINE = 1 / 3, 1, 1 / 6
RIVAL_TRAITS = ("ambitious", "competitive")
DRIFT = 1
ESTRANGED_LINE = 1 / 12
MAKE_UP_CHANCE = 1 / 6
GATHERING = 1 / 2
FAMILY_GRIEF = 2
STORY_CHANCE = 1 / 6
EVENTS_MAX = 2
RESPECT_LOOK_UP = 30
SEE = "see"
PROUD_RANKS = (CatRank.APPRENTICE, CatRank.MEDICINE_APPRENTICE, CatRank.MEDIATOR_APPRENTICE,
               CatRank.WARRIOR, CatRank.MEDICINE_CAT, CatRank.MEDIATOR, CatRank.DEPUTY, CatRank.LEADER)


def texts() -> dict:
    return load_lang_resource("events/families.json")


def _record() -> dict:
    from scripts.feelings import _record as rec

    r = rec().setdefault("families", {})
    r.setdefault("ranks", {})
    r.setdefault("rivals", [])
    r.setdefault("checked", [])
    r.setdefault("estranged", [])
    r.setdefault("away", {})
    return r


def key(a, b) -> str:
    return "|".join(sorted((a.ID, b.ID)))


def _stat(a, b, stat) -> int:
    from scripts.feelings import _stat as s

    return s(a, b, stat)


def _alive_in_clan(cat) -> bool:
    from scripts.feelings import _alive_in_clan as alive

    return alive(cat)


def _grown(cat) -> bool:
    """grown up: past the apprentice years"""
    return not cat.status.rank.is_baby() and not cat.status.rank.is_any_apprentice_rank()


def littermates(cat) -> list:
    return [s for s in (Cat.fetch_cat(i) for i in cat.get_siblings())
            if s and abs(s.moons - cat.moons) <= 1]


def relation_to(cat, other):
    """"parent", "kit" or "littermate" (what other is to cat), or None"""
    if other.ID in cat.get_parents():
        return "parent"
    if other.ID in cat.get_children():
        return "kit"
    if other in littermates(cat):
        return "littermate"
    return None


def family(cat) -> list:
    """parents, kits and littermates"""
    ids = list(cat.get_parents()) + list(cat.get_children())
    out = [c for c in (Cat.fetch_cat(i) for i in ids) if c]
    return out + [s for s in littermates(cat) if s not in out]


def closeness(a, b) -> str:
    if key(a, b) in _record()["estranged"]:
        return ESTRANGED
    like_ab, like_ba = _stat(a, b, "like"), _stat(b, a, "like")
    if like_ab < DISTANT_UNDER or like_ba < DISTANT_UNDER:
        return DISTANT
    if min(like_ab, like_ba) >= CLOSE_AT and min(_stat(a, b, "comfort"), _stat(b, a, "comfort")) >= CLOSE_AT:
        return CLOSE
    return ORDINARY


def is_estranged(a, b) -> bool:
    return bool(a and b and a is not b and game.clan) and key(a, b) in _record()["estranged"]


def is_rival(a, b) -> bool:
    return bool(a and b and a is not b and game.clan) and key(a, b) in _record()["rivals"]


class _Events:
    """at most 2 family lines a moon about other cats; the player's cat's always show"""

    def __init__(self):
        self.count = 0

    def post(self, text_key, a, b, force=False):
        from scripts import feelings

        you = game.clan.your_cat
        mine = you in (a, b)
        if not mine and not force and self.count >= EVENTS_MAX:
            return None
        t = texts()[text_key]
        out = feelings._post_text(choice(t) if isinstance(t, list) else t, a, b, force=mine or force)
        if out and not mine:
            self.count += 1
        return out


# what parents do

def protect(attacker, kit):
    """a cat who insults or fights a kit loses some of the parent's liking too"""
    from scripts.feelings import _nudge

    for parent in (Cat.fetch_cat(i) for i in kit.get_parents()):
        if parent and parent is not attacker and _alive_in_clan(parent) and closeness(parent, kit) == CLOSE:
            _nudge(parent, attacker, like=-PROTECT)


def worried_about(cat):
    """the hurt or sick kit a parent is worried about, if any"""
    from scripts.feelings import data

    kit = Cat.fetch_cat(data(cat).get("worried"))
    if kit and _alive_in_clan(kit) and _hurt(kit):
        return kit
    return None


def _hurt(cat) -> bool:
    """hurt or sick badly enough to worry about (not fleas, not grief)"""
    return any(c.name != "grief_stricken" and c.severity != "minor" for c in cat.temporary_conditions)


def _proud_and_worried(cats, ev):
    from scripts.feelings import _nudge, data

    ranks = _record()["ranks"]
    for kit in cats:
        rank = str(kit.status.rank)
        was = ranks.get(kit.ID)
        ranks[kit.ID] = rank
        parents = [p for p in (Cat.fetch_cat(i) for i in kit.get_parents()) if _alive_in_clan(p)]
        if was and was != rank and kit.status.rank in PROUD_RANKS:
            for parent in parents:
                if closeness(parent, kit) == CLOSE:
                    _nudge(parent, kit, like=PROUD, respect=PROUD)
                    if random() < PROUD_LINE:
                        ev.post("proud", parent, kit)
        for parent in parents:
            d = data(parent)
            if not _hurt(kit):
                if d.get("worried") == kit.ID:
                    d.pop("worried")
                continue
            if d.get("worried") or closeness(parent, kit) != CLOSE or random() >= WORRY_CHANCE:
                continue
            d["worried"] = kit.ID
            ev.post("worried", parent, kit)
    for cat_id in [i for i in ranks if not _alive_in_clan(Cat.fetch_cat(i))]:
        del ranks[cat_id]


# littermates

def _littermates(cats, ev):
    from scripts.feelings import _nudge, _traits

    rec = _record()
    seen = set()
    for cat in cats:
        if not cat.status.rank.is_any_apprentice_rank():
            continue
        for sib in littermates(cat):
            k = key(cat, sib)
            if k in seen or not _alive_in_clan(sib) or not sib.status.rank.is_any_apprentice_rank():
                continue
            seen.add(k)
            if k not in rec["checked"]:
                rec["checked"].append(k)
                if (_traits(cat) | _traits(sib)) & set(RIVAL_TRAITS) and random() < RIVAL_CHANCE:
                    rec["rivals"].append(k)
            if k in rec["rivals"]:
                _nudge(cat, sib, like=-RIVAL_LIKE)
                _nudge(sib, cat, like=-RIVAL_LIKE)
                if random() < RIVAL_LINE:
                    ev.post("rivals", cat, sib)
            else:
                _nudge(cat, sib, like=LITTERMATE_LIKE)
                _nudge(sib, cat, like=LITTERMATE_LIKE)
    # rivals stay rivals in the record, but the monthly pull stops once they've grown up
    alive = {c.ID for c in cats}
    rec["checked"] = [k for k in rec["checked"] if set(k.split("|")) <= alive]
    rec["rivals"] = [k for k in rec["rivals"] if set(k.split("|")) <= alive]


# grown kits and parents

def _growing_up(cats, ev):
    from scripts.feelings import _nudge

    rec = _record()
    for kit in cats:
        if not _grown(kit):
            continue
        for parent in (Cat.fetch_cat(i) for i in kit.get_parents()):
            if not _alive_in_clan(parent):
                continue
            k = key(parent, kit)
            if k in rec["estranged"]:
                if random() < ESTRANGED_LINE:
                    ev.post("estranged", parent, kit)
                continue
            if _stat(parent, kit, "like") < ESTRANGED_UNDER and _stat(kit, parent, "like") < ESTRANGED_UNDER:
                rec["estranged"].append(k)
                ev.post("estranged", parent, kit)
                continue
            if closeness(parent, kit) == DISTANT:
                # drift, until it settles just above neutral (the game won't let it go back to neutral)
                for a, b in ((parent, kit), (kit, parent)):
                    if _stat(a, b, "like") > _settled():
                        _nudge(a, b, like=-DRIFT)
    alive = {c.ID for c in cats}
    rec["estranged"] = [k for k in rec["estranged"] if set(k.split("|")) <= alive]


def _settled() -> int:
    """the lowest "likes" value, just above the neutral band"""
    from scripts.config import get_config

    return get_config("relationship.value_intervals.neutral") + 1


def make_up_target(cat):
    """an estranged parent or grown kit, if still around"""
    for k in _record()["estranged"]:
        ids = k.split("|")
        if cat.ID in ids:
            other = Cat.fetch_cat(ids[0] if ids[1] == cat.ID else ids[1])
            if _alive_in_clan(other):
                return other
    return None


def _make_ups(cats, ev):
    from scripts.feelings import _nudge, want_of

    rec = _record()
    for cat in cats:
        want = want_of(cat)
        if not want or want["kind"] != "makeup":
            continue
        other = Cat.fetch_cat(want.get("cat"))
        if not is_estranged(cat, other) or random() >= MAKE_UP_CHANCE:
            continue
        rec["estranged"].remove(key(cat, other))
        for a, b in ((cat, other), (other, cat)):
            if _stat(a, b, "like") < _settled():
                _nudge(a, b, like=_settled() - _stat(a, b, "like"))
        ev.post("make_up", cat, other)


# family in other Clans (multi clan mode)

def _away_family(cat) -> list:
    from scripts import outsiders

    return [f for f in family(cat) if not f.dead and outsiders.clan_of(f) is not None]


def _other_clans(cats, ev):
    from scripts import outsiders
    from scripts.feelings import data

    if not outsiders.on():
        return
    rec = _record()
    away_before = rec["away"]
    away_now = {}
    you = game.clan.your_cat
    for cat in cats:
        if cat.status.rank.is_baby():
            continue
        d = data(cat)
        # word comes from the Gathering that a family member over there died
        for fam_id in away_before.get(cat.ID, []):
            fam = Cat.fetch_cat(fam_id)
            if fam and fam.dead and closeness(cat, fam) not in (DISTANT, ESTRANGED):
                d["family_lost"] = [fam.ID, game.clan.age]
                ev.post("died_away", cat, fam, force=cat is you)
        away = _away_family(cat)
        away_now[cat.ID] = [f.ID for f in away]
        close = [f for f in away if closeness(cat, f) == CLOSE]
        if not close or not cat.can_work() or random() >= GATHERING:
            continue
        # at the Gathering with them
        d["happy"] = game.clan.age
        want = d.get("want")
        if want and want["kind"] == SEE and want.get("cat") in [f.ID for f in close]:
            want["done"] = True
    rec["away"] = away_now


def see_target(cat):
    """close family in another Clan the cat could want to see again"""
    from scripts import outsiders

    if not outsiders.on() or cat.status.rank.is_baby():
        return None
    close = [f for f in _away_family(cat) if closeness(cat, f) == CLOSE]
    return choice(close) if close else None


def see_gone(want) -> bool:
    from scripts import outsiders

    target = Cat.fetch_cat(want.get("cat"))
    return not target or target.dead or outsiders.clan_of(target) is None


def grieving_for(cat):
    from scripts.feelings import data

    lost = data(cat).get("family_lost")
    if lost and game.clan.age - lost[1] <= FAMILY_GRIEF:
        dead = Cat.fetch_cat(lost[0])
        if dead and dead.dead:
            return dead
    return None


# grandparents

def _stories(cats, ev):
    for elder in cats:
        if elder.status.rank != CatRank.ELDER:
            continue
        grandkits = []
        for kid in (Cat.fetch_cat(i) for i in elder.get_children()):
            if kid:
                grandkits += [g for g in (Cat.fetch_cat(i) for i in kid.get_children())
                              if _alive_in_clan(g) and (g.status.rank.is_baby() or
                                                        g.status.rank.is_any_apprentice_rank())]
        close = [g for g in grandkits if _stat(elder, g, "like") >= CLOSE_AT and _stat(g, elder, "like") >= CLOSE_AT]
        if close and random() < STORY_CHANCE:
            ev.post("story", elder, choice(close))


def on_moon():
    from scripts.feelings import _clanmates

    cats = _clanmates()
    ev = _Events()
    _proud_and_worried(cats, ev)
    _littermates(cats, ev)
    _growing_up(cats, ev)
    _make_ups(cats, ev)
    _other_clans(cats, ev)
    _stories(cats, ev)


def respect_target(cat):
    """an apprentice whose parent is a warrior they look up to wants that parent's respect"""
    from scripts.feelings import RESPECT_DONE

    if not cat.status.rank.is_any_apprentice_rank():
        return None
    parents = [p for p in (Cat.fetch_cat(i) for i in cat.get_parents())
               if _alive_in_clan(p) and p.status.rank in (CatRank.WARRIOR, CatRank.DEPUTY, CatRank.LEADER)
               and _stat(cat, p, "respect") >= RESPECT_LOOK_UP and _stat(p, cat, "respect") < RESPECT_DONE]
    return choice(parents) if parents else None


def profile_lines(cat) -> str:
    """the player's cat's family: close, distant and estranged"""
    if cat is not game.clan.your_cat:
        return ""
    t = texts()["profile"]
    groups = {CLOSE: [], DISTANT: [], ESTRANGED: []}
    for fam in family(cat):
        if not _alive_in_clan(fam) and not (fam and not fam.dead and _away(fam)):
            continue
        c = closeness(cat, fam)
        if c in groups:
            groups[c].append(str(fam.name))
    out = ""
    for c, names in groups.items():
        if names:
            more = t["more"] if len(names) > 4 else ""
            out += t[c].replace("%{cats}", ", ".join(names[:4]) + more) + "\n"
    return out


def _away(cat) -> bool:
    from scripts import outsiders

    return outsiders.on() and outsiders.clan_of(cat) is not None


def talk_fits(t_c, you, block) -> bool:
    """talk filters: t_c_family (what t_c is to the player's cat), t_c_family_feel (how close)"""
    if "t_c_family" in block and relation_to(you, t_c) not in block["t_c_family"]:
        return False
    if "t_c_family_feel" in block and (relation_to(you, t_c) is None
                                       or closeness(you, t_c) not in block["t_c_family_feel"]):
        return False
    return True

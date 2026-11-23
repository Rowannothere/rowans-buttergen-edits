"""BUTTERGEN: the exploring patrol (Other Clans step 1). The player's cat and up to 2 willing
Clanmates go onto another Clan's land, or outside the Clans. Multi clan mode only.
Texts: events/explore_patrols.json. Rules: Notes\\Buttergen exploring patrol (for review).txt"""

import copy
from random import choice, choices, randint, random

from scripts.cat.enums import CatSocial
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource

CATEGORY = "explore"
OUTSIDE = "outside"
# patrolled marker for the moon (Clangen 1, Lifegen 2, Dark Forest 3, date 4)
PATROLLED = "5"
MAX_COMPANIONS = 2
# who comes along: like and lawfulness (0 to 16)
WILLING_LIKE, WILLING_LAW = 15, 10
CLOSE_LIKE, CLOSE_LAW = 40, 14
CLAN_SPLIT = {"caught": 50, "lone": 20, "land": 30}
OUTSIDE_SPLIT = {"kittypet": 40, "loner": 30, "rogue": 20, "nothing": 10}
INJURY_CHANCE = 1 / 3
SMALL_INJURIES = ("scrapes", "bruises")
CAUGHT_RELATIONS, CAUGHT_RELATIONS_HOSTILE = -1, -2
# like, both ways, for each kind of meeting
LIKE = {"lone_friendly": 5, "lone_cold": -3, "kittypet_curious": 3, "kittypet_scared": 0,
        "loner_friendly": 5, "loner_wary": 1, "rogue_swipe": -3, "rogue_sneer": -2}
KNOWN_OUTSIDER_CHANCE = 0.5
SOCIALS = {"kittypet": CatSocial.KITTYPET, "loner": CatSocial.LONER, "rogue": CatSocial.ROGUE}

# set by the patrol screen: a Clan's group_ID, or OUTSIDE
where = {"to": OUTSIDE}
# set by the patrol screen when the caught talk opens, so the talk screen goes back there
talk_return = {"screen": None}


def texts() -> dict:
    return load_lang_resource("events/explore_patrols.json")


def _you():
    return game.clan.your_cat if game.clan else None


def on() -> bool:
    from scripts import outsiders

    return outsiders.on()


def can_go() -> bool:
    """the player's cat can go exploring at all (not a kit, shunned, hurt or serving duties)"""
    from scripts.honor import judgment

    you = _you()
    if not on() or you is None or you.dead or not you.status.alive_in_player_clan:
        return False
    if you.status.is_shunned() or you.status.rank.is_baby() or not you.can_work():
        return False
    sentence = judgment.sentence(you)
    return not (sentence and sentence["type"] == judgment.DUTIES)


def other_clans() -> list:
    return list(game.clan.all_other_clans) if on() else []


def target_clan():
    return next((c for c in other_clans() if c.group_ID == where["to"]), None)


def unwilling(cat) -> str:
    """why a Clanmate won't come along, or "" if they will"""
    you = _you()
    rel = cat.relationships.get(you.ID) if you else None
    like = rel.like if rel else 0
    law = cat.personality.lawfulness
    if like >= CLOSE_LIKE:
        return "" if law < CLOSE_LAW else texts()["unwilling"]["law"]
    if like < WILLING_LIKE:
        return texts()["unwilling"]["like"]
    return "" if law < WILLING_LAW else texts()["unwilling"]["law"]


def is_exploring(patrol) -> bool:
    return getattr(patrol, "explore", None) is not None


def pick_event(patrol_list):
    """the patrol picked for where the player chose"""
    want = "explore_outside" if where["to"] == OUTSIDE or target_clan() is None else "explore_clan"
    return next(p for p in patrol_list if p.event_id == want)


def setup(patrol):
    """the patrol starts: the other Clan is the one whose land they cross into"""
    clan = target_clan() if where["to"] != OUTSIDE else None
    patrol.explore = {"clan": clan, "result": None, "cat": None, "talk": None}
    if clan is not None:
        patrol.other_clan = clan


def intro(patrol):
    if not is_exploring(patrol):
        return None
    place = "clan" if patrol.explore["clan"] else "outside"
    alone = "alone" if len(patrol.patrol_cats) == 1 else "group"
    return choice(texts()["intro"][f"{place}_{alone}"])


def decline(patrol):
    if not is_exploring(patrol):
        return None
    return choice(texts()["decline"])


def _roll(split: dict) -> str:
    return choices(list(split), weights=list(split.values()))[0]


def _clan_cat(clan, lone: bool):
    """a real, grown cat of that Clan"""
    from scripts.cat.cats import Cat
    from scripts.cat.enums import CatRank

    pool = [c for c in Cat.all_cats_list if not c.dead and c.status.group_ID == clan.group_ID
            and not c.status.rank.is_baby() and c.status.rank != CatRank.ELDER]
    if lone:
        pool = [c for c in pool if c.status.rank != CatRank.LEADER] or pool
    return choice(pool) if pool else None


def _outside_cat(kind: str):
    """a kittypet, loner or rogue the Clan already knows of half the time, otherwise a new one"""
    from scripts.cat.cats import Cat
    from scripts.events_module.consequences import create_new_cat

    social = SOCIALS[kind]
    known = [c for c in Cat.all_cats_list if not c.dead and c.status.social == social
             and c.status.is_outsider and c.moons >= 12]
    if known and random() < KNOWN_OUTSIDER_CHANCE:
        return choice(known)
    cat = create_new_cat(Cat, moons=randint(12, 100), outside=True, original_social=social)[0]
    cat.history.beginning = None
    game.clan.add_cat(cat)
    return cat


def outcome(patrol, chosen_outcome, outcome_cats):
    """what happens out there: the outcome with the right text, and the cat they meet as e_c"""
    from scripts import outsiders

    if not is_exploring(patrol):
        return chosen_outcome
    t = texts()
    clan = patrol.explore["clan"]
    cat = None
    if clan is not None:
        result = _roll(CLAN_SPLIT)
        if result in ("caught", "lone"):
            cat = _clan_cat(clan, lone=result == "lone")
            if cat is None:
                result = "land"
        if result == "lone":
            result = "lone_cold" if outsiders.mood(cat) == "hostile" else "lone_friendly"
    else:
        result = _roll(OUTSIDE_SPLIT)
        if result != "nothing":
            cat = _outside_cat(result)
            result = result + choice({"kittypet": ("_curious", "_scared"), "loner": ("_friendly", "_wary"),
                                      "rogue": ("_swipe", "_sneer")}[result])
        elif random() < 1 / 3:
            result = "nothing_prey"
    patrol.explore["result"] = result
    patrol.explore["cat"] = cat
    if cat is not None:
        outcome_cats["e_c"] = cat
        patrol.involved_cats["e_c"] = cat
    changed = copy.copy(chosen_outcome)
    changed.strings = [choice(t[result])]
    if result.startswith("rogue"):
        changed.outcome_art = "gen_bord_rogues"
    return changed


def _injure(cat):
    from scripts.cat.conditions.gain_conditions import gain_temporary_condition

    have = {c.name for c in cat.temporary_conditions}
    options = [i for i in SMALL_INJURIES if i not in have]
    if options:
        gain_temporary_condition(cat, choice(options))


def after_outcome(patrol) -> list:
    """the effects, and the lines for the patrol results"""
    from scripts import outsiders
    from scripts.clan_package.cotc import change_clan_relations
    from scripts.events_module.text_adjust import event_text_adjust
    from scripts.cat.cats import Cat
    from scripts.honor import patrols as honor_patrols
    from scripts.honor.temptation import nudge

    if not is_exploring(patrol):
        return []
    # wanting to see the world
    from scripts import feelings

    feelings.explored(patrol.patrol_cats)
    t = texts()
    you = _you()
    clan = patrol.explore["clan"]
    result = patrol.explore["result"]
    cat = patrol.explore["cat"]
    lines = []

    def render(text):
        return event_text_adjust(Cat, text, main_cat=cat or you, clan=game.clan, other_clan=clan)

    if cat is not None:
        outsiders.meet(cat, "exploring")
        if result in LIKE and LIKE[result]:
            for c in patrol.patrol_cats:
                nudge(c, cat, like=LIKE[result])
                nudge(cat, c, like=LIKE[result])
    if result == "caught":
        patrol.explore["talk"] = cat
        hostile = outsiders.mood(cat) == "hostile"
        if hostile and random() < INJURY_CHANCE:
            _injure(choice(patrol.patrol_cats))
            lines.append(render(t["caught_fight"]))
        else:
            lines.append(render(t["caught_after"]))
        change_clan_relations(game.clan, clan, CAUGHT_RELATIONS_HOSTILE if hostile else CAUGHT_RELATIONS)
        game.clan.explore_news = getattr(game.clan, "explore_news", None) or []
        game.clan.explore_news.append(clan.name)
    elif result == "rogue_swipe" and random() < INJURY_CHANCE:
        _injure(you)
    # crossing into another Clan's land is a minor misdeed: the companions saw it and crossed too
    if clan is not None:
        cats = {"p_l": you}
        spec = honor_patrols.brk("p_l", "cross_border", caught=result == "caught", followers=True)
        lines += honor_patrols._run_break(spec, patrol, cats, "", clan)
    return lines


def on_skip():
    """the other Clan's complaint, in the other Clans tab"""
    from scripts.cat.cats import Cat
    from scripts.events_module.event_information import EventInformation
    from scripts.events_module.text_adjust import event_text_adjust

    news = getattr(game.clan, "explore_news", None) or []
    game.clan.explore_news = []
    for name in dict.fromkeys(news):
        clan = next((c for c in game.clan.all_other_clans if c.name == name), None)
        if clan is None:
            continue
        text = event_text_adjust(Cat, texts()["complaint"], clan=game.clan, other_clan=clan)
        game.cur_events_list.append(EventInformation(text, ["other_clans"], []))

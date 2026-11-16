"""BUTTERGEN: Other Clans step 2, romance across borders. Cats in the player's Clan and cats from other
Clans who love each other can become mates in secret, which breaks "Keep your heart in your own Clan".
Multi clan mode only. Texts: events/honor_heart.json."""

from random import choice, choices as weighted_choice, randint, random, uniform

from scripts.cat.cats import Cat
from scripts.events_module import weekskip
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.honor import code, core
from scripts.honor.acts import HONOR_LOSS, LONGING

ACT = "heart_mate"
ASK, OUT = "heart_ask", "heart_out"
KINDS = (ASK, OUT)
MATES, FRIENDS, TURN = "mates", "friends", "turn"
END, KEEP, JOIN = "end", "keep", "join"

ROMANCE_AT = 40
ASK_EVERY = 12
FRIENDS_ROMANCE = 15
TURN_ROMANCE, TURN_LIKE = 20, 10
APART_AT = 15
LONGING_GAIN = 4
# chance a moon that a secret pair meets (and could be seen)
MEET_CHANCE = 0.5
MEET_ROMANCE = (1, 3)
# after it comes out, the other Clan's cat may ask to join the player's Clan
THEY_ASK = 0.25
ASK_BONUS_CAP = 20
RUMOR_CHANCE = 0.08
# other cats' choices when nobody asks the player
OTHERS_SHOWN = 1 / 3


def texts() -> dict:
    return load_lang_resource("events/honor_heart.json")


def on() -> bool:
    from scripts import outsiders

    return outsiders.on()


def _you():
    return game.clan.your_cat if game.clan else None


def _alive_in_clan(cat) -> bool:
    return bool(cat) and not cat.dead and cat.status.alive_in_player_clan


def _clan_of(cat):
    from scripts import outsiders

    return outsiders.clan_of(cat) if cat and not cat.dead else None


def _rel(cat_from, cat_to):
    return cat_from.relationships.get(cat_to.ID) if cat_from and cat_to else None


def _stat(cat_from, cat_to, stat) -> int:
    rel = _rel(cat_from, cat_to)
    return getattr(rel, stat) if rel else 0


def _change(cat_from, cat_to, **stats):
    rel = _rel(cat_from, cat_to)
    if rel is None:
        return
    for stat, amount in stats.items():
        setattr(rel, stat, max(-100, min(100, getattr(rel, stat) + amount)))


def record() -> dict:
    rec = getattr(game.clan, "code_heart", None)
    if not isinstance(rec, dict):
        rec = game.clan.code_heart = {}
    rec.setdefault("pairs", [])
    rec.setdefault("asked", {})
    return rec


def _key(home, away) -> str:
    return f"{home.ID}|{away.ID}"


def _render(text, home, away, other_clan=None):
    return event_text_adjust(Cat, text, main_cat=home, random_cat=away, clan=game.clan,
                             other_clan=other_clan or _clan_of(away))


def _post(key, home, away, top=None, other_clan=None):
    text = _render(texts()[key], home, away, other_clan)
    event = EventInformation(text, ["relation"], [c.ID for c in (home, away) if c])
    you = _you()
    if top or (top is None and you in (home, away)):
        game.cur_events_list.insert(0, event)
    else:
        game.cur_events_list.append(event)
    return text


# the pairs

def pair_of(cat_a, cat_b):
    """the pair two cats make (either order), or None"""
    if not game.clan or not cat_a or not cat_b:
        return None
    for pair in record()["pairs"]:
        if {pair["home"], pair["away"]} == {cat_a.ID, cat_b.ID}:
            return pair
    return None


def _cats(pair):
    return Cat.fetch_cat(pair["home"]), Cat.fetch_cat(pair["away"])


def is_secret(pair) -> bool:
    return bool(pair) and not pair.get("open") and not pair.get("out")


def keeps_together(cat_a, cat_b) -> bool:
    """Clangen splits mates who live in different Clans. Pairs here stay together"""
    return pair_of(cat_a, cat_b) is not None


def no_kits(cat_a, cat_b) -> bool:
    """kits for these pairs come with step 3"""
    return pair_of(cat_a, cat_b) is not None


def mate_note(cat, mate) -> str:
    """the profile's "(ClanName, secret)" after a mate in another Clan, or "" """
    pair = pair_of(cat, mate)
    if not pair:
        return ""
    other_clan = _clan_of(mate) or _clan_of(cat)
    name = f"{other_clan.name}Clan" if other_clan else ""
    return texts()["mate_secret" if is_secret(pair) else "mate_known"].replace("%{clan}", name)


def _has_clan_mate(cat) -> bool:
    return any(_alive_in_clan(Cat.fetch_cat(m)) for m in cat.mate)


def _start(home, away, decided_by_you=False):
    """they become mates. Secret if the Clan follows rule 5"""
    rec = record()
    other_clan = _clan_of(away)
    open_ = not code.counts(ACT)
    affair = _has_clan_mate(home)
    rec["pairs"].append({"home": home.ID, "away": away.ID, "since": game.clan.age, "open": open_,
                         "out": False, "met_moon": None})
    home.set_mate(away)
    if not open_:
        core.change_honor(home, -randint(*HONOR_LOSS["serious"]))
    if home is _you() or away is _you():
        _post("mates_open" if open_ else "mates", home, away, top=True)
    if affair and not open_:
        _affair_roll(home, away, other_clan)


def _affair_roll(home, away, other_clan):
    """like Lifegen's affairs: it can be found out right away by a mate in the Clan"""
    from scripts.game_structure import constants

    gen = constants.CONFIG["lifegen"]["gen"]
    caught = uniform(gen["affair_caught_chance_min"], gen["affair_caught_chance_max"])
    mates = [m for m in (Cat.fetch_cat(i) for i in home.mate) if _alive_in_clan(m) and m is not away]
    for mate in mates:
        rel = _rel(mate, home)
        if rel and (rel.trust > 50 or rel.comfort > 50):
            caught += 5
        elif rel and rel.trust < 10 and rel.comfort < 10:
            caught -= 5
    if random() * 100 >= caught or not mates:
        return
    from scripts.cat.conditions.gain_conditions import gain_temporary_condition
    from scripts.honor import witness

    low, high = gen["affair_relationship_change_lb"], gen["affair_relationship_change_ub"]
    leaves = random() < 0.5
    for mate in mates:
        _change(mate, home, like=-randint(low, high), comfort=-randint(low, high),
                trust=-randint(low, high), romance=-randint(low, high))
        if leaves:
            gain_temporary_condition(mate, "heartbroken")
            mate.unset_mate(home)
        _post("affair_leave" if leaves else "affair_stay", home, mate, top=True, other_clan=other_clan)
    witness.report(home, mates[0], ACT, other_clan, "report")


def _end(pair, key="end"):
    home, away = _cats(pair)
    if pair in record()["pairs"]:
        record()["pairs"].remove(pair)
    if home and away:
        if away.ID in home.mate:
            home.unset_mate(away)
        if key and (_you() in (home, away) or random() < OTHERS_SHOWN):
            _post(key, home, away)


# asking

def can_pair(home, away) -> bool:
    if not _alive_in_clan(home) or _clan_of(away) is None or home.status.rank.is_baby():
        return False
    if away.ID in home.mate or pair_of(home, away):
        return False
    if home.status.is_shunned() or home.status.is_exiled():
        return False
    from scripts.honor.judgment import sentence

    if sentence(home) is not None:
        return False
    try:
        return home.is_potential_mate(away)
    except Exception:  # pylint: disable=broad-except
        return False


def _asked_recently(home, away) -> bool:
    moon = record()["asked"].get(_key(home, away))
    return moon is not None and game.clan.age - moon < ASK_EVERY


def _in_love(home, away) -> bool:
    return _stat(home, away, "romance") >= ROMANCE_AT and _stat(away, home, "romance") >= ROMANCE_AT


def candidates(home) -> list:
    """the other Clans' cats who love this cat back and could be asked about now"""
    from scripts import outsiders

    found = []
    for other_id in list(home.relationships.keys()):
        away = Cat.fetch_cat(other_id)
        if away is None or _clan_of(away) is None:
            continue
        if home is _you() and not outsiders.has_met(away):
            continue
        if _in_love(home, away) and can_pair(home, away) and not _asked_recently(home, away):
            found.append(away)
    return found


def decide_ask(home, away) -> str:
    law = home.personality.lawfulness / 16
    romance = min(1.0, _stat(home, away, "romance") / 80)
    honor = max(0, home.honor) / 100
    taken = 0.25 if _has_clan_mate(home) else 0
    if not code.counts(ACT):
        law = honor = 0
    weights = (0.15 + romance * 0.7 * (1 - law), 0.2 + law * 0.5 + honor * 0.3 + taken, 0.05 + taken * 0.4)
    return weighted_choice((MATES, FRIENDS, TURN), weights)[0]


def answer_ask(home, away, option):
    record()["asked"][_key(home, away)] = game.clan.age
    if option == MATES:
        _start(home, away)
    elif option == FRIENDS:
        _change(home, away, romance=-FRIENDS_ROMANCE)
        if home is _you():
            _post("friends", home, away)
    else:
        _change(away, home, romance=-TURN_ROMANCE, like=-TURN_LIKE)
        if home is _you():
            _post("turned", home, away)


def _asks():
    """new pairs: the player's cat gets a choice, other cats decide on their own"""
    from scripts.honor import choices

    you = _you()
    if _alive_in_clan(you):
        found = candidates(you)
        if found and choices.can_offer():
            away = max(found, key=lambda c: _stat(you, c, "romance"))
            choices._offer({"kind": ASK, "cat": away.ID})
    for cat_id in list(game.clan.clan_cats):
        home = Cat.fetch_cat(cat_id)
        if home is None or home is you or not _alive_in_clan(home):
            continue
        for away in candidates(home):
            answer_ask(home, away, decide_ask(home, away))
            break


# after it comes out

def decide_out(home, away) -> str:
    law = home.personality.lawfulness / 16
    romance = min(1.0, _stat(home, away, "romance") / 80)
    options = [END, KEEP] + ([JOIN] if _can_join(home, away) else [])
    weights = [0.2 + law * 0.6, 0.15 + romance * (1 - law) * 0.6, 0.1 + romance * 0.4][:len(options)]
    return weighted_choice(options, weights)[0]


def _can_join(home, away) -> bool:
    from scripts.honor import switching

    target = away.status.group_ID
    return (switching.eligible(home) and not switching.busy(home) and target in switching.targets(home)
            and not switching.wait_for(home, target))


def _ask_bonus(home, away) -> int:
    return max(0, min(ASK_BONUS_CAP, _stat(away, home, "like") // 4))


def answer_out(pair, option):
    home, away = _cats(pair)
    if not home or not away:
        return
    if option == END:
        _end(pair)
    elif option == JOIN and _can_join(home, away):
        from scripts.honor import switching

        switching.record()["asks"].append({"cat": home.ID, "to": away.status.group_ID,
                                           "bonus": _ask_bonus(home, away), "follow": None})
        if home is _you() or random() < OTHERS_SHOWN:
            _post("join", home, away)
    else:
        # back to a secret: seen again, judged again
        pair["out"] = False
        if home is _you() or random() < OTHERS_SHOWN:
            _post("keep", home, away)


def _they_ask(pair):
    """the other Clan's cat may ask to join the player's Clan"""
    from scripts.honor import switching

    home, away = _cats(pair)
    target = switching.home_group()
    if (random() >= THEY_ASK or not switching.eligible(away) or switching.busy(away)
            or target not in switching.targets(away) or switching.wait_for(away, target)):
        return
    switching.record()["asks"].append({"cat": away.ID, "to": target,
                                       "bonus": _ask_bonus(away, home), "follow": None})
    _post("join_in", home, away)


def came_out(cat):
    """called when a heart_mate misdeed comes out (witness.report). Both Clans hear, the other cat is
    punished in their own Clan, and the pair decides what happens next"""
    from scripts.honor import choices

    for pair in list(record()["pairs"]):
        if pair["home"] != cat.ID or pair.get("out") or pair.get("open"):
            continue
        home, away = _cats(pair)
        if not away or away.dead:
            continue
        pair["out"] = True
        other_clan = _clan_of(away)
        if other_clan is not None:
            game.clan.set_relations(game.clan, other_clan, None, -1)
        _post("news", home, away, top=True, other_clan=other_clan)
        from scripts.honor.leader import is_leader

        if not is_leader(away):
            # nobody judges a leader
            _post("judged_there", home, away, top=True, other_clan=other_clan)
            core.change_reputation(away, -randint(3, 6))
        if home is _you():
            # the player chooses, this moon or the next one if a choice is already waiting
            pair["your_choice"] = True
            _offer_out(pair)
        else:
            answer_out(pair, decide_out(home, away))
        if pair in record()["pairs"]:
            _they_ask(pair)


def _offer_out(pair):
    from scripts.honor import choices

    if pair.get("your_choice") and choices.can_offer():
        pair.pop("your_choice", None)
        choices._offer({"kind": OUT, "cat": pair["away"]})


# meeting

def can_meet(you, away) -> bool:
    pair = pair_of(you, away)
    return (bool(pair) and pair["home"] == you.ID and _alive_in_clan(you) and not away.dead
            and pair.get("met_moon") != game.clan.age and not you.status.is_shunned())


def meet(pair, by_you=False):
    """a meeting: closer together, and if it's a secret, someone may see"""
    from scripts.honor import witness

    home, away = _cats(pair)
    pair["met_moon"] = game.clan.age
    _change(home, away, romance=randint(*MEET_ROMANCE))
    _change(away, home, romance=randint(*MEET_ROMANCE))
    if by_you:
        _post("meet", home, away, top=True)
    if is_secret(pair):
        witness.after_break(home, ACT, _clan_of(away))


# every skip

def _tidy():
    you = _you()
    for pair in list(record()["pairs"]):
        home, away = _cats(pair)
        if home is None or away is None or home.dead:
            record()["pairs"].remove(pair)
            continue
        if away.dead:
            record()["pairs"].remove(pair)
            if home is you and _alive_in_clan(home):
                _post("grief", home, away, top=True)
            continue
        # moved Clans, or no longer mates: not a cross-Clan pair anymore
        if (not _alive_in_clan(home) or _clan_of(away) is None or away.ID not in home.mate):
            record()["pairs"].remove(pair)
            continue
        if _stat(home, away, "romance") < APART_AT or _stat(away, home, "romance") < APART_AT:
            _end(pair, "apart")


def on_skip(full_moon: bool):
    if not on():
        return
    scale = 1 / weekskip.WEEKS_IN_MOON if weekskip.on() else 1.0
    _tidy()
    # the player's waiting choice first, before anything else can take this moon's choice
    for pair in list(record()["pairs"]):
        _offer_out(pair)
    for pair in list(record()["pairs"]):
        home, _away = _cats(pair)
        if is_secret(pair):
            home.temptation[LONGING] = min(100, home.temptation.get(LONGING, 0) + LONGING_GAIN * scale)
        if pair.get("met_moon") != game.clan.age and random() < MEET_CHANCE * scale:
            meet(pair)
    if full_moon:
        _asks()


def rumor_at_gathering():
    """two cats from two other Clans aren't tracked, but now and then the Gathering talks"""
    if not on() or len(game.clan.all_other_clans) < 2 or random() >= RUMOR_CHANCE:
        return None
    other_clan = choice(game.clan.all_other_clans)
    text = event_text_adjust(Cat, texts()["rumor"], clan=game.clan, other_clan=other_clan)
    game.cur_events_list.append(EventInformation(text, ["relation"], []))
    return text


def register_litter_mates(cat, outside_parent):
    """Lifegen's half-Clan litters can make the parents mates: with rule 5 followed, that's a secret"""
    if not on() or not _alive_in_clan(cat) or _clan_of(outside_parent) is None or pair_of(cat, outside_parent):
        return
    record()["pairs"].append({"home": cat.ID, "away": outside_parent.ID, "since": game.clan.age,
                              "open": not code.counts(ACT), "out": False, "met_moon": None})


# the player's choices (scripts/honor/choices.py hands these over)

def pending_gone(c) -> bool:
    away = Cat.fetch_cat(c.get("cat"))
    you = _you()
    if away is None or away.dead or not _alive_in_clan(you):
        return True
    if c["kind"] == ASK:
        return not can_pair(you, away)
    return pair_of(you, away) is None


def window_text(c):
    you, away = _you(), Cat.fetch_cat(c["cat"])
    t = texts()
    oc = _clan_of(away)
    if c["kind"] == ASK:
        part = t["ask"]
        prompt = _render(part["prompt_mate" if _has_clan_mate(you) else "prompt"], you, away, oc)
        labels = part["options" if code.counts(ACT) else "options_open"]
        return prompt, [(o, _render(label, you, away, oc)) for o, label in zip((MATES, FRIENDS, TURN), labels)]
    part = t["out"]
    prompt = _render(part["prompt"], you, away, oc)
    keys = [END, KEEP] + ([JOIN] if _can_join(you, away) else [])
    return prompt, [(o, _render(label, you, away, oc)) for o, label in zip(keys, part["options"])]


def resolve_choice(c, option):
    from scripts.honor import choices

    you, away = _you(), Cat.fetch_cat(c["cat"])
    if c["kind"] == ASK:
        if option == choices.DECIDE:
            option = decide_ask(you, away)
        answer_ask(you, away, option)
        return option
    pair = pair_of(you, away)
    if pair is None:
        return None
    if option == choices.DECIDE:
        option = decide_out(you, away)
    answer_out(pair, option)
    return option

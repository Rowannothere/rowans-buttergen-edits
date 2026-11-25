"""BUTTERGEN: the Clan's own warrior code. Each rule is a clan setting (Warrior code tab); an act
against a rule the Clan doesn't follow still happens, but it isn't a misdeed."""

from scripts.clan_package.settings import get_clan_setting

# clan setting for each rule, in the order of the Warrior code tab
RULES = [
    "code defend",
    "code borders",
    "code eat first",
    "code leader's word",
    "code own clan",
    "healer mates break the code",
    "code no needless killing",
    "code border markers",
    "code gathering truce",
    "code stay in camp",
    "code clan property",
    "code honesty",
]

RULE_OF = {
    "pass_secrets": "code defend", "kill_kits": "code defend", "steal_kit": "code defend",
    "hunt_border": "code borders", "cross_border": "code borders", "herb_border": "code borders",
    "border_raid": "code borders", "claim_land": "code borders", "kit_border": "code borders",
    "eat_first": "code eat first", "app_eat_first": "code eat first", "feed_elders": "code eat first",
    "give_share": "code eat first", "eat_last": "code eat first",
    "disobey_mentor": "code leader's word", "ignore_sign": "code leader's word",
    "skip_duties": "code leader's word", "carry_messages": "code leader's word",
    "secret_meeting": "code leader's word",
    "healer_mate": "healer mates break the code", "healer_kits": "healer mates break the code",
    "healer_adopt": "healer mates break the code",
    "heart_mate": "code own clan", "heart_kits": "code own clan", "outside_kits": "code own clan",
    "let_trespasser": "code border markers", "markers_lapse": "code border markers",
    "mark_their_land": "code border markers", "renew_markers": "code border markers",
    "gathering_fight": "code gathering truce",
    "sneak_out": "code stay in camp", "kit_sneak": "code stay in camp",
    "twoleg_food": "code clan property", "favorite_herbs": "code clan property",
    "best_nest": "code clan property", "leave_den": "code clan property",
    "lie_leader": "code honesty", "hide_sign": "code honesty", "bend_sign": "code honesty",
    "hide_news": "code honesty", "twist_words": "code honesty", "spread_rumors": "code honesty",
    "unfair_patrols": "code honesty", "favorite_off": "code honesty", "spite": "code honesty",
    "neglect_kit": "code honesty", "kits_wander": "code honesty", "break_shunning": "code honesty",
}


# nothing can break these yet: grayed out on the Clan creation page
LATER = ("code no needless killing",)


def starting_rules() -> dict:
    """the ticks a new Clan starts with (display_settings.toml)"""
    from scripts.game_structure.constants import DISPLAY_SETTINGS

    return {rule: bool(DISPLAY_SETTINGS["clan"]["code"][rule]) for rule in RULES}


def follows(rule: str) -> bool:
    return bool(get_clan_setting(rule, default=True))


def counts(act_key: str) -> bool:
    """True if the Clan follows the rule this act belongs to (acts with no rule always count)"""
    rule = RULE_OF.get(act_key)
    return rule is None or follows(rule)


def followed_now() -> dict:
    return {rule: follows(rule) for rule in RULES}


# never left out of another Clan's code: no Clan would drop these
_ALWAYS_KEPT = ("code defend", "code gathering truce")


def texts() -> dict:
    from scripts.game_structure.localization import load_lang_resource

    return load_lang_resource("events/honor_code.json")


def rule_name(rule: str) -> str:
    import i18n

    return i18n.t(f"settings.{rule}")


def on_skip_start():
    """before the skip's judgments: announce rules the player turned on or off since the last
    skip, and drop waiting misdeeds against a rule the Clan no longer follows"""
    from random import choice

    from scripts.cat.cats import Cat
    from scripts.events_module.event_information import EventInformation
    from scripts.events_module.text_adjust import event_text_adjust
    from scripts.game_structure import game

    clan = game.clan
    if not clan:
        return
    now = followed_now()
    seen = clan.code_rules_seen
    clan.code_rules_seen = now
    _give_other_clans_codes()
    if seen is None:
        # an older save or a new Clan: nothing to announce yet
        return
    leader = clan.leader if clan.leader and not clan.leader.dead and clan.leader.status.alive_in_player_clan else None
    you = leader is not None and leader is clan.your_cat
    t = texts()
    for rule in RULES:
        if seen.get(rule, True) == now[rule]:
            continue
        key = ("rule_on" if now[rule] else "rule_off") + ("_you" if you else "" if leader else "_no_leader")
        text = choice(t[key]).replace("[rule]", rule_name(rule))
        text = event_text_adjust(Cat, text, main_cat=leader, clan=clan)
        clan_event = EventInformation(text, ["misc"], [leader.ID] if leader else [])
        clan_event_list = game.cur_events_list
        if you:
            clan_event_list.insert(0, clan_event)
        else:
            clan_event_list.append(clan_event)
    clan.code_judgments = [e for e in clan.code_judgments if counts(e.get("act", ""))]


def _give_other_clans_codes():
    """each other Clan follows all the rules but 0 to 2 (flavor only for now)"""
    from random import randint, sample

    from scripts.game_structure import game

    for other in game.clan.all_other_clans:
        if other.name not in game.clan.other_codes:
            pool = [r for r in RULES if r not in _ALWAYS_KEPT]
            game.clan.other_codes[other.name] = sample(pool, randint(0, 2))


def other_clan_line(other) -> str:
    """for the other Clan's allegiances: the rules it follows, then the ones it doesn't"""
    from scripts.game_structure import game

    if not game.clan:
        return ""
    off = game.clan.other_codes.get(other.name) or []
    t = texts()
    kept = [rule_name(r) for r in RULES if r not in off]
    line = t["other_clan_follows"] + "<br>" + "<br>".join(kept)
    if off:
        line += "<br><br>" + t["other_clan"].replace("[rules]", "; ".join(rule_name(r) for r in off))
    return line

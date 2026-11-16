import logging
import random

from scripts.cat.cats import Cat
from scripts.clan_package.settings import get_clan_setting, set_clan_setting
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.territory import territory_class
from scripts.war import War

logger = logging.getLogger(__name__)


def process_territory_month():
    if not game.clan.territory_tiles:
        return

    _prune_tile_events()
    _process_map_interaction()
    _advance_territory_wars()
    _start_declared_territory_wars()
    _territory_wobble()


def _prune_tile_events():
    from scripts.config import get_config

    event_lifetime = get_config("bellsofwar.save_events_for")
    for tile in game.clan.territory_tiles:
        tile.events[:] = [
            event
            for event in tile.events
            if game.clan.age - event.get("moon", game.clan.age) < event_lifetime
        ]


def _process_map_interaction():
    interaction_data = get_clan_setting("map_interaction")
    if not interaction_data:
        return
    set_clan_setting("map_interaction", {})

    if not isinstance(interaction_data, dict):
        logger.warning("Ignoring malformed map interaction: %r", interaction_data)
        return

    tile = territory_class.get_tile_from_string(interaction_data.get("tile", ""))
    if tile is None:
        logger.warning("Ignoring map interaction for missing tile: %r", interaction_data)
        return
    current_owner_id = tile.owner.group_ID if tile.owner else None
    if current_owner_id != interaction_data.get("owner_ID"):
        logger.warning("Ignoring stale map interaction for tile %s", tile.tile_string)
        return

    action = interaction_data.get("interaction")
    if action not in {"claim", "take", "forfeit", "attack"}:
        logger.warning("Ignoring unknown map interaction: %r", action)
        return

    owner = tile.owner
    war = (
        game.clan.get_current_territory_war(owner)
        if owner and owner is not game.clan
        else None
    )
    war_started = False
    if action == "forfeit":
        _forfeit_tile(tile, war)
        return

    if owner is game.clan or (owner and tile.in_dispute()):
        return

    interaction_events = load_lang_resource("events/map_interactions.json")
    success = _roll_interaction(tile, action, owner)
    if action == "attack" and owner:
        success = random.random() < (0.25 if tile.camp else 0.6)

    if action == "take" and owner and not success and not war:
        if tile.is_bordering(game.clan) and random.randrange(8) == 0:
            war = _start_territory_war(game.clan, owner, tile)
            war_started = war is not None

    message = _interaction_message(
        interaction_events, action, tile, owner, success, war, war_started
    )
    if owner and action in {"take", "attack"}:
        relation_change = -1 if action == "take" else -3
        game.clan.set_relations(
            game.clan, owner, offset=relation_change
        )

    tile_string = tile.tile_string
    if success and action in {"claim", "take"} and not tile.camp:
        tile.change_owner(game.clan)
        tile = territory_class.get_tile_from_string(tile_string)
    elif action == "attack" and war and success:
        war.win_war(game.clan)
        war.end_war()
        tile = territory_class.get_tile_from_string(tile_string)

    if tile:
        tile.add_event(message)
    game.cur_events_list.append(
        EventInformation(message, ["other_clans"], event_tile=tile_string)
    )


def _roll_interaction(tile, action, owner):
    chance = max(1, 3 + round(tile.desirability()) + tile.strength)
    if not tile.is_bordering(game.clan):
        chance += 6
    if action == "take":
        chance = max(1, round(chance / 2))
    if owner is None:
        chance *= 2
    return random.randrange(chance) == 0


def _interaction_message(
    events, action, tile, owner, success, war, war_started=False
):
    standing = _clan_standing(owner) if owner else "unclaimed"
    if standing not in {"ally", "amicable", "neutral", "tense", "hostile"}:
        standing = "neutral"
    outcome = "success" if success else "failure"
    border = "border" if tile.is_bordering(game.clan) else "not_border"

    if action == "claim":
        options = events["claim"][standing][border][outcome]
    elif action == "take":
        options = [
            event
            for event in events["take"]
            if event["success"] == (None if war_started else success)
            and event["border"] in (border == "border", "any")
            and (standing in event["standing"] or "any" in event["standing"])
            and ("terrain" not in event or tile.poi in event["terrain"])
            and ("herb" not in event or tile.herb in event["herb"])
        ]
        options = [
            text
            for event in options
            for text in event["events"]
        ]
    elif action == "forfeit":
        options = events["forfeit"]
    else:
        attack_events = events["attack"]
        if war:
            location = "camp" if tile.camp else (
                "border" if border == "border" else "territory"
            )
            options = attack_events["at_war"][location].get(tile.terrain, [])
        else:
            options = attack_events["not_at_war"]["camp"][outcome]

    if not options:
        options = [f"c_n makes a move near o_c_n's territory."]
    message = event_text_adjust(
        Cat,
        random.choice(options),
        main_cat=game.clan.leader,
        clan=game.clan,
        other_clan=owner,
        chosen_herb=tile.herb,
        chosen_poi=tile.poi,
    )
    return message


def _clan_standing(other_clan):
    from scripts.config import get_config

    relation = game.clan.get_relations(game.clan, other_clan)
    relation_cap = get_config("reputation.other_clans.relation_cap")
    neutral = get_config("reputation.other_clans.neutral")
    hostile = get_config("reputation.other_clans.hostile")
    if relation >= relation_cap - max(1, (relation_cap - neutral) // 4):
        return "ally"
    if relation > neutral:
        return "amicable"
    if relation > hostile:
        return "neutral"
    if relation > max(0, hostile // 2):
        return "tense"
    return "hostile"


def _forfeit_tile(tile, war):
    if tile.owner is not game.clan or tile.camp:
        return
    tile_string = tile.tile_string
    if war and war.demand == tile:
        new_owner = war.get_opponent_object(game.clan)
        message = event_text_adjust(
            Cat,
            random.choice(load_lang_resource("events/map_interactions.json")["forfeit_war"]),
            clan=game.clan,
            other_clan=new_owner,
        )
        tile.change_owner(new_owner)
        war.end_war()
    else:
        message = event_text_adjust(
            Cat,
            random.choice(load_lang_resource("events/map_interactions.json")["forfeit"]),
            clan=game.clan,
        )
        tile.change_owner(None)
    tile = territory_class.get_tile_from_string(tile_string)
    if tile:
        tile.add_event(message)
    game.cur_events_list.append(
        EventInformation(message, ["other_clans"], event_tile=tile_string)
    )


def _advance_territory_wars():
    for war in game.clan.territory_wars.copy():
        offense = war.get_offense_object()
        defense = war.get_defense_object()
        if not offense or not defense:
            war.end_war()
            continue

        war.duration += 1
        relation = game.clan.get_relations(offense, defense)
        change = random.choice(("rel_up", "neutral", "rel_down"))
        if change == "rel_up":
            war.progress = min(1, war.progress + 1)
            game.clan.set_relations(offense, defense, offset=2)
        elif change == "rel_down":
            war.progress = max(-1, war.progress - 1)
            game.clan.set_relations(offense, defense, offset=-1)

        threshold = 10 - war.duration
        if war.duration < 2 or (relation < threshold and war.duration < 8):
            continue

        winner = None
        if war.duration >= 8 or random.randrange(4) != 0:
            winner = offense if war.progress >= 0 else defense
        demand_tile = war.demand if hasattr(war.demand, "tile_string") else None
        event_tile_string = demand_tile.tile_string if demand_tile else None
        if winner:
            war.win_war(winner)
        war.end_war()

        message = event_text_adjust(
            Cat,
            (
                "c_n wins the war against o_c_n and claims the disputed territory."
                if winner
                else "c_n and o_c_n agree to end their war without a victor."
            ),
            clan=winner or offense,
            other_clan=defense if winner is offense else offense,
        )
        if event_tile_string:
            tile = territory_class.get_tile_from_string(event_tile_string)
            if tile:
                tile.add_event(message)
        game.cur_events_list.append(
            EventInformation(message, ["other_clans"], event_tile=event_tile_string)
        )


def _start_declared_territory_wars():
    clans = [game.clan] + game.clan.all_other_clans
    for index, offense in enumerate(clans):
        for defense in clans[index + 1 :]:
            if defense.group_ID not in game.clan.get_wars(offense.group_ID):
                continue
            if _active_war_between(offense, defense):
                continue
            war_offense = offense
            war_defense = defense
            demands = territory_class.get_tiles(
                ["other_clan_inner_border"], clan=war_offense, other_clan=war_defense
            )
            if not demands:
                demands = territory_class.get_tiles(
                    ["other_clan_inner_border"], clan=war_defense, other_clan=war_offense
                )
                war_offense, war_defense = war_defense, war_offense
            if not demands:
                continue
            war = _start_territory_war(
                war_offense, war_defense, random.choice(demands)
            )
            if war:
                message = event_text_adjust(
                    Cat,
                    "c_n and o_c_n go to war over disputed territory.",
                    clan=war_offense,
                    other_clan=war_defense,
                )
                war.demand.add_event(message)
                game.cur_events_list.append(
                    EventInformation(
                        message,
                        ["other_clans"],
                        event_tile=war.demand.tile_string,
                    )
                )


def _start_territory_war(offense, defense, demand):
    if not offense or not defense or _active_war_between(offense, defense):
        return None
    war = War(
        offense=offense.group_ID,
        defense=defense.group_ID,
        demand=demand,
    )
    game.clan.territory_wars.append(war)
    return war


def _active_war_between(first, second):
    return any(
        war.is_in_war(first, second) for war in game.clan.territory_wars
    )


def _territory_wobble():
    if not game.clan.all_other_clans or random.randrange(45) != 0:
        return
    first = random.choice(game.clan.all_other_clans)
    neighbours = territory_class.get_neighbouring_clans(first)
    neighbours = [
        clan
        for clan in neighbours
        if clan is not game.clan
        and not _active_war_between(first, clan)
    ]
    if not neighbours:
        return
    second = random.choice(neighbours)
    first_tiles = territory_class.get_tiles(
        ["other_clan_border"], clan=first, other_clan=second
    )
    second_tiles = territory_class.get_tiles(
        ["other_clan_inner_border"], clan=first, other_clan=second
    )
    tiles = first_tiles or second_tiles
    if not tiles:
        return
    tile = random.choice(tiles)
    tile_string = tile.tile_string
    old_owner = tile.owner
    if random.randrange(6) == 0:
        tile.change_owner(second if old_owner is first else first)
    event_data = load_lang_resource("events/territory.json")["taken_territory"]
    possible = [event for event in event_data if event["success"] == (tile.owner is not old_owner)]
    if not possible:
        return
    message = event_text_adjust(
        Cat,
        random.choice(random.choice(possible)["events"]),
        clan=old_owner,
        other_clan=second if old_owner is first else first,
    )
    tile = territory_class.get_tile_from_string(tile_string)
    if tile:
        tile.add_event(message)
    game.cur_events_list.append(
        EventInformation(message, ["other_clans"], event_tile=tile_string)
    )

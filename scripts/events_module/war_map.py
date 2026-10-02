import random

import i18n

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.clan_package.settings import get_clan_setting, set_clan_setting
from scripts.clan_package.get_clan_cats import find_alive_cats_with_rank
from scripts.events_module.event_information import EventInformation
from scripts.events_module.text_adjust import (
    adjust_list_text,
    event_text_adjust,
    ongoing_event_text_adjust,
)
from scripts.game_structure import game
from scripts.game_structure.game.switches import (
    Switch,
    switch_get_value,
    switch_set_value,
)
from scripts.game_structure.localization import load_lang_resource
from scripts.territory import territory_class
from scripts.war import War


WAR_TXT = None
TERRITORY_TXT = None
MAP_INTERACTIONS = None
_language = None


def load_other_clan_events():
    global WAR_TXT, TERRITORY_TXT, MAP_INTERACTIONS, _language

    locale = i18n.config.get("locale")
    if _language == locale:
        return

    WAR_TXT = load_lang_resource("events/war.json")
    TERRITORY_TXT = load_lang_resource("events/territory.json")
    MAP_INTERACTIONS = load_lang_resource("events/map_interactions.json")
    _language = locale


def _relation_between(first_clan, second_clan):
    if first_clan is game.clan:
        return first_clan.get_relations(first_clan, second_clan)
    if second_clan is game.clan:
        return game.clan.get_relations(second_clan, first_clan)
    return game.clan.get_relations(first_clan, second_clan)


def _set_relation_between(first_clan, second_clan, value):
    game.clan.set_relations(first_clan, second_clan, value=value)


def check_war():
    load_other_clan_events()
    if game.clan.age <= 4 or not game.clan.all_other_clans:
        return

    switch_set_value(Switch.war_rel_change_type, {})

    for war in game.clan.war.copy():
        offense_clan = war.get_offense_object()
        defense_clan = war.get_defense_object()
        if not offense_clan or not defense_clan:
            war.end_war()
            continue

        threshold = 10
        if "bloodthirsty" in offense_clan.temperament:
            threshold = 12
        if set(offense_clan.temperament).intersection(
            {"mellow", "amiable", "gracious"}
        ):
            threshold = 7
        threshold -= war.duration

        relation = _relation_between(offense_clan, defense_clan)
        if relation >= threshold and war.duration > 1:
            war.end_war()
            find_war_events("conclusion_events", war)
            continue

        war.duration += 1
        relation_change = random.choice(("rel_up", "neutral", "rel_down"))
        war.progress = ("rel_up", "neutral", "rel_down").index(relation_change) - 1
        if relation_change == "rel_up":
            relation += 2
        elif relation_change == "rel_down":
            relation -= 1
        _set_relation_between(offense_clan, defense_clan, max(0, relation))
        relation_changes = switch_get_value(Switch.war_rel_change_type)
        relation_changes.setdefault(offense_clan.group_ID, {})[
            defense_clan.group_ID
        ] = relation_change
        relation_changes.setdefault(defense_clan.group_ID, {})[
            offense_clan.group_ID
        ] = relation_change
        switch_set_value(Switch.war_rel_change_type, relation_changes)
        find_war_events("progress_events", war, relation_change)

    for other_clan in game.clan.all_other_clans:
        if other_clan.get_current_war():
            continue

        possible_clans = (
            game.clan.all_other_clans + [game.clan]
            if game.clan.clancount == "multiclan"
            else [game.clan]
        )
        possible_clans = [
            clan
            for clan in possible_clans
            if clan is not other_clan and not clan.get_current_war()
        ]
        if not possible_clans:
            continue

        opponent = random.choice(possible_clans)
        threshold = 5
        if "bloodthirsty" in other_clan.temperament:
            threshold = 10
        if set(other_clan.temperament).intersection(
            {"mellow", "amiable", "gracious"}
        ):
            threshold = 3

        relation = _relation_between(other_clan, opponent)
        if relation > threshold or random.random() >= 1 / max(1, relation * 3):
            continue

        new_war = War(
            offense=other_clan.group_ID,
            defense=opponent.group_ID,
            duration=0,
            progress=-1,
        )
        new_war.get_demand()
        game.clan.war.append(new_war)
        relation_changes = switch_get_value(Switch.war_rel_change_type)
        relation_changes.setdefault(other_clan.group_ID, {})[
            opponent.group_ID
        ] = "rel_down"
        relation_changes.setdefault(opponent.group_ID, {})[
            other_clan.group_ID
        ] = "rel_down"
        switch_set_value(Switch.war_rel_change_type, relation_changes)
        find_war_events("trigger_events", new_war)


def find_war_events(event_type, war, relation_change=None):
    load_other_clan_events()
    outcome = None
    if event_type == "conclusion_events":
        outcome = random.choice(("offense_wins", "truce", "defense_wins"))

    if relation_change:
        war_events = WAR_TXT[event_type][relation_change]
    elif outcome:
        war_events = WAR_TXT[event_type][outcome]
    else:
        war_events = WAR_TXT[event_type]

    offense_clan = war.get_offense_object()
    defense_clan = war.get_defense_object()
    if not offense_clan or not defense_clan or not war_events:
        return

    available_med = find_alive_cats_with_rank(
        Cat, [CatRank.MEDICINE_CAT], working=True
    )
    is_player_war = war.is_in_war(game.clan)

    filtered_events = []
    for entry in war_events:
        text = entry if isinstance(entry, str) else entry[0]
        if not is_player_war and any(
            token in text for token in ("lead_name", "dep_name", "med_name")
        ):
            continue
        if "lead_name" in text and not game.clan.leader:
            continue
        if "dep_name" in text and not game.clan.deputy:
            continue
        if "med_name" in text and not available_med:
            continue
        filtered_events.append(entry)
    if not filtered_events:
        return

    winner = None
    additional_text = ""
    event_tile = None
    if outcome:
        winner = {
            "offense_wins": offense_clan,
            "truce": None,
            "defense_wins": defense_clan,
        }[outcome]
        if winner:
            war.win_war(winner)
            if war.demand:
                if isinstance(war.demand, str):
                    additional_text = f" {winner.name} wins some {war.demand}."
                else:
                    additional_text = f" {winner.name} wins a piece of territory."
                    event_tile = war.demand
        else:
            additional_text = " No Clan walks away the winner."

    chosen_event = random.choice(filtered_events)
    event_text = chosen_event if isinstance(chosen_event, str) else chosen_event[0]
    event_text = ongoing_event_text_adjust(
        Cat,
        event_text + additional_text,
        other_clan_name=defense_clan.name,
        clan=offense_clan,
    )
    if event_tile is None and not isinstance(chosen_event, str) and len(chosen_event) > 1:
        possible_tiles = territory_class.get_tiles(
            chosen_event[1],
            offense_clan,
            defense_clan,
        )
        if possible_tiles:
            event_tile = random.choice(possible_tiles)

    tile_string = event_tile.tile_string if event_tile else None
    game.cur_events_list.append(
        EventInformation(event_text, ["other_clans"], event_tile=tile_string)
    )
    if event_tile:
        event_tile.add_event(event_text)


def other_clans_territory_wobble():
    load_other_clan_events()
    if len(game.clan.all_other_clans) < 2 or not TERRITORY_TXT:
        return
    if random.randrange(45):
        return

    first_clan = random.choice(game.clan.all_other_clans)
    neighbours = territory_class.get_neighbouring_clans(first_clan)
    neighbours = [clan for clan in neighbours if clan is not game.clan]
    if not neighbours:
        return
    second_clan = random.choice(neighbours)

    first_tiles = territory_class.get_tiles(
        ["other_clan_border"], clan=first_clan, other_clan=second_clan
    )
    second_tiles = territory_class.get_tiles(
        ["other_clan_inner_border"], clan=second_clan, other_clan=first_clan
    )
    first_tiles = [tile for tile in first_tiles if not tile.in_dispute()]
    second_tiles = [tile for tile in second_tiles if not tile.in_dispute()]
    if not first_tiles and not second_tiles:
        return

    success = random.randrange(6) == 0
    number = random.randint(1, 2)
    possible_tiles = first_tiles if number == 1 else second_tiles
    if not possible_tiles:
        possible_tiles = second_tiles if number == 1 else first_tiles
    tile = random.choice(possible_tiles)
    old_owner = first_clan if number == 1 else second_clan
    new_owner = second_clan if number == 1 else first_clan

    if success:
        tile.change_owner(new_owner)
        tile = territory_class.get_tile_from_string(tile.tile_string)

    event_options = [
        event
        for event in TERRITORY_TXT["taken_territory"]
        if event["success"] == success
    ]
    if not event_options:
        return
    event = random.choice(random.choice(event_options)["events"])
    event_text = event_text_adjust(
        Cat, event, clan=old_owner, other_clan=new_owner
    )
    tile.add_event(event_text)
    game.cur_events_list.append(
        EventInformation(
            event_text, ["other_clans"], event_tile=tile.tile_string
        )
    )


def handle_map_interaction_event():
    load_other_clan_events()
    interaction_data = get_clan_setting("map_interaction")
    if not interaction_data:
        return

    tile = territory_class.get_tile_from_string(interaction_data.get("tile"))
    interaction = interaction_data.get("interaction")
    if tile is None or interaction not in MAP_INTERACTIONS:
        set_clan_setting("map_interaction", {})
        return

    other_clan = tile.owner
    events = MAP_INTERACTIONS[interaction]
    possible_events = None
    additional_text = ""

    if tile.in_dispute():
        disputed_war = next(
            (war for war in game.clan.war if war.demand == tile), None
        )
        if disputed_war and interaction == "forfeit":
            other_clan = disputed_war.get_opponent_object(game.clan)
            tile.change_owner(other_clan)
            tile = territory_class.get_tile_from_string(tile.tile_string)
            tile.add_event(
                event_text_adjust(
                    Cat,
                    "o_c_n gain ownership of this territory when c_n forfeited it.",
                    clan=game.clan,
                    other_clan=other_clan,
                )
            )
            disputed_war.end_war()
            set_clan_setting("map_interaction", {})
            return

    if interaction == "attack":
        ongoing_war = game.clan.get_current_war()
        if (
            ongoing_war
            and other_clan
            and other_clan.group_ID
            == ongoing_war.get_opponent_object(game.clan).group_ID
        ):
            ongoing_war.win_war(game.clan)
            ongoing_war.end_war()
            possible_events = events["end_war"]

    success = False
    started_war = False
    if possible_events is None:
        success_chance = 3 + round(tile.desirability()) + tile.strength
        if not tile.is_bordering(game.clan):
            success_chance += 6
        if interaction == "take":
            success_chance = round(success_chance / 2)
        if not other_clan:
            success_chance /= 2

        success = random.random() < 1 / max(1, success_chance)
        war_chance = success_chance if success else success_chance + 5
        if (
            other_clan
            and interaction == "take"
            and not game.clan.get_current_war()
            and not other_clan.get_current_war()
            and random.random() < 1 / max(1, war_chance)
        ):
            started_war = True

        success_key = "war" if started_war else "success" if success else "failure"
        border_key = "border" if tile.is_bordering(game.clan) else "not_border"
        location_key = (
            "camp"
            if tile.camp
            else "border"
            if other_clan
            and tile
            in territory_class.get_tiles(
                ["other_clan_inner_border"],
                clan=game.clan,
                other_clan=other_clan,
            )
            else "territory"
        )
        attack_war_key = (
            "at_war"
            if other_clan and game.clan.get_current_war(other_clan)
            else "not_at_war"
        )
        standing = other_clan.get_standing(game.clan) if other_clan else "unclaimed"

        if interaction == "take":
            other_clan.relations = max(0, other_clan.relations - 1)
            possible_events = get_take_events(
                standing,
                border=tile.is_bordering(game.clan),
                success=None if started_war else success,
                tile=tile,
                events=events,
            )
        elif interaction == "claim":
            if tile.poi in events[standing]:
                possible_events = events[standing][tile.poi][success_key]
            else:
                possible_events = events[standing][border_key][success_key]
        elif interaction == "attack" and tile.camp:
            chances = {"ally": 2, "amicable": 3, "neutral": 5, "tense": 6, "hostile": 5}
            raid_success = random.randrange(chances[standing]) == 0
            possible_events = events[attack_war_key]["camp"][
                "success" if raid_success else "failure"
            ]
            if raid_success:
                additional_text = raid_camp()
            other_clan.relations = max(0, other_clan.relations - (3 if raid_success else 2))
        elif interaction == "attack":
            possible_events = events[attack_war_key][location_key][tile.terrain]
            other_clan.relations = max(0, other_clan.relations - 3)
        else:
            possible_events = events

    possible_events = list(possible_events or [])
    if not game.clan.leader:
        possible_events = [
            event for event in possible_events if "m_c" not in event
        ]
    if not possible_events:
        set_clan_setting("map_interaction", {})
        return

    chosen_event = random.choice(possible_events)
    event_text = event_text_adjust(
        Cat,
        chosen_event,
        main_cat=game.clan.leader,
        clan=game.clan,
        other_clan=other_clan,
    ) + additional_text
    if "(herb)" in event_text:
        herb = tile.herb.replace("_", " ") if tile.herb else "herbs"
        event_text = event_text.replace("(herb)", herb)

    tile_string = tile.tile_string
    game.cur_events_list.append(
        EventInformation(event_text, ["misc"], event_tile=tile_string)
    )
    tile.add_event(event_text)

    if success and not started_war and not tile.camp:
        tile.change_owner(game.clan)
        tile = territory_class.get_tile_from_string(tile_string)
        tile.add_event(
            event_text_adjust(
                Cat, "This territory was claimed by c_n.", clan=game.clan
            )
        )

    if started_war:
        game.clan.war.append(
            War(
                offense=other_clan.group_ID,
                defense=game.clan.group_ID,
                demand=tile,
            )
        )
        other_clan.relations = 1
        tile.add_event(
            event_text_adjust(
                Cat,
                "c_n and o_c_n went to war over this territory.",
                clan=game.clan,
                other_clan=other_clan,
            )
        )

    set_clan_setting("map_interaction", {})


def raid_camp():
    supplies = random.choice((["herbs"], ["prey"], ["prey", "herbs"]))
    if "herbs" in supplies:
        medicine_cats = find_alive_cats_with_rank(
            Cat, [CatRank.MEDICINE_CAT, CatRank.MEDICINE_APPRENTICE]
        )
        medicine_cat = random.choice(medicine_cats) if medicine_cats else None
        herb_names, found_herbs = game.clan.herb_supply.get_found_herbs(
            med_cat=medicine_cat
        )
        game.herb_events_list.append(
            i18n.t(
                "screens.patrol.herb_log_raid",
                count=sum(found_herbs.values()),
                herbs=adjust_list_text(herb_names).capitalize(),
            )
        )
    if "prey" in supplies and game.clan.freshkill_pile:
        game.clan.freshkill_pile.add_freshkill(
            game.clan.freshkill_pile.amount_food_needed()
        )
    return f" ({adjust_list_text(supplies)} gained)"


def get_take_events(standing, border, success, tile, events):
    possible_events = []
    terrain_events = []
    for event in events:
        if standing not in event["standing"]:
            continue
        if event["border"] != "any" and event["border"] != border:
            continue
        if event["success"] != success:
            continue
        if "terrain" in event:
            matches_terrain = (
                tile.poi in event["terrain"]
                or tile.terrain in event["terrain"]
                or (
                    "water" in event["terrain"]
                    and tile.terrain in territory_class.water_types
                )
            )
            if not matches_terrain:
                continue
            terrain_events.extend(event["events"])
        if "herb" in event and tile.herb not in event["herb"]:
            continue
        possible_events.extend(event["events"])
    return terrain_events or possible_events


load_other_clan_events()

import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scripts.cat.cats import Cat
from scripts.clan import Clan
from scripts.clan_package.settings import get_clan_setting, set_clan_setting
from scripts.events_module.event_information import EventInformation
from scripts.events_module.patrol.patrol import Patrol
from scripts.events_module.text_adjust import event_text_adjust
from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource
from scripts.tile import TerritoryTile
from scripts.ui.elements.map_tile import MapTileButton
from scripts.war import War
from scripts.territory_events import (
    _advance_territory_wars,
    _interaction_message,
    _process_map_interaction,
)


class OtherClanStub:
    group_ID = "territory-test-other"
    name = "OtherClan"


class TestTerritory(unittest.TestCase):
    def setUp(self):
        self.previous_clan = game.clan
        self.previous_events = game.cur_events_list
        self.previous_map_interaction = get_clan_setting("map_interaction")
        self.clan = Clan(
            save_id="territory_test",
            self_run_init_functions=False,
        )
        self.other_clan = OtherClanStub()
        self.clan.all_other_clans = [self.other_clan]

    def tearDown(self):
        game.clan = self.previous_clan
        game.cur_events_list = self.previous_events
        set_clan_setting("map_interaction", self.previous_map_interaction)

    def test_tile_event_and_history_lists_are_independent(self):
        first = TerritoryTile()
        second = TerritoryTile()

        first.events.append({"text": "event"})
        first.history.append({"ownership_change": {"old": None, "new": None}})

        self.assertEqual(second.events, [])
        self.assertEqual(second.history, [])

    def test_map_poi_names_resolve_from_the_point_of_interest_translation(self):
        game.clan = self.clan
        tile = TerritoryTile(poi="terrain_abandonednest")

        self.assertIn("abandoned twoleg nest", tile.name_string().lower())
        self.assertIn("tile://0-0", tile.location_link())
        self.assertIn("abandoned twoleg nest", tile.location_link().lower())
        self.assertEqual(
            event_text_adjust(Cat, "POI", chosen_poi="terrain_abandonednest"),
            "the abandoned Twoleg nest",
        )

    def test_generated_territory_is_saved_and_reused(self):
        initial_map = {
            "1-1": {
                "owner": self.clan.group_ID,
                "terrain": "land",
                "camp": True,
            }
        }
        changed_map = {
            "1-1": {
                "owner": None,
                "terrain": "river",
                "camp": False,
            }
        }
        game.clan = self.clan

        with TemporaryDirectory() as save_dir:
            with (
                patch("scripts.clan.get_save_dir", return_value=save_dir),
                patch(
                    "scripts.create_territory.generate_territories",
                    side_effect=[initial_map, changed_map],
                ) as generate_territories,
            ):
                self.clan.load_territory_json()
                first_owner = self.clan.territory_tiles[0].owner
                self.clan.load_territory_json()

        self.assertIs(first_owner, self.clan)
        self.assertIs(self.clan.territory_tiles[0].owner, self.clan)
        generate_territories.assert_called_once()

    def test_event_information_round_trip_preserves_map_location(self):
        event = EventInformation("Patrol event", ["misc"], event_tile="1-1")

        loaded_event = EventInformation.from_dict(event.to_dict(), Cat)

        self.assertEqual(loaded_event.event_tile, "1-1")

    def test_herb_map_view_has_a_color_without_a_herb_color_attribute(self):
        tile = TerritoryTile()
        tile.herb = "chamomile"
        button = MapTileButton.__new__(MapTileButton)
        button.opacity = 255
        button.current_view = "herbs"
        button.tile_object = tile
        button.view_colour = True
        button.view_grid = False
        button.view_terrain = False
        button.icon_tile = False
        button.selected = False

        self.assertTrue(button._get_colour_dict())

    def test_completed_patrol_records_its_tile_only_once(self):
        tile = TerritoryTile(x=1, y=1, owner=self.clan, terrain="land")
        herb_tile = TerritoryTile(x=2, y=1, owner=self.clan, terrain="land")
        herb_tile.herb = "chamomile"
        self.clan.territory_tiles = [tile, herb_tile]
        game.clan = self.clan
        game.cur_events_list = []
        patrol = Patrol()
        patrol.clan = self.clan
        patrol.event_tile = patrol._choose_event_tile("med")
        patrol.did_proceed = True

        self.assertIs(patrol.event_tile, herb_tile)
        patrol.record_location("The patrol returned from the territory.")
        patrol.record_location("The patrol returned from the territory.")

        self.assertEqual(len(herb_tile.events), 1)
        self.assertEqual(tile.events, [])
        self.assertEqual(len(game.cur_events_list), 1)
        self.assertEqual(game.cur_events_list[0].event_tile, herb_tile.tile_string)

    def test_territory_war_round_trip_preserves_diplomacy_wars(self):
        self.clan._territory_group_id_remap = {
            "old-other-id": self.other_clan.group_ID
        }
        self.clan.territory_tiles = self.clan.generate_territories_tile_list(
            {
                "2-3": {
                    "owner": "old-other-id",
                    "terrain": "land",
                }
            }
        )
        tile = self.clan.territory_tiles[0]
        diplomacy_wars = {
            self.clan.group_ID: {
                self.other_clan.group_ID: {"at_war": True, "duration": 2}
            }
        }
        self.clan.war = diplomacy_wars
        self.clan._saved_territory_wars = [
            {
                "offense": self.clan.group_ID,
                "defense": "old-other-id",
                "demand": tile.tile_string,
                "duration": 3,
                "progress": 1,
            }
        ]

        self.clan.load_territory_wars()

        loaded_war = self.clan.territory_wars[0]
        self.assertIs(loaded_war.demand, tile)
        self.assertIs(self.clan.get_current_territory_war(self.other_clan), loaded_war)
        self.assertEqual(loaded_war.get_war_dict()["demand"], "2-3")
        self.assertIs(self.clan.war, diplomacy_wars)

    def test_failed_take_that_starts_war_uses_declaration_text(self):
        self.clan.relations = {
            self.clan.group_ID: {self.other_clan.group_ID: 17}
        }
        tile = TerritoryTile(x=1, y=1, owner=self.other_clan, terrain="land")
        self.clan.territory_tiles = [tile]

        message = _interaction_message(
            load_lang_resource("events/map_interactions.json"),
            "take",
            tile,
            self.other_clan,
            False,
            object(),
            war_started=True,
        )

        self.assertIn("war", message.lower())

    def test_queued_claim_changes_tile_and_clears_action(self):
        tile = TerritoryTile(x=1, y=1, terrain="land")
        self.clan.territory_tiles = [tile]
        self.clan.age = 2
        self.clan.remap_territory_strength = lambda: None
        game.cur_events_list = []
        set_clan_setting(
            "map_interaction",
            {"tile": tile.tile_string, "owner_ID": None, "interaction": "claim"},
        )

        with patch("scripts.territory_events.random.randrange", return_value=0):
            _process_map_interaction()

        self.assertIs(tile.owner, self.clan)
        self.assertEqual(get_clan_setting("map_interaction"), {})
        self.assertTrue(tile.events)
        self.assertEqual(len(game.cur_events_list), 1)
        self.assertEqual(game.cur_events_list[0].event_tile, tile.tile_string)

    def test_war_victory_claims_demand_without_replacing_diplomacy_state(self):
        self.clan.relations = {
            self.clan.group_ID: {self.other_clan.group_ID: 10}
        }
        tile = TerritoryTile(x=1, y=1, owner=self.other_clan, terrain="land")
        self.clan.territory_tiles = [tile]
        self.clan.remap_territory_strength = lambda: None
        diplomacy_wars = {self.clan.group_ID: {self.other_clan.group_ID: {}}}
        self.clan.war = diplomacy_wars
        self.clan.territory_wars = [
            War(
                offense=self.clan.group_ID,
                defense=self.other_clan.group_ID,
                demand=tile,
                duration=1,
            )
        ]
        game.cur_events_list = []

        with (
            patch("scripts.territory_events.random.choice", return_value="rel_up"),
            patch("scripts.territory_events.random.randrange", return_value=1),
        ):
            _advance_territory_wars()

        self.assertIs(tile.owner, self.clan)
        self.assertEqual(self.clan.territory_wars, [])
        self.assertIs(self.clan.war, diplomacy_wars)
        self.assertEqual(game.cur_events_list[0].event_tile, tile.tile_string)


if __name__ == "__main__":
    unittest.main()

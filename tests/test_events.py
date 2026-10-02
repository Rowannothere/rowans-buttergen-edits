import os
import shutil
from typing import List
import unittest
from pathlib import Path
from random import choice, shuffle, randint, Random
from unittest.mock import Mock, patch
from uuid import uuid4

from scripts import events
from scripts.cat import save_load
from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.cat.factories.new_cat_factory import NewCatFactory as cat_factory
from scripts.cat.sprites.load_sprites import sprites
from scripts.clan import Clan, Afterlife
from scripts.clan_package.get_clan_cats import (
    get_living_clan_cat_count,
)
from scripts.clan_package.settings import set_clan_setting
from scripts.events_module.patrol.patrol import Patrol
from scripts.events_module.short.short_event_generation import (
    filter_events,
)
from scripts.events_module.event_information import EventInformation
from scripts.game_structure import game
from scripts.game_structure.game.switches import (
    Switch,
    switch_get_value,
    switch_set_value,
)
from scripts.game_structure.game.save_load import read_clans
from scripts.housekeeping.datadir import get_save_dir
from scripts.cat_relations.inheritance import Inheritance


class TestEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # load in the spritesheets
        # we have to do this to prevent a crash, even though we won't be displaying anything
        sprites.load_all()

        cls.test_clan_name = f"Test_{uuid4()}"

        cls.clanlist = read_clans()
        cls.previously_loaded_clan = cls.clanlist[0] if cls.clanlist else None

        game.starclan = Afterlife()
        game.dark_forest = Afterlife()
        game.clan = Clan(
            save_id=cls.test_clan_name,
            display_name="Test",
            clan_count_mode="multiclan",
            leader=cat_factory.create_cat(rank=CatRank.LEADER),
            deputy=cat_factory.create_cat(rank=CatRank.DEPUTY),
            medicine_cat=cat_factory.create_cat(rank=CatRank.MEDICINE_CAT),
            biome="Forest",
            camp_bg="camp1",
            symbol="symbolADDER0",
            your_cat=cat_factory.create_cat(rank=CatRank.KITTEN),
            game_mode="expanded",
            starting_members=[
                cat_factory.create_cat(rank=rank)
                for rank in [
                    CatRank.KITTEN,
                    CatRank.APPRENTICE,
                    CatRank.APPRENTICE,
                    CatRank.WARRIOR,
                    CatRank.WARRIOR,
                    CatRank.WARRIOR,
                    CatRank.WARRIOR,
                    CatRank.WARRIOR,
                    CatRank.WARRIOR,
                    CatRank.ELDER,
                ]
            ],
            starting_season="Newleaf",
        )
        # dpmo
        # game.clan.your_cat.inheritance = Inheritance(game.clan.your_cat)
        # ---
        save_load.cat_to_fade.clear()
        game.clan.create_clan(your_cat=game.clan.your_cat, unborn=True)
        game.cur_events_list.clear()
        game.herb_events_list.clear()
        game.clan.herb_supply.start_storage(15)
        game.clan.save_herb_supply(game.clan)
        game.clan.grief_strings.clear()
        Cat.sort_cats()
        # prevent them from just dying of starvation
        set_clan_setting("business as usual", False)
        set_clan_setting("hunting", True)

    @classmethod
    def tearDownClass(cls):
        """
        Be a polite bulk test and clean up after yourself
        :return:
        """
        rempath = get_save_dir() + "/" + cls.test_clan_name
        shutil.rmtree(rempath)
        if os.path.exists(rempath + "/clan.json"):
            os.remove(rempath + "/clan.json")

        if cls.previously_loaded_clan:
            with open(Path(get_save_dir()) / "currentclan.txt", "w") as currentclanfile:
                currentclanfile.write(str(cls.previously_loaded_clan))

    def test_random_cat_assignment(self):
        """
        Testing if random_cat is incorrectly reassigned to None when no events are available.
        """
        main_cat = choice(Cat.all_cats_list)
        random_cat = choice(Cat.all_cats_list)
        while random_cat == main_cat:
            random_cat = choice(Cat.all_cats_list)

        chosen_event, new_random_cat = filter_events(
            possible_events=[],
            main_cat=main_cat,
            random_cat=random_cat,
            other_clan=game.clan.all_other_clans[0],
            sub_types=[],
            allowed_events=None,
            excluded_events=None,
            ignore_subtyping=False,
            reduction_avoidance_chance=1,
        )

        self.assertEqual(random_cat, new_random_cat)

    def test_legacy_war_save_migrates_to_war_objects(self):
        other_clan = game.clan.all_other_clans[0]
        game.clan._saved_war_data = {
            str(game.clan.group_ID): {
                str(other_clan.group_ID): {"at_war": True, "duration": 3}
            }
        }

        game.clan.load_war()

        self.assertEqual(len(game.clan.war), 1)
        self.assertEqual(game.clan.war[0].duration, 3)
        self.assertIs(game.clan.war[0].get_opponent_object(game.clan), other_clan)
        game.clan.war = []

    def test_event_tile_survives_event_serialization(self):
        tile = game.clan.territory_tiles[0]
        event = EventInformation("A map event.", ["other_clans"], event_tile=tile.tile_string)

        restored = EventInformation.from_dict(event.to_dict(), Cat)

        self.assertEqual(restored.event_tile, tile.tile_string)

    def test_map_poi_tiles_have_display_names(self):
        for poi_category in ("gathering", "moonplace"):
            tile = next(
                tile for tile in game.clan.territory_tiles if tile.poi == poi_category
            )
            self.assertIn("<b>", tile.name_string())

    def test_load_clan_uses_the_loaded_clan_for_territory_and_war(self):
        loader = Clan()
        loaded_clan = Mock()
        loaded_clan.save_id = "loaded"
        previous_clan = game.clan
        previous_clan_list = switch_get_value(Switch.clan_list)
        loader.load_clan_json = lambda: setattr(game, "clan", loaded_clan)
        loader.add_guide_influence = lambda: None
        switch_set_value(Switch.clan_list, ["loaded"])

        try:
            with patch("scripts.clan.os.path.exists", return_value=True), patch(
                "scripts.clan.get_version", return_value=None
            ), patch("scripts.clan.load_clan_settings"):
                loader.load_clan()

            loaded_clan.load_territory_json.assert_called_once_with()
            loaded_clan.load_war.assert_called_once_with()
        finally:
            game.clan = previous_clan
            switch_set_value(Switch.clan_list, previous_clan_list)

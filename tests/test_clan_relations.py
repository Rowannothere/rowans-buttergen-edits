import unittest
from types import SimpleNamespace

from scripts.clan import Clan
from scripts.game_structure import game


class TestClanRelations(unittest.TestCase):
    def setUp(self):
        self.previous_clan = game.clan
        game.clan = SimpleNamespace(group_ID="1")
        self.clan_manager = object.__new__(Clan)

    def tearDown(self):
        game.clan = self.previous_clan

    def test_player_clan_relations_use_other_clan_map(self):
        other_clan = SimpleNamespace(group_ID="8", relations={"1": 11})

        self.assertEqual(
            11, self.clan_manager.get_relations(game.clan, other_clan)
        )

        self.clan_manager.set_relations(game.clan, other_clan, 17)
        self.assertEqual(17, other_clan.relations["1"])

    def test_other_clan_relations_use_source_clan_map(self):
        source_clan = SimpleNamespace(group_ID="8", relations={"9": 8})
        target_clan = SimpleNamespace(group_ID="9", relations={})

        self.assertEqual(
            8, self.clan_manager.get_relations(source_clan, target_clan)
        )

        self.clan_manager.set_relations(source_clan, target_clan, 14)
        self.assertEqual(14, source_clan.relations["9"])

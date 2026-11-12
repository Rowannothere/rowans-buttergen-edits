import unittest
from random import Random
from types import SimpleNamespace

from scripts.cat.enums import CatRank, CatCompatibility
from scripts.cat.factories.test_cat_factory import TestCatFactory
from scripts.cat_relations.enums import RelType

from scripts.cat.cats import (
    Cat,
    merge_legacy_faith_and_affinity,
    merge_legacy_honor_scores,
)
from scripts.cat_relations.inheritance2 import inheritance_db
from scripts.cat_relations.relationship import Relationship
from scripts.events_module.event_filters import (
    get_highest_romantic_relation,
    get_personality_compatibility,
)
from scripts.clan_package.get_clan_cats import get_alive_clan_queens
from scripts.honor import core
from scripts.lifegen_utility import get_cluster

cat_factory = TestCatFactory()


class TestPersonalityClusters(unittest.TestCase):
    def test_clusters_use_highest_and_lowest_facets(self):
        examples = (
            ("stability", "sociability", "brooding"),
            ("stability", "lawfulness", "cool"),
            ("stability", "aggression", "stable"),
            ("sociability", "stability", "unabashed"),
            ("sociability", "lawfulness", "silly"),
            ("sociability", "aggression", "sweet"),
            ("lawfulness", "stability", "neurotic"),
            ("lawfulness", "sociability", "introspective"),
            ("lawfulness", "aggression", "upstanding"),
            ("aggression", "stability", "hotheaded"),
            ("aggression", "sociability", "assertive"),
            ("aggression", "lawfulness", "unlawful"),
        )
        for highest, lowest, expected in examples:
            with self.subTest(highest=highest, lowest=lowest):
                facets = {
                    "stability": 8,
                    "sociability": 8,
                    "lawfulness": 8,
                    "aggression": 8,
                }
                facets[highest] = 16
                facets[lowest] = 0
                self.assertEqual(get_cluster(SimpleNamespace(**facets)), (expected, ""))

    def test_equal_facets_use_stable_fallback(self):
        personality = SimpleNamespace(
            stability=8,
            sociability=8,
            lawfulness=8,
            aggression=8,
        )
        self.assertEqual(get_cluster(personality), ("stable", ""))


class TestFaithMigration(unittest.TestCase):
    def test_saves_only_unified_faith(self):
        cat = cat_factory.create_cat(disable_random=True)
        cat.faith = 2.8
        cat_data = cat.get_save_dict()

        self.assertIn("faith", cat_data)
        self.assertEqual(cat_data["faith"], 3)
        self.assertIsInstance(cat_data["faith"], int)
        self.assertNotIn("starclan_affinity", cat_data)
        self.assertNotIn("dark_forest_affinity", cat_data)

    def test_merges_legacy_affinities_into_faith(self):
        self.assertEqual(merge_legacy_faith_and_affinity(1, 20, 0), 3)
        self.assertEqual(merge_legacy_faith_and_affinity(1, 0, 20), -1)

    def test_clamps_merged_faith(self):
        self.assertEqual(merge_legacy_faith_and_affinity(8, 100, -100), 9)
        self.assertEqual(merge_legacy_faith_and_affinity(-8, -100, 100), -9)

    def test_cat_faith_is_integer_and_bounded(self):
        cat = cat_factory.create_cat(disable_random=True)
        cat.faith = 3.6
        self.assertEqual(cat.faith, 4)
        self.assertIsInstance(cat.faith, int)

        cat.faith = -50.2
        self.assertEqual(cat.faith, -9)


class TestHonorScoreUnification(unittest.TestCase):
    def test_legacy_scores_are_averaged(self):
        self.assertEqual(merge_legacy_honor_scores(3, 6, 9), 6)
        self.assertEqual(merge_legacy_honor_scores(None, 3, None), 3)

    def test_legacy_score_is_clamped(self):
        self.assertEqual(merge_legacy_honor_scores(100, 100, 100), 9)
        self.assertEqual(merge_legacy_honor_scores(-100, -100, -100), -9)

    def test_reputation_and_trust_share_honor(self):
        cat = cat_factory.create_cat(disable_random=True)
        cat.reputation = 35
        self.assertEqual(cat.honor, 9)
        self.assertEqual(cat.clan_trust, 9)

        cat.clan_trust = -12
        self.assertEqual(cat.honor, -9)
        self.assertEqual(cat.reputation, -9)

    def test_honor_is_integer_and_bounded(self):
        cat = cat_factory.create_cat(disable_random=True)
        cat.honor = 2.7
        self.assertEqual(cat.honor, 3)
        self.assertIsInstance(cat.honor, int)

        cat.honor = -20.4
        self.assertEqual(cat.honor, -9)

    def test_reputation_and_trust_changes_share_honor(self):
        cat = cat_factory.create_cat(disable_random=True)
        core.change_reputation(cat, 5)
        core.change_clan_trust(cat, -8)
        self.assertEqual(cat.honor, -3)
        self.assertEqual(cat.reputation, -3)
        self.assertEqual(cat.clan_trust, -3)

    def test_saves_only_one_honor_score(self):
        cat = cat_factory.create_cat(disable_random=True)
        cat.honor = 2.8
        cat_data = cat.get_save_dict()
        self.assertIn("honor", cat_data)
        self.assertEqual(cat_data["honor"], 3)
        self.assertIsInstance(cat_data["honor"], int)
        self.assertNotIn("reputation", cat_data)
        self.assertNotIn("clan_trust", cat_data)


class TestPersonalityCompatibility(unittest.TestCase):
    current_traits = [
        "adventurous",
        "aloof",
        "ambitious",
        "arrogant",
        "bloodthirsty",
        "bold",
        "bouncy",
        "calm",
        "careful",
        "confident",
        "competitive",
        "cold",
        "charismatic",
        "cunning",
        "cowardly",
        "childish",
        "compassionate",
        "emotional",
        "energetic",
        "fierce",
        "flexible",
        "faithful",
        "flamboyant",
        "grumpy",
        "gloomy",
        "humble",
        "insecure",
        "justified",
        "loyal",
        "lonesome",
        "loving",
        "meek",
        "mellow",
        "methodical",
        "nervous",
        "oblivious",
        "obsessive",
        "playful",
        "reserved",
        "righteous",
        "responsible",
        "rebellious",
        "strict",
        "stoic",
        "sneaky",
        "strange",
        "sincere",
        "shameless",
        "spontaneous",
        "thoughtful",
        "troublesome",
        "trusting",
        "vengeful",
        "witty",
        "wise",
        "impulsive",
        "bullying",
        "attention-seeker",
        "charming",
        "daring",
        "noisy",
        "daydreamer",
        "sweet",
        "polite",
        "know-it-all",
        "bossy",
        "disciplined",
        "patient",
        "manipulative",
        "secretive",
        "rebellious",
        "grumpy",
        "passionate",
        "honest",
        "leader-like",
        "smug",
        "unruly",
        "shy",
        "self-conscious",
        "skittish",
        "fearless",
    ]

    def test_some_neutral_combinations(self):
        # TODO: the one who updated the personality should update the tests!!
        pass
        # cat1 = cat_factory.create_cat()
        # cat2 = cat_factory.create_cat()

    #
    # cat1.personality.trait = self.current_traits[0]
    # cat2.personality.trait = self.current_traits[1]
    # self.assertIsNone(get_personality_compatibility(cat1,cat2))
    # self.assertIsNone(get_personality_compatibility(cat2,cat1))
    #
    # cat1.personality.trait = self.current_traits[3]
    # cat2.personality.trait = self.current_traits[5]
    # self.assertIsNone(get_personality_compatibility(cat1,cat2))
    # self.assertIsNone(get_personality_compatibility(cat2,cat1))
    #
    # cat1.personality.trait = self.current_traits[7]
    # cat2.personality.trait = self.current_traits[10]
    # self.assertIsNone(get_personality_compatibility(cat1,cat2))
    # self.assertIsNone(get_personality_compatibility(cat2,cat1))

    def test_some_positive_combinations(self):
        # TODO: the one who updated the personality should update the tests!!
        pass

    def test_some_negative_combinations(self):
        # TODO: the one who updated the personality should update the tests!!
        pass

    def test_false_trait(self):
        cat1 = cat_factory.create_cat(disable_random=True)
        cat2 = cat_factory.create_cat(disable_random=True)
        cat1.personality.trait = None
        cat2.personality.trait = None
        self.assertEqual(
            get_personality_compatibility(cat1, cat2), CatCompatibility.NEUTRAL
        )
        self.assertEqual(
            get_personality_compatibility(cat2, cat1), CatCompatibility.NEUTRAL
        )


class TestCountRelation(unittest.TestCase):
    def test_2_cats_jealousy(self):
        # given
        cat1 = cat_factory.create_cat(disable_random=True)
        cat2 = cat_factory.create_cat(disable_random=True)
        cat3 = cat_factory.create_cat(disable_random=True)
        cat4 = cat_factory.create_cat(disable_random=True)

        relation_1_2 = Relationship(cat_from=cat1, cat_to=cat2)
        relation_3_2 = Relationship(cat_from=cat3, cat_to=cat2)
        relation_4_2 = Relationship(cat_from=cat4, cat_to=cat2)
        cat1.relationships[cat2.ID] = relation_1_2
        cat3.relationships[cat2.ID] = relation_3_2
        cat4.relationships[cat2.ID] = relation_4_2
        relation_1_2.link_relationship()
        relation_3_2.link_relationship()
        relation_4_2.link_relationship()

        # when
        relation_1_2.respect -= 20
        relation_3_2.respect -= 20
        relation_4_2.respect -= 10

        # then
        temp_dict = {v: [] for v in [*RelType]}

        for inter_cat in [cat1, cat2, cat3, cat4]:
            if cat2.ID in inter_cat.relationships:
                relation = inter_cat.relationships[cat2.ID]
            else:
                continue

            for value in [*RelType]:
                temp_dict[value].append(relation.get_amount_of_type(value) <= -20)

        relation_dict = {v: sum(temp_dict[v]) for v in [*RelType]}

        self.assertEqual(relation_dict["romance"], 0)
        self.assertEqual(relation_dict["like"], 0)
        self.assertEqual(relation_dict["respect"], 2)
        self.assertEqual(relation_dict["comfort"], 0)
        self.assertEqual(relation_dict["trust"], 0)


class TestHighestRomance(unittest.TestCase):
    def test_exclude_mate(self):
        # given
        cat1 = cat_factory.create_cat(disable_random=True)
        cat2 = cat_factory.create_cat(disable_random=True)
        cat3 = cat_factory.create_cat(disable_random=True)
        cat4 = cat_factory.create_cat(disable_random=True)

        # when
        cat1.mate.append(cat2.ID)
        cat2.mate.append(cat1.ID)
        relation_1_2 = Relationship(cat_from=cat1, cat_to=cat2)
        relation_1_3 = Relationship(cat_from=cat1, cat_to=cat3)
        relation_1_4 = Relationship(cat_from=cat1, cat_to=cat4)
        relation_1_2.romance = 60
        relation_1_3.romance = 50
        relation_1_4.romance = 40

        relations = [relation_1_2, relation_1_3, relation_1_4]

        # then
        self.assertNotEqual(
            relation_1_2, get_highest_romantic_relation(relations, exclude_mate=True)
        )
        self.assertEqual(
            relation_1_3, get_highest_romantic_relation(relations, exclude_mate=True)
        )
        self.assertNotEqual(
            relation_1_4, get_highest_romantic_relation(relations, exclude_mate=True)
        )

    def test_include_mate(self):
        # given
        cat1 = cat_factory.create_cat(disable_random=True)
        cat2 = cat_factory.create_cat(disable_random=True)
        cat3 = cat_factory.create_cat(disable_random=True)
        cat4 = cat_factory.create_cat(disable_random=True)

        # when
        cat1.mate.append(cat2.ID)
        cat2.mate.append(cat1.ID)
        relation_1_2 = Relationship(cat_from=cat1, cat_to=cat2)
        relation_1_3 = Relationship(cat_from=cat1, cat_to=cat3)
        relation_1_4 = Relationship(cat_from=cat1, cat_to=cat4)
        relation_1_2.romance = 60
        relation_1_3.romance = 50
        relation_1_4.romance = 40

        relations = [relation_1_2, relation_1_3, relation_1_4]

        # then
        self.assertEqual(
            relation_1_2, get_highest_romantic_relation(relations, exclude_mate=False)
        )
        self.assertNotEqual(
            relation_1_3, get_highest_romantic_relation(relations, exclude_mate=False)
        )
        self.assertNotEqual(
            relation_1_4, get_highest_romantic_relation(relations, exclude_mate=False)
        )


class TestGetQueens(unittest.TestCase):
    def setUp(self) -> None:
        self.test_cat1 = cat_factory.create_cat(
            status_dict={"rank": CatRank.WARRIOR}, disable_random=True
        )
        self.test_cat2 = cat_factory.create_cat(
            status_dict={"rank": CatRank.WARRIOR}, disable_random=True
        )
        self.test_cat3 = cat_factory.create_cat(
            status_dict={"rank": CatRank.WARRIOR}, disable_random=True
        )
        self.test_cat4 = cat_factory.create_cat(
            status_dict={"rank": CatRank.WARRIOR}, disable_random=True
        )
        self.test_cat5 = cat_factory.create_cat(
            status_dict={"rank": CatRank.WARRIOR}, disable_random=True
        )
        self.test_cat6 = cat_factory.create_cat(
            status_dict={"rank": CatRank.WARRIOR}, disable_random=True
        )

    def tearDown(self) -> None:
        del self.test_cat1
        del self.test_cat2
        del self.test_cat3
        del self.test_cat4
        del self.test_cat5
        del self.test_cat6

    def test_single_mother(self):
        # given
        # young enough kid
        self.test_cat1.phenotype.Generator("fem")

        self.test_cat2.status._change_rank(CatRank.KITTEN)
        self.test_cat2.parent1 = self.test_cat1.ID

        # too old kid
        self.test_cat3.phenotype.Generator("fem")

        self.test_cat4.status._change_rank(CatRank.APPRENTICE)
        self.test_cat4.parent1 = self.test_cat3.ID

        inheritance_db.load_inheritances(Cat)

        # then
        living_cats = [self.test_cat1, self.test_cat2, self.test_cat3, self.test_cat4]
        self.assertEqual(
            [self.test_cat1.ID], list(get_alive_clan_queens(living_cats)[0].keys())
        )

    def test_single_father(self):
        # given
        # young enough kid
        self.test_cat1.phenotype.Generator("masc")

        self.test_cat2.status._change_rank(CatRank.KITTEN)
        self.test_cat2.parent1 = self.test_cat1.ID

        # too old kid
        self.test_cat3.phenotype.Generator("masc")

        self.test_cat4.status._change_rank(CatRank.APPRENTICE)
        self.test_cat4.parent1 = self.test_cat3.ID

        inheritance_db.load_inheritances(Cat)

        # then
        living_cats = [self.test_cat1, self.test_cat2, self.test_cat3, self.test_cat4]
        self.assertEqual(
            [self.test_cat1.ID], list(get_alive_clan_queens(living_cats)[0].keys())
        )

    def tests_hetero_pair(self):
        # given
        # young enough kid
        self.test_cat1.phenotype.Generator("fem")

        self.test_cat2.phenotype.Generator("masc")

        self.test_cat3.status._change_rank(CatRank.KITTEN)
        self.test_cat3.parent1 = self.test_cat2.ID
        self.test_cat3.parent2 = self.test_cat1.ID

        # too old kid
        self.test_cat4.phenotype.Generator("fem")

        self.test_cat5.phenotype.Generator("masc")

        self.test_cat6.status._change_rank(CatRank.APPRENTICE)
        self.test_cat6.parent1 = self.test_cat5.ID
        self.test_cat6.parent2 = self.test_cat4.ID

        inheritance_db.load_inheritances(Cat)

        # then
        living_cats = [
            self.test_cat1,
            self.test_cat2,
            self.test_cat3,
            self.test_cat4,
            self.test_cat5,
            self.test_cat6,
        ]
        self.assertEqual(
            [self.test_cat1.ID], list(get_alive_clan_queens(living_cats)[0].keys())
        )

    def test_gay_pair(self):
        # given
        # young enough kid
        self.test_cat1.phenotype.Generator("masc")

        self.test_cat2.phenotype.Generator("masc")

        self.test_cat3.status._change_rank(CatRank.KITTEN)
        self.test_cat3.parent1 = self.test_cat2.ID
        self.test_cat3.parent2 = self.test_cat1.ID

        # too old kid
        self.test_cat4.phenotype.Generator("masc")

        self.test_cat5.phenotype.Generator("masc")

        self.test_cat6.status._change_rank(CatRank.APPRENTICE)
        self.test_cat6.parent1 = self.test_cat5.ID
        self.test_cat6.parent2 = self.test_cat4.ID

        inheritance_db.load_inheritances(Cat)

        # then
        living_cats = [
            self.test_cat1,
            self.test_cat2,
            self.test_cat3,
            self.test_cat4,
            self.test_cat5,
            self.test_cat6,
        ]
        self.assertTrue(
            [self.test_cat1.ID] == list(get_alive_clan_queens(living_cats)[0].keys())
            or [self.test_cat2.ID] == list(get_alive_clan_queens(living_cats)[0].keys())
        )

    def test_lesbian_pair(self):
        # given
        # young enough kid
        self.test_cat1.phenotype.Generator("fem")

        self.test_cat2.phenotype.Generator("fem")

        self.test_cat3.status._change_rank(CatRank.KITTEN)
        self.test_cat3.parent1 = self.test_cat2.ID
        self.test_cat3.parent2 = self.test_cat1.ID

        # too old kid
        self.test_cat4.phenotype.Generator("fem")

        self.test_cat5.phenotype.Generator("fem")

        self.test_cat6.status._change_rank(CatRank.APPRENTICE)
        self.test_cat6.parent1 = self.test_cat5.ID
        self.test_cat6.parent2 = self.test_cat4.ID

        inheritance_db.load_inheritances(Cat)

        # then
        living_cats = [
            self.test_cat1,
            self.test_cat2,
            self.test_cat3,
            self.test_cat4,
            self.test_cat5,
            self.test_cat6,
        ]
        self.assertTrue(
            [self.test_cat1.ID] == list(get_alive_clan_queens(living_cats)[0].keys())
            or [self.test_cat2.ID] == list(get_alive_clan_queens(living_cats)[0].keys())
        )

    def test_poly_pair(self):
        # given
        # young enough kid
        self.test_cat1.phenotype.Generator("fem")

        self.test_cat2.phenotype.Generator("fem")

        self.test_cat3.phenotype.Generator("masc")

        self.test_cat4.status._change_rank(CatRank.KITTEN)
        self.test_cat4.parent1 = self.test_cat2.ID
        self.test_cat4.parent2 = self.test_cat1.ID
        self.test_cat4.adoptive_parents.append(self.test_cat3.ID)

        inheritance_db.load_inheritances(Cat)

        # then
        living_cats = [
            self.test_cat1,
            self.test_cat2,
            self.test_cat3,
            self.test_cat4,
            self.test_cat5,
            self.test_cat6,
        ]
        self.assertEqual(
            [self.test_cat2.ID], list(get_alive_clan_queens(living_cats)[0].keys())
        )

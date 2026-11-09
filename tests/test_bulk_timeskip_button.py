import unittest
from types import SimpleNamespace
from unittest.mock import patch

from scripts.events_module import bulk_timeskip
from scripts.game_structure.game.switches import Switch


class BulkTimeskipTest(unittest.TestCase):
    def _run_bulk_skip(self, weekly, starting_week=0):
        clan = SimpleNamespace(age=3, weeks=starting_week)
        switch_values = {
            Switch.patrol_category: "date",
            Switch.talk_category: "flirt",
        }

        def set_switch(switch, value):
            switch_values[switch] = value

        def advance_one_skip():
            if weekly:
                clan.weeks = (clan.weeks + 1) % bulk_timeskip.weekskip.WEEKS_IN_MOON
                if clan.weeks == 0:
                    clan.age += 1
            else:
                clan.age += 1

        with (
            patch.object(bulk_timeskip.game, "clan", clan),
            patch.object(bulk_timeskip.weekskip, "on", return_value=weekly),
            patch.object(
                bulk_timeskip,
                "switch_get_value",
                side_effect=lambda switch: switch_values[switch],
            ),
            patch.object(bulk_timeskip, "switch_set_value", side_effect=set_switch),
            patch("scripts.events.one_moon", side_effect=advance_one_skip) as one_moon,
            patch.object(bulk_timeskip, "_automate_moon") as automate_moon,
        ):
            bulk_timeskip.bulk_timeskip()

        self.assertEqual(clan.age, 15)
        self.assertEqual(automate_moon.call_count, 12)
        self.assertEqual(switch_values[Switch.patrol_category], "date")
        self.assertEqual(switch_values[Switch.talk_category], "flirt")
        return one_moon.call_count

    def test_bulk_skip_advances_twelve_moons(self):
        self.assertEqual(self._run_bulk_skip(weekly=False), 12)

    def test_weekskip_advances_twelve_full_moons_from_mid_moon(self):
        self.assertEqual(self._run_bulk_skip(weekly=True, starting_week=2), 46)


if __name__ == "__main__":
    unittest.main()

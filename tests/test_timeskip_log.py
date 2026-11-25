import tempfile
import unittest
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.events_module import timeskip_log


class Rank(Enum):
    WARRIOR = "warrior"


class TimeskipLogTest(unittest.TestCase):
    def setUp(self):
        self.clan = SimpleNamespace(
            save_id="TestClan",
            name="TestClan",
            group_ID="test-clan",
            age=0,
            weeks=1,
            current_season="Newleaf",
            biome="Forest",
            all_other_clans=[],
        )
        self.cat = SimpleNamespace(
            name="Testcat",
            moons=12,
            dead=False,
            thought="Is thinking about the forest",
            status=SimpleNamespace(group_ID=self.clan.group_ID, rank=Rank.WARRIOR),
        )
        self.event = SimpleNamespace(
            clan=self.clan.group_ID, text="A patrol returns to camp."
        )

    def test_weekskip_writes_sections_and_appends_activities(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(timeskip_log, "get_save_dir", return_value=temp_dir),
                patch.object(timeskip_log.weekskip, "on", return_value=True),
            ):
                timeskip_log.record_timeskip(
                    self.clan, [self.clan], [self.cat], [self.event]
                )
                timeskip_log.record_activity(
                    self.clan,
                    self.clan,
                    "Patrols",
                    "Testcat patrols the border.",
                    living_cats=[self.cat],
                )
                timeskip_log.record_activity(
                    self.clan,
                    self.clan,
                    "Dialogue",
                    'Testcat: "The forest is quiet."',
                    living_cats=[self.cat],
                )

            log_path = (
                Path(temp_dir) / "TestClan" / "moon_logs" / "Moon 0" / "Week 1.txt"
            )
            text = log_path.read_text(encoding="utf-8")
            self.assertIn("### Clan Members", text)
            self.assertIn("- Testcat - 12 moons - warrior", text)
            self.assertIn("### Events\n- A patrol returns to camp.", text)
            self.assertIn("### Patrols\n- Testcat patrols the border.", text)
            self.assertIn('### Dialogue\n- Testcat: "The forest is quiet."', text)
            self.assertIn("Testcat thinks: Is thinking about the forest", text)

    def test_non_weekskip_uses_one_file_per_moon(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(timeskip_log, "get_save_dir", return_value=temp_dir),
                patch.object(timeskip_log.weekskip, "on", return_value=False),
            ):
                path = timeskip_log.get_log_path(self.clan)

            self.assertEqual(
                path,
                Path(temp_dir) / "TestClan" / "moon_logs" / "Moon 0.txt",
            )

    def test_fourth_week_stays_in_the_previous_moons_folder(self):
        self.clan.age = 1
        self.clan.weeks = 0
        with patch.object(timeskip_log.weekskip, "on", return_value=True):
            week_four = timeskip_log._period(self.clan)
            self.clan.weeks = 1
            next_moon = timeskip_log._period(self.clan)

        self.assertEqual(week_four, (0, 4))
        self.assertEqual(next_moon, (1, 1))


if __name__ == "__main__":
    unittest.main()

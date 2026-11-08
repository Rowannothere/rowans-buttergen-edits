import unittest

from scripts.screens.EventsScreen import _has_clan_time_progressed


class TestEventsScreenTimeProgress(unittest.TestCase):
    def test_new_clan_has_not_progressed_before_first_skip(self):
        self.assertFalse(_has_clan_time_progressed(0, 0, False))
        self.assertFalse(_has_clan_time_progressed(0, 0, True))

    def test_week_skips_progress_before_first_full_moon(self):
        for weeks in (1, 2, 3):
            with self.subTest(weeks=weeks):
                self.assertTrue(_has_clan_time_progressed(0, weeks, True))

    def test_full_moon_progress_is_unchanged(self):
        self.assertTrue(_has_clan_time_progressed(1, 0, False))
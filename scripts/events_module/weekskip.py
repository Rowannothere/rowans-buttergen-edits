"""BUTTERGEN: skipping by weeks instead of moons, from Rowan's idea.

With the "weekskip" Clan setting on, every skip is a week and every 4th one is also a full moon.
- Every week: relationships, chats, thoughts, your cat's own events, and talking, flirting and
  patrolling open up again.
- Every week, but each roll only 1 week in 4 on average: big events like deaths, injuries,
  illnesses, new cats, accessories and murders, so they come as often per moon as without weeks.
- Only on the full moon: anything that counts time, like aging, pregnancies and births, healing,
  ceremonies, experience, fresh-kill and herbs, outbreaks, seasons and the Clan's age.

The week is kept in game.clan.weeks (0 to 3, 0 is the full moon).
"""
from contextlib import contextmanager
from random import randint, random

from scripts.clan_package.settings import get_clan_setting
from scripts.game_structure import game

WEEKS_IN_MOON = 4


def on() -> bool:
    return bool(game.clan) and bool(get_clan_setting("weekskip"))


def _unborn() -> bool:
    your_cat = getattr(game.clan, "your_cat", None) if game.clan else None
    return bool(your_cat) and your_cat.moons < 0


def advance() -> bool:
    """Moves on one skip and says if it's a full moon. Your cat is always born on the first skip,
    whatever the week."""
    if not on() or _unborn():
        if game.clan:
            game.clan.weeks = 0
        return True
    game.clan.weeks = (getattr(game.clan, "weeks", 0) + 1) % WEEKS_IN_MOON
    return game.clan.weeks == 0


def full_moon() -> bool:
    """If the skip that just happened was a full moon"""
    return not on() or getattr(game.clan, "weeks", 0) == 0


def next_is_full_moon() -> bool:
    """If the next skip will be a full moon, for things that happen right before one"""
    return not on() or _unborn() or getattr(game.clan, "weeks", 0) == WEEKS_IN_MOON - 1


def big_event_roll() -> bool:
    """True if a big event gets its roll this skip. With weeks on that's 1 skip in 4 on average,
    so big events come as often per moon as they do without weeks."""
    return not on() or randint(1, WEEKS_IN_MOON) == 1


def age_text(moons: int) -> str:
    """Like "12 moons" or "12 moons, 2 weeks". The weeks only show with weeks on."""
    text = f"{moons} moon" if moons == 1 else f"{moons} moons"
    weeks = getattr(game.clan, "weeks", 0) if game.clan else 0
    if on() and weeks:
        text += ", 1 week" if weeks == 1 else f", {weeks} weeks"
    return text


# ------------------------------------------------------------------ prey and herbs
# With weeks on you can hunt and gather every week, so what comes in during a week counts for a
# quarter, and a moon of weekly patrols brings in what one patrol a moon did. The Clan's own moon
# gathering (auto fresh-kill, focus, the healers' herbs) runs inside moon_work() and isn't cut.
_moon_work = 0


@contextmanager
def moon_work():
    global _moon_work
    _moon_work += 1
    try:
        yield
    finally:
        _moon_work -= 1


def weekly_prey(amount):
    if not on() or _moon_work:
        return amount
    return amount / WEEKS_IN_MOON


def weekly_herbs(count: int) -> int:
    """A quarter, rounded up or down at random so small finds still add up over a moon"""
    if not on() or _moon_work:
        return count
    whole, left = divmod(int(count), WEEKS_IN_MOON)
    return whole + (1 if random() < left / WEEKS_IN_MOON else 0)

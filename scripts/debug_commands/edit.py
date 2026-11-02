"""
Cat editor console commands. Lets the player change almost anything about any cat from the
debug console (press F3 or ` in game). Type "edit help" for the list of sub commands.
Only works when the Cat Editor setting is on.
"""

from typing import List, Optional

from scripts.cat.cats import Cat
from scripts.cat.enums import CatRank
from scripts.cat.personality import Personality
from scripts.cat_relations.enums import RelType
from scripts.debug_commands.command import Command
from scripts.debug_commands.utils import add_output_line_to_log as say
from scripts.game_structure import game
from scripts.cat_editor_logic import (
    editor_enabled,
    REL_PRESETS,
    FAITH_MODES as LOGIC_FAITH_MODES,
    apply_preset,
    set_faith_mode,
    set_rel_stat,
)

REL_STATS = [str(r) for r in RelType]
FAITH_MODES = LOGIC_FAITH_MODES

FLAGS = ["no_mates", "no_kits", "no_faith", "no_retire"]


def find_cat(query: str) -> Optional[Cat]:
    """Find a cat by ID, full name, or a unique name prefix (case insensitive)."""
    q = query.strip().lower()
    cats = list(Cat.all_cats_list)
    for cat in cats:
        if cat.ID == query:
            return cat
    exact = [c for c in cats if str(c.name).lower() == q]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        say(f"More than one cat is named '{query}'. Use an ID instead (see: edit find {query}).")
        return None
    partial = [c for c in cats if str(c.name).lower().startswith(q) or c.name.prefix.lower() == q]
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        say(f"'{query}' matches {len(partial)} cats. Be more specific or use an ID (edit find {query}).")
        return None
    say(f"No cat found for '{query}'. Names with spaces need quotes, e.g. \"Fire star\".")
    return None


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def parse_int(text: str) -> Optional[int]:
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def describe(cat: Cat) -> str:
    return f"{cat.name} ({cat.ID})"


class FindCommand(Command):
    name = "find"
    description = "Search cats by part of a name"
    usage = "<text>"

    def callback(self, args: List[str]):
        if not args:
            say("Usage: edit find <text>")
            return
        q = " ".join(args).lower()
        hits = [c for c in Cat.all_cats_list if q in str(c.name).lower()]
        if not hits:
            say("No matches.")
        for c in hits[:40]:
            say(f"{c.ID} - {c.name}, {c.status.rank}, {c.moons} moons{' (dead)' if c.dead else ''}")
        if len(hits) > 40:
            say(f"...and {len(hits) - 40} more. Narrow the search.")


class InfoCommand(Command):
    name = "info"
    description = "Show a cat's faith, mates and flags"
    usage = "<cat>"

    def callback(self, args: List[str]):
        if not args:
            say("Usage: edit info <cat>")
            return
        cat = find_cat(args[0])
        if not cat:
            return
        mates = [str(Cat.fetch_cat(m).name) for m in cat.mate if Cat.fetch_cat(m)]
        say(f"{describe(cat)}: {cat.status.rank}, {cat.moons} moons, trait {cat.personality.trait}")
        say(
            f"faith {cat.faith} (effective {cat.get_effective_faith()}), lock '{cat.lock_faith}', "
            f"df trainee: {cat.joined_df}, no_faith: {cat.no_faith}"
        )
        say(f"mates: {', '.join(mates) if mates else 'none'}")
        say(
            f"flags: no_mates={cat.no_mates}, no_kits={cat.no_kits}, no_retire={cat.no_retire}"
        )


class FaithCommand(Command):
    name = "faith"
    description = "Set a cat's faith: starclan, darkforest, neutral, flexible, none, or a number -9..9"
    usage = "<cat> <starclan|darkforest|neutral|flexible|none|-9..9>"

    def callback(self, args: List[str]):
        if len(args) < 2:
            say("Usage: edit faith <cat> <starclan|darkforest|neutral|flexible|none|-9..9>")
            return
        cat = find_cat(args[0])
        if not cat:
            return
        mode = args[1].lower().replace("_", "").replace(" ", "")
        if mode == "df":
            mode = "darkforest"
        if mode == "nofaith":
            mode = "none"
        number = parse_int(mode)
        if number is not None:
            ok = set_faith_mode(cat, "number", number)
        else:
            ok = set_faith_mode(cat, mode)
        if not ok:
            say(f"Unknown faith '{args[1]}'. Options: {', '.join(FAITH_MODES)} or a number -9..9")
            return
        say(f"{cat.name}: faith {cat.faith}, lock '{cat.lock_faith}', df trainee {cat.joined_df}, no_faith {cat.no_faith}.")


class RelCommand(Command):
    name = "rel"
    description = "Set a relationship stat (negatives allowed): like, respect, trust, comfort, romance, or all"
    usage = "<from cat> <to cat> <like|respect|trust|comfort|romance|all> <-100..100> [both]"

    def callback(self, args: List[str]):
        if len(args) < 4:
            say(f"Usage: edit rel {self.usage}")
            return
        a, b = find_cat(args[0]), find_cat(args[1])
        if not a or not b:
            return
        if a.ID == b.ID:
            say("Pick two different cats.")
            return
        stat = args[2].lower()
        value = parse_int(args[3])
        if value is None:
            say("The value must be a whole number.")
            return
        stats = REL_STATS if stat == "all" else [stat]
        if any(s not in REL_STATS for s in stats):
            say(f"Unknown stat '{stat}'. Options: {', '.join(REL_STATS)}, all")
            return
        both = len(args) > 4 and args[4].lower() in ("both", "mutual", "true")
        for s in stats:
            set_rel_stat(a, b, s, value)
            if both:
                set_rel_stat(b, a, s, value)
        say(f"Set {a.name} -> {b.name} {stat} to {value}{' (and back)' if both else ''}.")


class PresetCommand(Command):
    name = "feel"
    description = "Quick relationship presets: " + ", ".join(REL_PRESETS)
    usage = "<from cat> <to cat> <preset> [both]"

    def callback(self, args: List[str]):
        if len(args) < 3:
            say(f"Usage: edit feel {self.usage}")
            say("Presets: " + ", ".join(REL_PRESETS))
            return
        a, b = find_cat(args[0]), find_cat(args[1])
        if not a or not b:
            return
        if a.ID == b.ID:
            say("Pick two different cats.")
            return
        preset = args[2].lower()
        if preset not in REL_PRESETS:
            say("Unknown preset. Options: " + ", ".join(REL_PRESETS))
            return
        both = len(args) > 3 and args[3].lower() in ("both", "mutual", "true")
        apply_preset(a, b, preset, both)
        say(f"{a.name} now feels '{preset}' toward {b.name}{' and vice versa' if both else ''}.")


class MateCommand(Command):
    name = "mate"
    description = "Make two cats mates. Cats can have several mates, so this makes open relationships and polycules"
    usage = "<cat> <cat> [more cats...]"

    def callback(self, args: List[str]):
        if len(args) < 2:
            say("Usage: edit mate <cat> <cat> [more cats...]  (3+ cats = everyone becomes mates with everyone)")
            return
        cats = [find_cat(a) for a in args]
        if any(c is None for c in cats):
            return
        if len({c.ID for c in cats}) != len(cats):
            say("Each cat can only be listed once.")
            return
        for i, a in enumerate(cats):
            for b in cats[i + 1:]:
                a.set_mate(b)
        say("Mates set: " + ", ".join(str(c.name) for c in cats))


class UnmateCommand(Command):
    name = "unmate"
    description = "End a mate bond between two cats"
    usage = "<cat> <cat>"

    def callback(self, args: List[str]):
        if len(args) < 2:
            say("Usage: edit unmate <cat> <cat>")
            return
        a, b = find_cat(args[0]), find_cat(args[1])
        if not a or not b:
            return
        if b.ID not in a.mate:
            say(f"{a.name} and {b.name} are not mates.")
            return
        a.unset_mate(b)
        say(f"{a.name} and {b.name} are no longer mates.")


class RankCommand(Command):
    name = "rank"
    description = "Change a cat's rank (use quotes or underscores for 'medicine cat')"
    usage = "<cat> <rank>"

    def callback(self, args: List[str]):
        if len(args) < 2:
            say("Usage: edit rank <cat> <rank>")
            say("Ranks: " + ", ".join(str(r) for r in CatRank))
            return
        cat = find_cat(args[0])
        if not cat:
            return
        want = " ".join(args[1:]).lower().replace("_", " ")
        rank = next((r for r in CatRank if str(r) == want), None)
        if rank is None:
            say("Unknown rank. Ranks: " + ", ".join(str(r) for r in CatRank))
            return
        if rank == CatRank.LEADER:
            game.clan.new_leader(cat)
        else:
            cat.rank_change(rank, resort=True)
            if rank == CatRank.DEPUTY:
                game.clan.new_deputy(cat)
        say(f"{cat.name} is now {cat.status.rank}.")


class TraitCommand(Command):
    name = "trait"
    description = "Change a cat's personality trait"
    usage = "<cat> <trait>"

    def callback(self, args: List[str]):
        if len(args) < 2:
            say("Usage: edit trait <cat> <trait>")
            return
        cat = find_cat(args[0])
        if not cat:
            return
        table = Personality.trait_ranges["kit_traits" if cat.personality.kit else "normal_traits"]
        trait = args[1].lower()
        if trait not in table:
            say("Unknown trait. Options: " + ", ".join(sorted(table)))
            return
        cat.personality.trait = trait
        say(f"{cat.name}'s trait is now {trait}.")


class FlagCommand(Command):
    name = "flag"
    description = "Turn a behaviour flag on/off: " + ", ".join(FLAGS)
    usage = "<cat> <flag> <on|off>"

    def callback(self, args: List[str]):
        if len(args) < 3:
            say(f"Usage: edit flag {self.usage}")
            return
        cat = find_cat(args[0])
        if not cat:
            return
        flag = args[1].lower()
        if flag not in FLAGS:
            say("Unknown flag. Options: " + ", ".join(FLAGS))
            return
        setattr(cat, flag, args[2].lower() in ("on", "true", "yes", "1"))
        say(f"{cat.name}: {flag} = {getattr(cat, flag)}")


class EditCommand(Command):
    name = "edit"
    description = "Cat editor (faith, relationships, mates, rank, trait). Try: edit help"
    aliases = ["tg", "e"]
    sub_commands = [
        FindCommand(),
        InfoCommand(),
        FaithCommand(),
        RelCommand(),
        PresetCommand(),
        MateCommand(),
        UnmateCommand(),
        RankCommand(),
        TraitCommand(),
        FlagCommand(),
    ]

    def callback(self, args: List[str]):
        say("Cat editor. Cats can be given by name, unique name start, or ID. Use \"quotes\" for names with spaces.")
        for sub in self.sub_commands:
            say(f"  edit {sub.name} {sub.usage}")
            say(f"      {sub.description}")


def _needs_editor(callback):
    """stops the edit commands from doing anything while the cat editor setting is off"""

    def wrapped(self, args: List[str]):
        if not editor_enabled():
            say("The cat editor is turned off. Turn on 'Cat Editor' in the game settings to use it.")
            return
        return callback(self, args)

    return wrapped


for _cmd in (EditCommand, FindCommand, InfoCommand, FaithCommand, RelCommand, PresetCommand,
             MateCommand, UnmateCommand, RankCommand, TraitCommand, FlagCommand):
    _cmd.callback = _needs_editor(_cmd.callback)

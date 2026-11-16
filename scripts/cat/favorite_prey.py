"""BUTTERGEN: each cat's favorite and disliked prey, picked from their home biome's prey (kittypets
get kittypet food). Picked the first time it's needed, then kept. Lines that say "r_c's favorite
prey" or "{PRONOUN/r_c/poss} least favorite prey" name it (process_text calls name_in_text)."""

import re
from random import choice, random

from scripts.game_structure import game
from scripts.game_structure.localization import load_lang_resource

KITTYPET_FOOD = ("kibble", "tuna", "chicken", "salmon", "wet food", "turkey", "ham", "sardines")
RARE_KITTYPET_FOOD = "beef stroganoff"
RARE_CHANCE = 0.03

_OWNER = r"(?<![A-Za-z])(?P<abbr>[a-z]_[a-z](?::?\d+)?)"
_PATTERNS = (
    re.compile(_OWNER + r"'s (?P<least>least )?favou?rite prey(?! was)"),
    re.compile(r"\{PRONOUN/" + _OWNER + r"/poss\} (?P<least>least )?favou?rite prey(?! was)"),
    re.compile(r"\b(?P<you>[Yy]our) (?P<least>least )?favou?rite prey(?! was)"),
)


def _biome() -> str:
    if not game.clan:
        return "forest"
    biome = str(game.clan.override_biome or game.clan.biome).lower()
    # the prey lists say "mountain", the Clan says "mountainous"
    return {"mountainous": "mountain"}.get(biome, biome)


def _wild_prey(biome) -> list:
    lists = load_lang_resource("patrols/prey_text_replacements.json")
    found = []
    for key, value in lists.items():
        if key.startswith(biome + "_") and key.endswith("_singular") and isinstance(value, list):
            found.extend(value)
    return list(dict.fromkeys(found))


def _is_kittypet(cat) -> bool:
    from scripts.cat.enums import CatRank

    return cat.status.rank == CatRank.KITTYPET


def _pick(cat, avoid=None) -> str:
    if _is_kittypet(cat):
        if avoid != RARE_KITTYPET_FOOD and random() < RARE_CHANCE:
            return RARE_KITTYPET_FOOD
        pool = [f for f in KITTYPET_FOOD if f != avoid]
    else:
        pool = [p for p in _wild_prey(_biome()) if p != avoid] or [p for p in _wild_prey("forest") if p != avoid]
    return choice(pool) if pool else "mouse"


def favorite(cat) -> str:
    if not getattr(cat, "favorite_prey", None):
        cat.favorite_prey = _pick(cat, avoid=getattr(cat, "disliked_prey", None))
    return cat.favorite_prey


def disliked(cat) -> str:
    if not getattr(cat, "disliked_prey", None):
        cat.disliked_prey = _pick(cat, avoid=favorite(cat))
    return cat.disliked_prey


def _a(word) -> str:
    return ("an " if word[0].lower() in "aeiou" else "a ") + word


def name_in_text(text, cat_dict) -> str:
    """adds the prey after "X's favorite prey": ", a thrush," mid-sentence, ", a thrush" before
    punctuation. Lines about prey in general, or asking what it was, stay as they are"""
    if "prey" not in text or not ("favorite prey" in text or "favourite prey" in text):
        return text
    from scripts.cat.cats import Cat

    def cat_for(abbr):
        entry = cat_dict.get(abbr)
        cat = entry[0] if isinstance(entry, (tuple, list)) and entry else entry
        if isinstance(cat, Cat) or cat is None:
            return cat
        # the text step only has names: find the cat, living ones first
        name = str(cat)
        found = [c for c in Cat.all_cats_list if str(c.name) == name]
        found.sort(key=lambda c: c.dead)
        return found[0] if found else None

    def repl(match):
        groups = match.groupdict()
        cat = cat_for("y_c") if groups.get("you") else cat_for(groups.get("abbr"))
        if cat is None:
            return match.group(0)
        prey = disliked(cat) if groups.get("least") else favorite(cat)
        end = match.end()
        nxt = text[end:end + 1]
        tail = "," if nxt and (nxt.isalnum() or nxt == " ") else ""
        return f"{match.group(0)}, {_a(prey)}{tail}"

    for pattern in _PATTERNS:
        text = pattern.sub(repl, text)
    return text

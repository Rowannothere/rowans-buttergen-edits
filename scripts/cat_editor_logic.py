"""Shared helpers for the cat editor, used by the editor window and the debug console. No UI in here."""

from scripts.cat.cats import Cat
from scripts.game_structure.game.settings import game_setting_get

REL_STATS = ["like", "respect", "trust", "comfort", "romance"]

# name -> (romance, like, respect, trust, comfort)
REL_PRESETS = {
    "rival": (0, -45, 15, -20, -25),
    "enemy": (0, -80, -40, -70, -60),
    "nemesis": (0, -100, -60, -100, -90),
    "friend": (0, 45, 30, 35, 40),
    "bestfriend": (0, 80, 60, 70, 75),
    "crush": (45, 35, 20, 15, 20),
    "lover": (75, 60, 45, 40, 55),
    "soulmate": (100, 100, 90, 90, 100),
    "stranger": (0, 0, 0, 0, 0),
}

FAITH_MODES = ["starclan", "darkforest", "neutral", "flexible", "none"]


def editor_enabled() -> bool:
    """the editor is off unless its turned on in the settings"""
    return bool(game_setting_get("cat_editor"))


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def get_rel_value(cat_from: Cat, cat_to: Cat, stat: str) -> int:
    rel = cat_from.relationships.get(cat_to.ID)
    return getattr(rel, stat) if rel else 0


def set_rel_stat(cat_from: Cat, cat_to: Cat, stat: str, value: int):
    rel = cat_from.create_one_relationship(cat_to)
    if rel is None:
        return
    low = 0 if stat == "romance" else -100
    setattr(rel, stat, clamp(int(value), low, 100))


def nudge_rel_stat(cat_from: Cat, cat_to: Cat, stat: str, amount: int, both: bool = False):
    set_rel_stat(cat_from, cat_to, stat, get_rel_value(cat_from, cat_to, stat) + amount)
    if both:
        set_rel_stat(cat_to, cat_from, stat, get_rel_value(cat_to, cat_from, stat) + amount)


def apply_preset(cat_from: Cat, cat_to: Cat, preset: str, both: bool = False):
    values = dict(zip(["romance", "like", "respect", "trust", "comfort"], REL_PRESETS[preset]))
    for stat, value in values.items():
        set_rel_stat(cat_from, cat_to, stat, value)
        if both:
            set_rel_stat(cat_to, cat_from, stat, value)


def set_faith_mode(cat: Cat, mode: str, number: int = None) -> bool:
    """Set a cat's faith. mode is one of FAITH_MODES, or 'number' together with the number argument.
    Returns False if the mode is unknown."""
    if mode not in FAITH_MODES and mode != "number":
        return False

    if mode == "darkforest":
        # dark forest trainee the normal lifegen way, join_df also finds them a df mentor
        if not cat.joined_df:
            cat.join_df()
        cat.lock_faith = "dark forest"
        cat.no_faith = False
        cat.faith = min(-6, cat.faith)
        return True

    # every other choice takes them out of dark forest training
    if cat.joined_df:
        cat.leave_df()
    cat.no_faith = False

    if mode == "starclan":
        cat.lock_faith = "starclan"
        cat.faith = max(6, cat.faith)
    elif mode == "neutral":
        cat.lock_faith = "neutral"
        cat.faith = clamp(cat.faith, -3, 3)
    elif mode == "flexible":
        cat.lock_faith = "flexible"
    elif mode == "none":
        cat.no_faith = True
        cat.lock_faith = "flexible"
    else:
        cat.lock_faith = "flexible"
        cat.faith = clamp(int(number), -9, 9)
    return True


def nudge_faith(cat: Cat, amount: int):
    """Move raw faith by amount (-9..9) and unlock it so the change actually shows."""
    cat.lock_faith = "flexible"
    cat.no_faith = False
    cat.faith = clamp(round(cat.faith) + amount, -9, 9)


# ------------------------------------------------------------------ stat editor stuff

# (attribute, label, low, high, reset value)
PERSONALITY_FACETS = [
    ("lawfulness", "Lawfulness", 0, 16, 8),
    ("sociability", "Sociability", 0, 16, 8),
    ("aggression", "Aggression", 0, 16, 8),
    ("stability", "Stability", 0, 16, 8),
]

# lifegen stats have no real cap in the game, queen training moves them by 1
LIFEGEN_STATS = [
    ("courage", "Courage", -10, 10, 0),
    ("intelligence", "Intelligence", -10, 10, 0),
    ("empathy", "Empathy", -10, 10, 0),
    ("compassion", "Compassion", -10, 10, 0),
    ("faith", "Faith", -9, 9, 0),
    ("starclan_affinity", "StarClan affinity", -100, 100, 0),
    ("dark_forest_affinity", "Dark Forest affinity", -100, 100, 0),
]

# these come from genes in genemod, adding them by hand wouldnt match how the cat looks
GENETIC_ONLY_CONDITIONS = [
    "manx syndrome", "flat nose", "rabbit gait", "albinism", "ocular albinism",
    "fully hairless", "partially hairless", "bad back", "narrowed chest", "bumpy skin",
]

LIFE_FLAGS = [
    ("no_kits", "No kits"),
    ("no_mates", "No mates"),
    ("no_retire", "No retiring"),
]


def get_stat(cat: Cat, attr: str):
    if attr in ("lawfulness", "sociability", "aggression", "stability"):
        return getattr(cat.personality, attr)
    return getattr(cat, attr)


def set_stat(cat: Cat, attr: str, value: int):
    """sets a facet or lifegen stat, clamped to its range"""
    for table in (PERSONALITY_FACETS, LIFEGEN_STATS):
        for name, _label, low, high, _reset in table:
            if name != attr:
                continue
            value = clamp(int(round(value)), low, high)
            if table is PERSONALITY_FACETS:
                # the setter picks a new trait if this facet doesnt fit the old one anymore
                setattr(cat.personality, attr, value)
            else:
                if attr == "faith":
                    # otherwise the faith lock would hide the change
                    cat.lock_faith = "flexible"
                    cat.no_faith = False
                setattr(cat, attr, value)
            return


def nudge_stat(cat: Cat, attr: str, amount: int):
    set_stat(cat, attr, get_stat(cat, attr) + amount)


def max_stats(cat: Cat, table):
    for name, _label, _low, high, _reset in table:
        if name == "dark_forest_affinity":
            # maxing out means a good cat, not a dark forest one
            set_stat(cat, name, 0)
            continue
        set_stat(cat, name, high)


def reset_stats(cat: Cat, table):
    for name, _label, _low, _high, reset in table:
        set_stat(cat, name, reset)


def all_traits(cat: Cat) -> list:
    from scripts.cat.personality import Personality

    table = Personality.trait_ranges["kit_traits" if cat.personality.kit else "normal_traits"]
    return sorted(table)


def set_trait(cat: Cat, trait: str) -> bool:
    """changes the trait and moves the facets into that trait's range so it sticks"""
    from scripts.cat.personality import Personality

    table = Personality.trait_ranges["kit_traits" if cat.personality.kit else "normal_traits"]
    if trait not in table:
        return False
    ranges = table[trait]
    personality = cat.personality
    # set the private values straight away, going through the setters one at a time
    # would keep picking new traits in between
    personality._law = (ranges["lawfulness"][0] + ranges["lawfulness"][1]) // 2
    personality._social = (ranges["sociability"][0] + ranges["sociability"][1]) // 2
    personality._aggress = (ranges["aggression"][0] + ranges["aggression"][1]) // 2
    personality._stable = (ranges["stability"][0] + ranges["stability"][1]) // 2
    personality.trait = trait
    return True


# ------------------------------------------------------------------ skills

SKILL_SLOTS = [("primary", "Main skill"), ("secondary", "Second skill")]


def skill_options() -> dict:
    """{label: SkillPath} for every skill path, labels like "hunting". Two paths that share a
    label get their path name added."""
    from scripts.cat.skills import Skill, SkillPath

    labels = {path: Skill(path).get_short_skill_string() for path in SkillPath}
    counts = {}
    for label in labels.values():
        counts[label] = counts.get(label, 0) + 1
    options = {}
    for path, label in labels.items():
        if counts[label] > 1:
            label = f"{label} ({path.name.lower()})"
        options[label] = path
    return dict(sorted(options.items()))


def skill_text(cat: Cat, slot: str) -> str:
    import i18n

    skill = getattr(cat.skills, slot)
    if not skill:
        return "none"
    name = i18n.t(f"cat.skills.{skill.skill}")
    if skill.interest_only:
        return f"{name} (just an interest, {skill.points} points)"
    return f"{name} (level {skill.tier}, {skill.points} points)"


def set_skill_path(cat: Cat, slot: str, path) -> None:
    """Changes which skill a slot has. The points stay, a new skill starts at 0"""
    from scripts.cat.skills import Skill

    old = getattr(cat.skills, slot)
    other_slot = "secondary" if slot == "primary" else "primary"
    other = getattr(cat.skills, other_slot)
    if other and other.path == path:
        # the same skill twice would count double, swap the two instead
        setattr(cat.skills, slot, other)
        setattr(cat.skills, other_slot, old)
        return
    if old:
        old.path = path
    else:
        setattr(cat.skills, slot, Skill(path, 0, interest_only=cat.moons < 6))


def nudge_skill_points(cat: Cat, slot: str, amount: int) -> None:
    skill = getattr(cat.skills, slot)
    if skill:
        skill.points += amount


def toggle_skill_interest(cat: Cat, slot: str) -> None:
    """Kits only have interests, grown cats have real levels"""
    skill = getattr(cat.skills, slot)
    if skill:
        skill.interest_only = not skill.interest_only


def remove_second_skill(cat: Cat) -> None:
    # the main skill can only be changed, the game expects every cat to have one
    cat.skills.secondary = None


def hidden_options() -> list:
    from scripts.cat.skills import HiddenSkillEnum

    return ["none"] + [hidden.value for hidden in HiddenSkillEnum]


def set_hidden(cat: Cat, value: str) -> None:
    from scripts.cat.skills import HiddenSkillEnum

    cat.skills.hidden = None if value == "none" else HiddenSkillEnum(value)


def max_skills(cat: Cat) -> None:
    for slot, _label in SKILL_SLOTS:
        skill = getattr(cat.skills, slot)
        if skill:
            skill.interest_only = False
            skill.points = skill.point_range[1]


def reset_skills(cat: Cat) -> None:
    for slot, _label in SKILL_SLOTS:
        skill = getattr(cat.skills, slot)
        if skill:
            skill.points = 0


def condition_options(kind: str) -> list:
    """names that can be given to a cat, kind is injury, illness or permanent"""
    from scripts.cat.cats import ILLNESSES, INJURIES
    import ujson

    if kind == "injury":
        return sorted(INJURIES)
    if kind == "illness":
        return sorted(ILLNESSES)
    with open("resources/dicts/conditions/permanent_conditions.json", "r", encoding="utf-8") as read_file:
        permanent = ujson.loads(read_file.read())
    return sorted(c for c in permanent if c not in GENETIC_ONLY_CONDITIONS)


def give_condition(cat: Cat, kind: str, name: str):
    if cat.dead:
        return
    if kind == "injury":
        cat.get_injured(name, event_triggered=True, lethal=False)
    elif kind == "illness":
        cat.get_ill(name, event_triggered=True, lethal=False)
    else:
        cat.get_permanent_condition(name, born_with=False, event_triggered=True)
    cat.pelt.rebuild_sprite = True


def remove_condition(cat: Cat, kind: str, name: str):
    table = {"injury": cat.injuries, "illness": cat.illnesses, "permanent": cat.permanent_condition}[kind]
    table.pop(name, None)
    if kind == "permanent" and name == "paralyzed":
        cat.pelt.paralyzed = False
    cat.pelt.rebuild_sprite = True


def heal_all(cat: Cat):
    """clears injuries and illnesses, keeps pregnancy and permanent conditions"""
    for name in list(cat.injuries):
        if name != "pregnant":
            cat.injuries.pop(name, None)
    cat.illnesses.clear()
    cat.pelt.rebuild_sprite = True


def clear_permanent(cat: Cat):
    cat.permanent_condition.clear()
    cat.pelt.paralyzed = False
    cat.pelt.rebuild_sprite = True


def unshun(cat: Cat):
    """welcomes a shunned cat back, the same way the clan forgiving them does"""
    if cat.status.is_shunned():
        cat.status.unshun_from_group(cat.status.group_ID)


def set_moons(cat: Cat, moons: int):
    cat.moons = max(0, int(moons))
    cat.pelt.rebuild_sprite = True


def set_rank(cat: Cat, rank) -> None:
    from scripts.cat.enums import CatRank
    from scripts.game_structure import game

    if rank == CatRank.LEADER:
        game.clan.new_leader(cat)
    else:
        cat.rank_change(rank, resort=True)
        if rank == CatRank.DEPUTY:
            game.clan.new_deputy(cat)

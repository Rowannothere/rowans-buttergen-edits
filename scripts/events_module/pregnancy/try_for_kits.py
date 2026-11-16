"""BUTTERGEN: "Try for kits", a button for any cat with a mate. For a few moons the pair is much
likelier to have kits. The usual rules (age, settings, healers, the warrior code) still apply."""

from scripts.game_structure import game

TRY_MOONS = 3
# the kit roll is "1 in chance", so dividing it by 3 makes kits 3 times likelier
FACTOR = 3


def _tries() -> dict:
    if not hasattr(game.clan, "kit_tries") or game.clan.kit_tries is None:
        game.clan.kit_tries = {}
    return game.clan.kit_tries


def moons_left(cat) -> int:
    until = _tries().get(cat.ID)
    return max(0, until - game.clan.age) if until else 0


def can_try(cat) -> bool:
    from scripts.events_module.pregnancy.check_parents import check_if_can_have_kits

    return (
        bool(cat.mate)
        and not cat.dead
        and cat.status.group is not None
        and cat.status.group.is_any_clan_group()
        and moons_left(cat) == 0
        and check_if_can_have_kits(cat)
    )


def start(cat):
    """the cat and every mate they have start trying"""
    from scripts.cat.cats import Cat

    until = game.clan.age + TRY_MOONS
    for cat_id in [cat.ID] + list(cat.mate):
        mate = Cat.fetch_cat(cat_id)
        if mate and not mate.dead:
            _tries()[cat_id] = until


def adjust(chance, cat, second_parent):
    """the kit chance for this pair, 3 times likelier while either of them is trying"""
    if not game.clan or not second_parent:
        return chance
    mates = [p for p in second_parent if p != "Surrogate" and p.ID in cat.mate]
    if mates and (moons_left(cat) or any(moons_left(p) for p in mates)):
        return max(1, int(chance / FACTOR))
    return chance


def reason_texts() -> dict:
    from scripts.game_structure.localization import load_lang_resource

    return load_lang_resource("events/kit_reasons.json")


def _cooldown_text(cat, t) -> str:
    moons = cat.birth_cooldown
    you = game.clan.your_cat if game.clan else None
    text = t["cooldown_you"] if cat is you else t["cooldown"].replace("%{name}", str(cat.name))
    word = t["moon"] if moons == 1 else t["moons"]
    return text.replace("%{moons}", str(moons)).replace("%{moon_word}", word)


def _cat_reason(cat, t) -> str:
    """why the cat itself can't have kits right now, in the order check_if_can_have_kits checks"""
    from scripts.cat.enums import CatAge
    from scripts.events_module.pregnancy.check_parents import check_parent_rank

    if cat.age in (CatAge.NEWBORN, CatAge.KITTEN, CatAge.ADOLESCENT) or cat.moons < 15:
        return t["young"]
    if "pregnant" in cat.temporary_conditions or cat.ID in game.clan.pregnancy_data:
        return t["pregnant"]
    if "recovering_from_birth" in cat.temporary_conditions:
        return t["recovering"]
    if cat.birth_cooldown:
        return _cooldown_text(cat, t)
    if cat.no_kits:
        return t["turned_off"]
    if not check_parent_rank(cat):
        return t["rank"]
    return ""


def _mate_reason(cat, t) -> str:
    """if every living mate had kits too recently, the first one's wait (kits need both parents ready)"""
    from scripts.cat.cats import Cat

    mates = [m for m in (Cat.fetch_cat(i) for i in cat.mate) if m and not m.dead]
    if mates and all(m.birth_cooldown for m in mates):
        return _cooldown_text(mates[0], t)
    return ""


def why_not(cat, have_kits=False) -> str:
    """the hover text for the "try for kits" or "have kits" button: why it's off, or a warning
    when it's on but every mate is still waiting. "" when there's nothing to say."""
    if not game.clan or cat.dead:
        return ""
    t = reason_texts()
    if not have_kits:
        if not cat.mate:
            return t["no_mate"]
        if cat.status.group is None or not cat.status.group.is_any_clan_group():
            return t["away"]
    reason = _cat_reason(cat, t)
    if reason:
        return reason
    if have_kits and not cat.mate:
        from scripts.events_module.pregnancy.check_parents import check_if_can_have_kits

        if not check_if_can_have_kits(cat, allow_unmated=True):
            return t["no_mate"]
    return _mate_reason(cat, t)


def cleanup():
    for cat_id, until in list(_tries().items()):
        if until <= game.clan.age:
            del _tries()[cat_id]

"""Automated 12-moon skip helpers."""

import logging
import random

from scripts.cat.cats import Cat
from scripts.events_module import weekskip
from scripts.events_module.dialogue.dialogue import Dialogue
from scripts.events_module.patrol.enums import PatrolChoice
from scripts.events_module.patrol.patrol import Patrol
from scripts.events_module.text_adjust import event_text_adjust, process_text
from scripts.events_module.timeskip_log import record_activity
from scripts.game_structure import game
from scripts.game_structure.game.switches import (
    Switch,
    switch_get_value,
    switch_set_value,
)

logger = logging.getLogger(__name__)

MOONS_TO_SKIP = 12


def _living_clan_cats(clan):
    return [
        cat
        for cat in Cat.all_cats.values()
        if cat.status.group_ID == clan.group_ID and not cat.dead
    ]


def _send_clan_patrols(clan):
    available = [
        cat
        for cat in _living_clan_cats(clan)
        if cat.status.rank.is_allowed_to_patrol(cat) and cat.can_work()
    ]
    random.shuffle(available)
    patrol_limit = max(1, len(available) // 3)
    patrol_count = random.randint(1, patrol_limit) if available else 0

    for _ in range(patrol_count):
        if not available:
            break
        patrol_size = random.randint(1, min(6, len(available)))
        patrol_cats = random.sample(available, patrol_size)
        available = [cat for cat in available if cat not in patrol_cats]
        patrol_type = (
            "med"
            if any(cat.status.rank.is_any_medicine_rank() for cat in patrol_cats)
            else random.choice(("general", "hunting", "border", "training"))
        )

        patrol = Patrol()
        try:
            intro = patrol.begin_patrol(patrol_cats, patrol_type, clan)
            outcome, results, _, _ = patrol.proceed_patrol(PatrolChoice.PROCEED)
        except RuntimeError:
            logger.warning(
                "Could not generate an automatic patrol for Clan %s",
                clan.name,
                exc_info=True,
            )
            continue

        text = f"{', '.join(str(cat.name) for cat in patrol_cats)}: {intro} | {outcome}"
        if results:
            text += f" | {results}"
        record_activity(
            game.clan,
            clan,
            "Patrols",
            text,
            living_cats=Cat.all_cats.values(),
        )


def _format_dialogue_line(text, dialogue, speaking_cat, clan, other_clan):
    if "|" in text:
        text = text.split("|")[-1]
    processed_cats = {
        abbreviation: (str(cat.name), random.choice(cat.pronouns))
        for abbreviation, cat in dialogue.cat_dict.items()
    }
    processed_cats["y_c"] = (
        str(dialogue.you.name),
        random.choice(dialogue.you.pronouns),
    )
    processed_cats["t_c"] = (
        str(dialogue.cat.name),
        random.choice(dialogue.cat.pronouns),
    )
    text = process_text(text, processed_cats)
    text = event_text_adjust(
        Cat,
        text=text,
        clan=clan,
        other_clan=other_clan,
    )
    return f"{speaking_cat.name}: {text}"


def _talk_with_random_cats():
    protagonist = game.clan.your_cat
    candidates = [
        cat
        for cat in Cat.all_cats.values()
        if cat.status.group_ID == protagonist.status.group_ID
        and cat.ID != protagonist.ID
        and not cat.dead
    ]
    if not candidates:
        return

    for cat in random.sample(candidates, random.randint(1, min(5, len(candidates)))):
        dialogue = Dialogue(cat=cat, you=protagonist)
        dialogue_options = dialogue.load_texts()
        key, selected_dialogue = dialogue.choose_dialogue(dialogue_options, flirt=False)
        dialogue.cat_dict = dialogue.dialogue_cat_dict.get(
            key, {"t_c": cat, "y_c": protagonist}
        )

        scene = "intro"
        transcript = []
        seen_scenes = set()
        while scene in selected_dialogue and scene not in seen_scenes:
            seen_scenes.add(scene)
            scene_lines = selected_dialogue[scene]
            if isinstance(scene_lines, str):
                scene_lines = [scene_lines]
            dialogue_clan = next(
                (
                    clan
                    for clan in [game.clan] + game.clan.all_other_clans
                    if clan.group_ID == cat.status.group_ID
                ),
                game.clan,
            )
            for line in scene_lines:
                speaker = cat
                if "|" in line:
                    speaker_key = line.split("|")[1]
                    speaker = dialogue.cat_dict.get(speaker_key, cat)
                transcript.append(
                    _format_dialogue_line(
                        line,
                        dialogue,
                        speaker,
                        dialogue_clan,
                        next(
                            (
                                clan
                                for clan in [game.clan] + game.clan.all_other_clans
                                if clan.group_ID != dialogue_clan.group_ID
                            ),
                            None,
                        ),
                    )
                )

            dialogue.handle_scene_effects(scene, selected_dialogue, dialogue.cat_dict)
            choices = selected_dialogue.get(f"{scene}_choices", {})
            if not choices:
                break
            selected_choice = random.choice(list(choices.values()))
            scene = selected_choice["next_scene"]

        dialogue_clan = next(
            (
                clan
                for clan in [game.clan] + game.clan.all_other_clans
                if clan.group_ID == cat.status.group_ID
            ),
            game.clan,
        )
        record_activity(
            game.clan,
            dialogue_clan,
            "Dialogue",
            "\n".join(transcript) or f"{cat.name}: (conversation)",
            living_cats=Cat.all_cats.values(),
        )


def _automate_moon():
    game.patrolled.clear()
    for clan in [game.clan] + game.clan.all_other_clans:
        _send_clan_patrols(clan)
    _talk_with_random_cats()


def bulk_timeskip():
    """Advance the current Clan by 12 moons, automating patrols and dialogue."""
    from scripts import events

    starting_age = game.clan.age
    target_age = starting_age + MOONS_TO_SKIP
    previous_patrol_category = switch_get_value(Switch.patrol_category)
    previous_talk_category = switch_get_value(Switch.talk_category)
    switch_set_value(Switch.patrol_category, "clangen")
    switch_set_value(Switch.talk_category, "talk")
    max_skips = MOONS_TO_SKIP * weekskip.WEEKS_IN_MOON
    skips = 0
    try:
        while game.clan.age < target_age and skips < max_skips:
            previous_age = game.clan.age
            events.one_moon()
            skips += 1
            if game.clan.age > previous_age:
                _automate_moon()
    finally:
        switch_set_value(Switch.patrol_category, previous_patrol_category)
        switch_set_value(Switch.talk_category, previous_talk_category)

    if game.clan.age < target_age:
        raise RuntimeError(
            f"Bulk skip stopped at moon {game.clan.age}; expected moon {target_age}"
        )

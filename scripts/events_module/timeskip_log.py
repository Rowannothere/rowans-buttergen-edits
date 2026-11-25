"""Write a readable record of each moon or week skip."""

import html
import re
from pathlib import Path

from scripts.events_module import weekskip
from scripts.housekeeping.datadir import get_save_dir


_SECTIONS = ("Clan Members", "Events", "Patrols", "Dialogue", "Thoughts")


def _clans_for(clan, clan_groups=None):
    if clan_groups is not None:
        return list(clan_groups)
    return [clan] + list(getattr(clan, "all_other_clans", []))


def _period(clan):
    if weekskip.on():
        week = getattr(clan, "weeks", 0)
        if week:
            return clan.age, week
        if clan.age == 0:
            return clan.age, 1
        return clan.age - 1, 4
    return clan.age, None


def get_log_path(clan):
    moon, week = _period(clan)
    log_dir = Path(get_save_dir()) / clan.save_id / "moon_logs"
    if week is not None:
        return log_dir / f"Moon {moon}" / f"Week {week}.txt"
    return log_dir / f"Moon {moon}.txt"


def _clan_marker(clan):
    return f"## Clan: {clan.name} [{clan.group_ID}]"


def _living_member_lines(clan, living_cats):
    members = [
        cat
        for cat in living_cats
        if cat.status.group_ID == clan.group_ID and not cat.dead
    ]
    members.sort(key=lambda cat: str(cat.name).casefold())
    return [
        f"- {cat.name} - {cat.moons} moons - "
        f"{cat.status.rank.name.lower().replace('_', ' ')}"
        for cat in members
    ] or ["- None"]


def _clean_entry(text):
    text = html.unescape(re.sub(r"<[^>]*>", "", str(text)))
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _entry_lines(entries):
    lines = []
    for entry in entries:
        clean_entry = _clean_entry(entry)
        if clean_entry:
            lines.extend(
                f"- {line}" if index == 0 else f"  {line}"
                for index, line in enumerate(clean_entry.split("\n"))
            )
    return lines or ["- None"]


def _new_clan_block(clan, living_cats):
    lines = [
        _clan_marker(clan),
        f"Biome: {getattr(clan, 'biome', 'Unknown')}",
    ]
    for section in _SECTIONS:
        lines.append(f"### {section}")
        lines.extend(
            _living_member_lines(clan, living_cats)
            if section == "Clan Members"
            else ["- None"]
        )
    return lines


def _new_log(clan, clan_groups, living_cats):
    moon, week = _period(clan)
    title = f"# {clan.name} - Moon {moon}"
    if week is not None:
        title += f", Week {week}"
    lines = [
        title,
        f"Season: {getattr(clan, 'current_season', 'Unknown')}",
        f"Biome: {getattr(clan, 'biome', 'Unknown')}",
        "",
    ]
    for group in clan_groups:
        lines.extend(_new_clan_block(group, living_cats))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _clan_block_bounds(lines, clan):
    marker = _clan_marker(clan)
    try:
        start = lines.index(marker)
    except ValueError:
        return None
    end = next(
        (
            index
            for index in range(start + 1, len(lines))
            if lines[index].startswith("## Clan: ")
        ),
        len(lines),
    )
    return start, end


def _replace_section(text, clan, section, entries):
    lines = text.splitlines()
    bounds = _clan_block_bounds(lines, clan)
    if bounds is None:
        raise ValueError(f"Missing log section for Clan {clan.name}")
    clan_start, clan_end = bounds
    section_heading = f"### {section}"
    try:
        section_start = lines.index(section_heading, clan_start + 1, clan_end)
    except ValueError as error:
        raise ValueError(f"Missing {section} section for Clan {clan.name}") from error
    section_end = next(
        (
            index
            for index in range(section_start + 1, clan_end)
            if lines[index].startswith("### ")
        ),
        clan_end,
    )
    lines[section_start + 1 : section_end] = _entry_lines(entries)
    return "\n".join(lines) + "\n"


def _append_section(text, clan, section, entry):
    lines = text.splitlines()
    bounds = _clan_block_bounds(lines, clan)
    if bounds is None:
        raise ValueError(f"Missing log section for Clan {clan.name}")
    clan_start, clan_end = bounds
    section_heading = f"### {section}"
    try:
        section_start = lines.index(section_heading, clan_start + 1, clan_end)
    except ValueError as error:
        raise ValueError(f"Missing {section} section for Clan {clan.name}") from error
    section_end = next(
        (
            index
            for index in range(section_start + 1, clan_end)
            if lines[index].startswith("### ")
        ),
        clan_end,
    )
    if lines[section_start + 1 : section_end] == ["- None"]:
        lines[section_start + 1 : section_end] = _entry_lines([entry])
    else:
        lines[section_end:section_end] = _entry_lines([entry])
    return "\n".join(lines) + "\n"


def _ensure_log(clan, clan_groups, living_cats):
    path = get_log_path(clan)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(_new_log(clan, clan_groups, living_cats), encoding="utf-8")
        return path

    text = path.read_text(encoding="utf-8")
    for group in clan_groups:
        if _clan_block_bounds(text.splitlines(), group) is None:
            text = (
                text.rstrip()
                + "\n\n"
                + "\n".join(_new_clan_block(group, living_cats))
                + "\n"
            )
    path.write_text(text, encoding="utf-8")
    return path


def record_timeskip(clan, clan_groups, living_cats, events):
    """Write the event and thought snapshot for a completed timeskip."""
    groups = list(clan_groups)
    cats = list(living_cats)
    path = _ensure_log(clan, groups, cats)
    text = path.read_text(encoding="utf-8")

    for group in groups:
        group_events = []
        group_thoughts = []
        for event in events:
            event_clan = event.clan
            event_group_id = getattr(event_clan, "group_ID", event_clan)
            if event_group_id is None:
                event_group_id = clan.group_ID
            if event_group_id == group.group_ID and event.text:
                group_events.append(event.text)
        for cat in cats:
            if cat.status.group_ID == group.group_ID and not cat.dead and cat.thought:
                group_thoughts.append(f"{cat.name} thinks: {cat.thought}")

        text = _replace_section(
            text, group, "Clan Members", _living_member_lines(group, cats)
        )
        text = _replace_section(text, group, "Events", group_events)
        text = _replace_section(text, group, "Thoughts", group_thoughts)

    path.write_text(text, encoding="utf-8")


def record_activity(
    clan, activity_clan, section, entry, clan_groups=None, living_cats=None
):
    """Append a patrol or dialogue entry to the current period's Clan section."""
    if section not in ("Patrols", "Dialogue"):
        raise ValueError(f"Unsupported activity section: {section}")
    groups = _clans_for(clan, clan_groups)
    if not any(group.group_ID == activity_clan.group_ID for group in groups):
        groups.append(activity_clan)
    if living_cats is None:
        from scripts.cat.cats import Cat

        living_cats = Cat.all_cats.values()
    path = _ensure_log(clan, groups, list(living_cats))
    text = path.read_text(encoding="utf-8")
    text = _append_section(text, activity_clan, section, entry)
    path.write_text(text, encoding="utf-8")

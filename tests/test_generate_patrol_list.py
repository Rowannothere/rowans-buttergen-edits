from types import SimpleNamespace
from unittest.mock import call, patch

import pytest

from scripts.events_module.patrol import generate_patrol_list


def test_clangen_neutral_patrol_does_not_load_lifegen_clangen_file():
    clan = SimpleNamespace(
        biome="Forest",
        override_biome=None,
        current_season="Newleaf",
    )
    with (
        patch.object(generate_patrol_list.game, "clan", clan),
        patch.object(
            generate_patrol_list, "switch_get_value", return_value="clangen"
        ),
        patch.object(generate_patrol_list, "get_config", return_value=False),
        patch.object(
            generate_patrol_list, "_get_all_patrols_of_type", return_value=[]
        ) as load_standard_patrols,
        patch.object(generate_patrol_list, "_load_file", return_value=[]) as load_file,
    ):
        assert generate_patrol_list.get_patrol_list(
            "hunting", other_clan_rep="neutral"
        ) == []

    load_standard_patrols.assert_called_once_with(
        "hunting", "forest", "patrols/", "newleaf"
    )
    load_file.assert_called_once_with("patrols/other_clan.json")
    assert call("patrols/lifegen/clangen.json") not in load_file.call_args_list


def test_lifegen_patrol_files_load_even_with_non_neutral_clan_relations():
    clan = SimpleNamespace(
        your_cat=SimpleNamespace(
            status=SimpleNamespace(rank="warrior"),
        )
    )
    with (
        patch.object(generate_patrol_list.game, "clan", clan),
        patch.object(
            generate_patrol_list, "switch_get_value", return_value="lifegen"
        ),
        patch.object(generate_patrol_list, "get_config", return_value=False),
        patch.object(
            generate_patrol_list, "get_clan_setting", return_value=False
        ),
        patch.object(generate_patrol_list, "_load_file", return_value=[]) as load_file,
    ):
        assert generate_patrol_list.get_patrol_list(
            "hunting", other_clan_rep="hostile"
        ) == []

    assert load_file.call_args_list == [
        call("patrols/lifegen/warrior.json"),
        call("patrols/lifegen/general.json"),
        call("patrols/other_clan.json"),
        call("patrols/other_clan_hostile.json"),
    ]


def test_patrol_category_without_other_clan_does_not_load_clan_events():
    clan = SimpleNamespace(
        biome="Forest",
        override_biome=None,
        current_season="Newleaf",
    )
    with (
        patch.object(generate_patrol_list.game, "clan", clan),
        patch.object(
            generate_patrol_list, "switch_get_value", return_value="clangen"
        ),
        patch.object(generate_patrol_list, "get_config", return_value=False),
        patch.object(
            generate_patrol_list, "_get_all_patrols_of_type", return_value=[]
        ),
        patch.object(generate_patrol_list, "_load_file", return_value=[]) as load_file,
    ):
        assert generate_patrol_list.get_patrol_list(
            "hunting", other_clan_rep=None
        ) == []

    load_file.assert_not_called()


def test_missing_patrol_file_is_not_cached_as_an_empty_list(monkeypatch):
    path = "patrols/missing_test_file.json"
    monkeypatch.delitem(generate_patrol_list.loaded_events, path, raising=False)
    load_resource = patch.object(
        generate_patrol_list,
        "load_lang_resource",
        side_effect=[FileNotFoundError(path), []],
    )
    with load_resource:
        with pytest.raises(FileNotFoundError, match=path):
            generate_patrol_list._load_file(path)

        assert path not in generate_patrol_list.loaded_events
        try:
            assert generate_patrol_list._load_file(path) == []
        finally:
            generate_patrol_list.loaded_events.pop(path, None)

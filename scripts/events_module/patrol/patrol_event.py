#!/usr/bin/env python3
# -*- coding: ascii -*-
from dataclasses import dataclass, field
from typing import Union, Literal, Optional

from scripts.cat.personality import Personality
from scripts.cat.skills import SkillPath
from scripts.game_structure.constants import HERBS
from scripts.events_module.parameter_dicts import (
    InvolvedCatDict,
    RelationshipConstraintDict,
)
from scripts.events_module.text_pool_event.text_pool_event import TextPoolEvent
from scripts.events_module.patrol.patrol_option import PatrolOption
from scripts.game_structure import constants

NUM_OF_TRAITS = len(Personality.trait_ranges["normal_traits"].keys()) + len(
    Personality.trait_ranges["kit_traits"].keys()
)
NUM_OF_SKILLS = len(SkillPath)


# slots increases performance and can be used since we won't be adding new attrs at runtime
@dataclass(slots=True)
class PatrolEvent:
    event_id: str

    intro_strings: list[str]
    decline_strings: list[str]
    success_outcomes: list[Union[dict, TextPoolEvent]] = field(default_factory=list)
    fail_outcomes: list[Union[dict, TextPoolEvent]] = field(default_factory=list)
    antag_success_outcomes: list[Union[dict, TextPoolEvent]] = field(
        default_factory=list
    )
    antag_fail_outcomes: list[Union[dict, TextPoolEvent]] = field(default_factory=list)
    options: list[Union[dict, PatrolOption]] = field(default_factory=list)

    types: list[
        Literal["hunting", "herb_gathering", "border", "training", "lifegen", "df", "date"]
    ] = "border"
    frequency: int = 4
    weight: int = 1  # will be increased via code
    chance_of_success: int = 0  # out of 100
    location: list[str] = field(default_factory=list)
    season: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    poi: Optional[dict[str, list]] = field(default_factory=dict)
    required_cat_types: dict[str, list[int]] = field(default_factory=dict)
    involved_cats: dict[str, InvolvedCatDict | dict] = field(default_factory=dict)
    relationship_constraint: list[RelationshipConstraintDict] = field(
        default_factory=list[RelationshipConstraintDict]
    )
    patrol_temperament: list[str] = field(default_factory=list)
    other_clan_temperament: list[str] = field(default_factory=list)

    herbs_given: list = field(default_factory=list)
    new_cat: bool = False
    other_clan: bool = False
    other_clan_filter: dict[str, list[str]] = field(default_factory=dict)

    # art
    patrol_art: Optional[str] = None
    patrol_art_clean: Optional[str] = None

    # LG
    random_cats: dict[str, dict] = field(default_factory=dict)
    """Constraints for the randomly chosen r_c:X cats of LifeGen patrols"""
    relationships: list[dict] = field(default_factory=list)
    """Relationship constraints between the randomly chosen LifeGen cats"""
    lifegen_outcomes: dict[str, dict] = field(default_factory=dict)
    """LifeGen-only consequences (murder, accessory, convert, faith_effects), keyed by outcome event_id"""
    # ---

    def __post_init__(self):
        self.weight = 1

        if self.location and "any" not in self.location:
            # add 4 for every biome not listed
            self.weight += 2 * (len(constants.BIOME_TYPES) - len(self.location))

        if self.season and "any" not in self.season:
            # add 4 for every season not listed
            self.weight += 2 * (len(constants.SEASONS) - len(self.season))

        if self.tags:
            self.weight += len(self.tags) * 2

        # add 8, 6, 4 or 2 if there are between 1-4 specific named locations
        # todo: check for balancing
        if self.poi.get("name") and not 1 > len(self.poi["name"]) > 5:
            self.weight += 8 - 2 * len(self.poi["name"])
        elif self.poi.get("tags"):
            # add 4-1 depending on how many specific points of interest are included
            # but only if specific ones are not already requested
            self.weight += min(4, len(self.poi.get("tags", [])))

        self.weight += TextPoolEvent.involved_cat_weight(self.involved_cats)

        # - 1 is for the patrol_cats that they all have
        self.weight += (len(self.required_cat_types.keys()) - 1) * 2

        # LOTS of weight on rel constraints
        self.weight += len(self.relationship_constraint) * 20

        self.weight = max(1, self.weight)

        self._generate_outcomes()

        self.options = [
            option if isinstance(option, PatrolOption) else PatrolOption(**option)
            for option in self.options
        ]
        self._assign_option_ids()

        self.new_cat = self._get_new_cat()
        self.other_clan = self._get_other_clan()
        self.herbs_given = self._get_herbs_given()

    def __eq__(self, other):
        return other == self.event_id

    def _get_new_cat(self) -> bool:
        """Returns boolean if there are any outcomes that results in
        a new cat joining (not just meeting)"""

        for outcome in (
            self.success_outcomes
            + self.fail_outcomes
            + self.antag_fail_outcomes
            + self.antag_success_outcomes
        ):
            if outcome.join or self._options_have(outcome, "join"):
                return True

        return False

    def _get_other_clan(self) -> bool:
        """Return boolean indicating if any outcome has any reputation effect"""
        for outcome in (
            self.success_outcomes
            + self.fail_outcomes
            + self.antag_fail_outcomes
            + self.antag_success_outcomes
        ):
            if outcome.reputation_changes.get("other_clan") or self._options_have(
                outcome, "other_clan"
            ):
                return True

        return False

    def _get_herbs_given(self) -> list:
        """
        returns list of herbs available to get from this patrol
        """
        herb_list = []
        for out in (
            self.success_outcomes
            + self.fail_outcomes
            + self.antag_fail_outcomes
            + self.antag_success_outcomes
        ):
            for supply_change in out.supply:
                if supply_change["type"] == "freshkill":
                    continue
                if supply_change["type"] in herb_list:
                    continue
                herb_list.append(supply_change["type"])
            for herb in self._get_herbs_from_options(out.options):
                if herb not in herb_list:
                    herb_list.append(herb)

        return herb_list

    @staticmethod
    def _options_have(outcome: TextPoolEvent, attribute: str) -> bool:
        for option in outcome.options:
            for child in option.success_outcomes + option.fail_outcomes:
                if attribute == "join" and child.join:
                    return True
                if attribute == "other_clan" and child.reputation_changes.get(
                    "other_clan"
                ):
                    return True
                if PatrolEvent._options_have(child, attribute):
                    return True
        return False

    @staticmethod
    def _get_herbs_from_options(options: list[PatrolOption]) -> list:
        herbs = []
        for option in options:
            for outcome in option.success_outcomes + option.fail_outcomes:
                for supply_change in outcome.supply:
                    if supply_change["type"] != "freshkill" and supply_change[
                        "type"
                    ] not in herbs:
                        herbs.append(supply_change["type"])
                for herb in PatrolEvent._get_herbs_from_options(outcome.options):
                    if herb not in herbs:
                        herbs.append(herb)
        return herbs

    def _assign_option_ids(self):
        def assign(options, prefix):
            for option_index, option in enumerate(options):
                option_prefix = f"{prefix}_option{option_index}"
                for outcome_type, outcomes in (
                    ("success", option.success_outcomes),
                    ("fail", option.fail_outcomes),
                ):
                    for outcome_index, outcome in enumerate(outcomes):
                        outcome.event_id = (
                            f"{option_prefix}_{outcome_type}{outcome_index}"
                        )
                        assign(outcome.options, outcome.event_id)

        assign(self.options, self.event_id)

    def _generate_outcomes(self):
        """
        Generates outcome objects for each outcome in the patrol
        """
        success = self.success_outcomes.copy()
        fail = self.fail_outcomes.copy()
        antag_success = self.antag_success_outcomes.copy()
        antag_fail = self.antag_fail_outcomes.copy()

        # clear old dicts so we can replace them
        self.success_outcomes.clear()
        self.fail_outcomes.clear()
        self.antag_success_outcomes.clear()
        self.antag_fail_outcomes.clear()

        for outcome in success:
            event_id = f"{self.event_id}_success{success.index(outcome)}"
            self.success_outcomes.append(
                TextPoolEvent(event_id=event_id, **self._pop_lifegen_info(event_id, outcome))
            )
        for outcome in fail:
            event_id = f"{self.event_id}_fail{fail.index(outcome)}"
            self.fail_outcomes.append(
                TextPoolEvent(event_id=event_id, **self._pop_lifegen_info(event_id, outcome))
            )
        for outcome in antag_success:
            event_id = f"{self.event_id}_antag_success{antag_success.index(outcome)}"
            self.antag_success_outcomes.append(
                TextPoolEvent(event_id=event_id, **self._pop_lifegen_info(event_id, outcome))
            )
        for outcome in antag_fail:
            event_id = f"{self.event_id}_antag_fail{antag_fail.index(outcome)}"
            self.antag_fail_outcomes.append(
                TextPoolEvent(event_id=event_id, **self._pop_lifegen_info(event_id, outcome))
            )

    def _pop_lifegen_info(self, event_id: str, outcome: dict) -> dict:
        """
        LG: Strips the LifeGen-only consequences from an outcome dict (TextPoolEvent doesn't know them)
        and stores them in lifegen_outcomes under the outcome's event_id
        """
        outcome = outcome.copy()
        lifegen_info = {
            key: outcome.pop(key)
            for key in ("murder", "accessory", "faith_effects", "convert")
            if key in outcome
        }
        if lifegen_info:
            self.lifegen_outcomes[event_id] = lifegen_info
        return outcome

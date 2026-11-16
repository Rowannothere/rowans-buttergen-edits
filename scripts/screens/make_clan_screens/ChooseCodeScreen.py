"""BUTTERGEN: the warrior code page while making a Clan. The ticks are kept in clan_info.code_rules
and become the new Clan's settings in save_clan (same rules as the Warrior code tab)."""

import pygame
import pygame_gui

from scripts.game_structure.screen_settings import MANAGER
from scripts.honor import code
from scripts.screens.enums import GameScreen
from scripts.screens.make_clan_screens.MakeClanScreenBase import MakeClanScreenBase
from scripts.ui.elements.checkbox import UICheckbox
from scripts.ui.elements.surface_image_button import UISurfaceImageButton
from scripts.ui.generate_button import ButtonStyles, get_button_dict
from scripts.ui.scale import ui_scale
from scripts.ui.theme import get_text_box_theme

ROW = 33
TOP = 160


class ChooseCodeScreen(MakeClanScreenBase):
    def __init__(self, name="choose_code_screen"):
        super().__init__(name)
        self.checkboxes: dict[str, UICheckbox] = {}

    def screen_switches(self):
        super().screen_switches()
        if not self.clan_info.code_rules:
            self.clan_info.code_rules = code.starting_rules()

        self.elements["previous_step"].enable()
        self.elements["next_step"].enable()

        self.elements["header"] = pygame_gui.elements.UITextBox(
            "screens.make_clan.code_header",
            ui_scale(pygame.Rect((0, 60), (400, -1))),
            object_id=get_text_box_theme("#text_box_40_horizcenter"),
            manager=MANAGER,
            anchors={"centerx": "centerx"},
        )
        self.elements["info"] = pygame_gui.elements.UITextBox(
            "screens.make_clan.code_info",
            ui_scale(pygame.Rect((0, 105), (760, -1))),
            object_id=get_text_box_theme("#text_box_30_horizcenter"),
            manager=MANAGER,
            anchors={"centerx": "centerx"},
        )
        height = ROW * len(code.RULES) + 16
        self.checkboxes = {}
        for n, rule in enumerate(code.RULES):
            y = TOP + n * ROW
            self.elements[f"label_{rule}"] = pygame_gui.elements.UITextBox(
                f"settings.{rule}",
                ui_scale(pygame.Rect((175, y - 2), (510, ROW))),
                object_id=get_text_box_theme("#text_box_30_horizleft_pad_0_8"),
                manager=MANAGER,
                starting_height=2,
            )
            box = UICheckbox(
                position=(125, y),
                tool_tip_text=f"settings.{rule}_tooltip",
                check=self.clan_info.code_rules.get(rule, True),
                manager=MANAGER,
                starting_height=2,
            )
            # disabled text boxes draw dark, like the Clan Settings tab
            self.elements[f"label_{rule}"].disable()
            if rule in code.LATER:
                box.disable()
            self.checkboxes[rule] = box

        self.elements["all"] = UISurfaceImageButton(
            ui_scale(pygame.Rect((215, TOP + height + 2), (180, 30))),
            "screens.make_clan.code_all",
            get_button_dict(ButtonStyles.SQUOVAL, (180, 30)),
            object_id="@buttonstyles_squoval",
            manager=MANAGER,
        )
        self.elements["reset"] = UISurfaceImageButton(
            ui_scale(pygame.Rect((405, TOP + height + 2), (180, 30))),
            "screens.make_clan.code_reset",
            get_button_dict(ButtonStyles.SQUOVAL, (180, 30)),
            object_id="@buttonstyles_squoval",
            manager=MANAGER,
        )

    def _set_all(self, rules: dict):
        for rule, box in self.checkboxes.items():
            if rule in code.LATER:
                continue
            self.clan_info.code_rules[rule] = rules[rule]
            if rules[rule]:
                box.check()
            else:
                box.uncheck()

    def handle_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            for rule, box in self.checkboxes.items():
                if event.ui_element == box:
                    followed = not self.clan_info.code_rules.get(rule, True)
                    self.clan_info.code_rules[rule] = followed
                    if followed:
                        box.check()
                    else:
                        box.uncheck()
                    return super().handle_event(event)
            if event.ui_element == self.elements["all"]:
                self._set_all({rule: True for rule in code.RULES})
            elif event.ui_element == self.elements["reset"]:
                self._set_all(code.starting_rules())
            elif event.ui_element == self.elements["previous_step"]:
                if self.clan_info.game_mode == "cruel_season":
                    self.change_screen(GameScreen.MAKE_CLAN_CHOOSE_CARDS)
                else:
                    self.change_screen(GameScreen.MAKE_CLAN_CHOOSE_MODE)
            elif event.ui_element == self.elements["next_step"]:
                self.change_screen(GameScreen.MAKE_CLAN_CHOOSE_NAME)
        return super().handle_event(event)

    def exit_screen(self):
        for box in self.checkboxes.values():
            box.kill()
        self.checkboxes = {}
        return super().exit_screen()

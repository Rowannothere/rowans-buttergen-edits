"""BUTTERGEN: the cat maker's breed presets. A list of Genemod's breeds (scripts/cat/breed_functions.py),
grouped the way the game rolls them; picking one makes a random cat of that breed."""

import pygame
import pygame_gui

from scripts.config import get_config
from scripts.ui.elements.modified_scrolling_container import UIModifiedScrollingContainer
from scripts.ui.elements.surface_image_button import UISurfaceImageButton
from scripts.ui.generate_button import get_button_dict, ButtonStyles
from scripts.ui.scale import ui_scale, ui_scale_dimensions
from scripts.ui.windows.window_base_class import GameWindow

WIDTH, HEIGHT = 720, 530
COL_W, BUTTON_W, BUTTON_H, GAP = 225, 215, 28, 32
GROUPS = (("Common", "common_breeds"), ("Uncommon", "medium_breeds"), ("Rare", "rare_breeds"))


def breed_groups() -> list:
    """(heading, sorted breed names) for each group"""
    odds = get_config("genetics_config")
    return [(title, sorted(odds[key], key=str.lower)) for title, key in GROUPS]


class BreedPresetWindow(GameWindow):
    def __init__(self, on_pick):
        self.on_pick = on_pick
        super().__init__(ui_scale(pygame.Rect(((800 - WIDTH) // 2, (700 - HEIGHT) // 2), (WIDTH, HEIGHT))))
        self.set_blocking(True)
        self.prompt = pygame_gui.elements.UITextBox(
            "Pick a breed. Picking it again makes another cat of that breed.",
            ui_scale(pygame.Rect((20, 10), (WIDTH - 40, 40))),
            object_id="#text_box_30_horizcenter",
            container=self,
        )
        groups = breed_groups()
        rows = max(len(names) for _title, names in groups)
        self.scroll = UIModifiedScrollingContainer(
            ui_scale(pygame.Rect((10, 55), (WIDTH - 30, HEIGHT - 135))),
            allow_scroll_x=False,
            allow_scroll_y=True,
            container=self,
        )
        self.scroll.set_scrollable_area_dimensions(ui_scale_dimensions((COL_W * 3, 40 + rows * GAP)))
        self.buttons = {}
        self.headings = []
        for col, (title, names) in enumerate(groups):
            x = 5 + col * COL_W
            self.headings.append(pygame_gui.elements.UITextBox(
                title,
                ui_scale(pygame.Rect((x, 0), (BUTTON_W, 34))),
                object_id="#text_box_30_horizcenter",
                container=self.scroll,
            ))
            for row, name in enumerate(names):
                self.buttons[name] = UISurfaceImageButton(
                    ui_scale(pygame.Rect((x, 36 + row * GAP), (BUTTON_W, BUTTON_H))),
                    name,
                    get_button_dict(ButtonStyles.SQUOVAL, (BUTTON_W, BUTTON_H)),
                    object_id="@buttonstyles_squoval",
                    container=self.scroll,
                )
        close_w = 200
        self.close = UISurfaceImageButton(
            ui_scale(pygame.Rect(((WIDTH - close_w) // 2, HEIGHT - 72), (close_w, 30))),
            "Never mind",
            get_button_dict(ButtonStyles.SQUOVAL, (close_w, 30)),
            object_id="@buttonstyles_squoval",
            container=self,
        )

    def process_event(self, event):
        handled = super().process_event(event)
        if event.type != pygame_gui.UI_BUTTON_START_PRESS:
            return handled
        if event.ui_element == self.close:
            self.kill()
            return True
        for name, button in self.buttons.items():
            if event.ui_element == button:
                self.kill()
                self.on_pick(name)
                return True
        return handled

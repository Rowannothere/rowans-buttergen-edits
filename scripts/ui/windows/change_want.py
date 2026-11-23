"""BUTTERGEN: the player picks what their cat wants most (scripts/feelings.py)."""

import pygame
import pygame_gui

from scripts import feelings
from scripts.ui.elements.surface_image_button import UISurfaceImageButton
from scripts.ui.generate_button import get_button_dict, ButtonStyles
from scripts.ui.scale import ui_scale
from scripts.ui.windows.window_base_class import GameWindow

WIDTH, BUTTON_W, BUTTON_H, GAP = 520, 440, 30, 36


class ChangeWantWindow(GameWindow):
    def __init__(self, cat, on_done=None):
        self.cat = cat
        self.on_done = on_done
        t = feelings.texts()["change_want"]
        current = feelings.want_of(cat)
        seen, self.options = set(), []
        for kind, target, _weight in feelings.fitting_wants(cat):
            if kind in seen or (current and current["kind"] == kind):
                continue
            seen.add(kind)
            want = {"kind": kind, "cat": target.ID if target else None}
            self.options.append((kind, want["cat"], feelings.want_text(cat, want)))
        height = 110 + GAP * (len(self.options) + 1)
        super().__init__(ui_scale(pygame.Rect(((800 - WIDTH) // 2, (700 - height) // 2), (WIDTH, height))))
        self.set_blocking(True)
        self.prompt = pygame_gui.elements.UITextBox(
            feelings._render(t["prompt"], cat),
            ui_scale(pygame.Rect((20, 15), (WIDTH - 40, 70))),
            object_id="#text_box_30_horizcenter",
            container=self,
        )
        self.buttons = {}
        y = 85
        for kind, target_id, label in self.options:
            self.buttons[(kind, target_id)] = UISurfaceImageButton(
                ui_scale(pygame.Rect(((WIDTH - BUTTON_W) // 2, y), (BUTTON_W, BUTTON_H))),
                label[0].upper() + label[1:],
                get_button_dict(ButtonStyles.SQUOVAL, (BUTTON_W, BUTTON_H)),
                object_id="@buttonstyles_squoval",
                container=self,
            )
            y += GAP
        cancel_w = 200
        self.cancel = UISurfaceImageButton(
            ui_scale(pygame.Rect(((WIDTH - cancel_w) // 2, y + 4), (cancel_w, BUTTON_H))),
            t["cancel"],
            get_button_dict(ButtonStyles.SQUOVAL, (cancel_w, BUTTON_H)),
            object_id="@buttonstyles_squoval",
            container=self,
        )

    def process_event(self, event):
        handled = super().process_event(event)
        if event.type != pygame_gui.UI_BUTTON_START_PRESS:
            return handled
        if event.ui_element == self.cancel:
            self.kill()
            return True
        for (kind, target_id), button in self.buttons.items():
            if event.ui_element == button:
                feelings.change_want(self.cat, kind, target_id)
                self.kill()
                if self.on_done:
                    self.on_done()
                return True
        return handled

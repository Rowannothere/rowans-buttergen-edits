"""Buttergen: the update window of the Windows exe, which updates the game with one button
(run.bat players get BGUpdateWindow)."""
import pygame
import pygame_gui

from scripts.game_structure.screen_settings import MANAGER
from scripts.housekeeping import bg_update, exe_update
from scripts.housekeeping.datadir import open_url
from scripts.housekeeping.game_version import get_version_info
from scripts.housekeeping.quit_game import quit_game
from scripts.ui.elements.surface_image_button import UISurfaceImageButton
from scripts.ui.generate_button import get_button_dict, ButtonStyles
from scripts.ui.scale import ui_scale
from scripts.ui.windows.window_base_class import GameWindow

FAILED_TEXT = ("The update didn't work, and nothing was changed. You can try again, or get it from "
               "the download page.")
LOCKED_TEXT = ("Windows won't let the game change its own folder. Move the Buttergen folder somewhere "
               "else, like your Documents, and try again.")


class BGExeUpdateWindow(GameWindow):
    def __init__(self, failed=False):
        super().__init__(ui_scale(pygame.Rect((150, 220), (500, 250))), click_outside_to_close=False)
        self.updater = None
        self.restarting = 0
        self.buttons = {}
        self.shown = None

        channel = "dev build " if bg_update.update_channel() == "dev" else ""
        title = f"Buttergen {channel}{bg_update.newer_version} is out!" if bg_update.newer_version else "Buttergen"
        pygame_gui.elements.UITextBox(
            title,
            ui_scale(pygame.Rect((0, 10), (500, -1))),
            object_id="#changelog_popup_title",
            container=self,
            manager=MANAGER,
        )
        self.text = pygame_gui.elements.UITextBox(
            "",
            ui_scale(pygame.Rect((15, 65), (470, 120))),
            object_id="#text_box_30",
            container=self,
            manager=MANAGER,
        )
        if failed:
            self.show_failed(FAILED_TEXT)
        else:
            self.set_page(
                f"You're playing {get_version_info().version_number}. The update downloads and the game "
                "restarts. Your Clans are kept somewhere else, so they're safe.",
                ("update now", "later"),
            )

    def set_page(self, text, buttons):
        if self.shown != text:
            self.text.set_text(text)
            self.shown = text
        if list(self.buttons) == list(buttons):
            return
        for button in self.buttons.values():
            button.kill()
        width, gap = 145, 10
        left = (500 - len(buttons) * width - (len(buttons) - 1) * gap) // 2
        self.buttons = {
            label: UISurfaceImageButton(
                ui_scale(pygame.Rect((left + i * (width + gap), 195), (width, 30))),
                label,
                get_button_dict(ButtonStyles.SQUOVAL, (width, 30)),
                object_id="@buttonstyles_squoval",
                container=self,
                manager=MANAGER,
            )
            for i, label in enumerate(buttons)
        }

    def show_failed(self, text):
        self.updater = None
        self.set_page(text, ("try again", "download page", "later"))

    def start(self):
        if not bg_update.build:
            # the check hasn't found the build this time
            self.show_failed(FAILED_TEXT)
            return
        self.updater = exe_update.Updater(
            bg_update.build, bg_update.update_channel(), get_version_info().version_number
        )
        self.set_page("Downloading... 0%", ("cancel",))
        self.updater.start()

    def update(self, time_delta):
        super().update(time_delta)
        if not self.alive() or self.updater is None:
            return
        stage = self.updater.stage
        if stage == exe_update.DOWNLOADING:
            self.set_page(f"Downloading... {self.updater.percent}%", ("cancel",))
        elif stage == exe_update.CHECKING:
            self.set_page("Checking the download...", ("cancel",))
        elif stage == exe_update.LOCKED:
            self.show_failed(LOCKED_TEXT)
        elif stage == exe_update.FAILED:
            self.show_failed(FAILED_TEXT)
        elif stage == exe_update.READY:
            self.set_page("Restarting to finish the update...", ())
            self.restarting += time_delta
            # long enough to read
            if self.restarting < 1.5:
                return
            try:
                self.updater.start_finishing()
            except OSError as error:
                print(f"Update failed: {error!r}")
                self.show_failed(FAILED_TEXT)
                return
            quit_game(savesettings=True)

    def process_event(self, event):
        if event.type == pygame_gui.UI_BUTTON_START_PRESS:
            label = next((l for l, b in self.buttons.items() if b == event.ui_element), None)
            if label in ("update now", "try again"):
                self.start()
                return True
            if label == "download page":
                open_url(bg_update.download_page())
                self.kill()
                return True
            if label in ("later", "cancel"):
                self.kill()
                return True
        return super().process_event(event)

    def kill(self):
        if getattr(self, "updater", None):
            self.updater.cancel()
        super().kill()

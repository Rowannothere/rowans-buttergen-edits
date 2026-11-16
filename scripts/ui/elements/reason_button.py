"""BUTTERGEN: a button that still shows its hover text while it's disabled, so it can say why it's off"""

from pygame_gui.core import UIElement

from scripts.ui.elements.surface_image_button import UISurfaceImageButton


class UIReasonButton(UISurfaceImageButton):
    def can_hover(self) -> bool:
        if self.is_enabled:
            return super().can_hover()
        return self.tool_tip_text is not None and not self.held

    def on_hovered(self):
        if self.is_enabled:
            super().on_hovered()
        else:
            # only the hover timer for the tooltip, the button keeps its disabled look
            UIElement.on_hovered(self)

    def on_unhovered(self):
        if self.is_enabled:
            super().on_unhovered()
        else:
            UIElement.on_unhovered(self)

"""Screen implementation for SettingsScreen."""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivymd.uix.button import MDRaisedButton, MDIconButton
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField


class SettingsScreen(MDScreen):
    """Application settings screen."""

    def on_pre_enter(self, *args: object) -> None:
        """Create widgets lazily so Kivy properties are ready."""
        if self.children:
            return
        layout = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))
        layout.add_widget(MDLabel(text="Settings", halign="center", font_style="H4", size_hint_y=None, height=dp(72)))
        layout.add_widget(MDLabel(text="Dark mode enabled", halign="center"))
        layout.add_widget(MDRaisedButton(text="Back", pos_hint={"center_x": 0.5}, on_release=lambda *_: setattr(self.manager, "current", "profile")))
        self.add_widget(layout)

"""Screen implementation for SettingsScreen."""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivymd.uix.screen import MDScreen


class SettingsScreen(MDScreen):
    """Application settings screen."""

    def on_pre_enter(self, *args: object) -> None:
        """Create widgets lazily so Kivy properties are ready."""
        if self.children:
            return
        layout = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))
        layout.add_widget(Label(text="Settings", font_size=dp(28), size_hint_y=None, height=dp(72)))
        layout.add_widget(Label(text="Dark mode enabled", size_hint_y=None, height=dp(48)))
        layout.add_widget(Button(text="Back", size_hint_y=None, height=dp(48), on_release=lambda *_: setattr(self.manager, "current", "profile")))
        self.add_widget(layout)

"""Screen implementation for LoginScreen."""

from __future__ import annotations

from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivymd.app import MDApp
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField

from client.screens.async_helpers import run_in_thread


class LoginScreen(MDScreen):
    """Login and forgot password screen."""

    def on_pre_enter(self, *args: object) -> None:
        """Create widgets lazily so Kivy properties are ready."""
        if self.children:
            return
        layout = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))
        layout.add_widget(MDLabel(text="Login", halign="center", font_style="H4", size_hint_y=None, height=dp(72)))
        self.username = MDTextField(hint_text="Username", mode="rectangle")
        self.password = MDTextField(hint_text="Password", password=True, mode="rectangle")
        self.status = MDLabel(text="", halign="center", theme_text_color="Secondary")
        layout.add_widget(self.username)
        layout.add_widget(self.password)
        layout.add_widget(MDRaisedButton(text="Login", pos_hint={"center_x": 0.5}, on_release=lambda *_: self.login()))
        layout.add_widget(MDRaisedButton(text="Create account", pos_hint={"center_x": 0.5}, on_release=lambda *_: setattr(self.manager, "current", "register")))
        layout.add_widget(self.status)
        self.add_widget(layout)

    def login(self) -> None:
        """Authenticate with the server and enter the chat list."""
        username = self.username.text.strip()
        password = self.password.text
        self.status.text = "Signing in..."
        app = MDApp.get_running_app()
        run_in_thread(
            lambda: app.auth.login(username, password),
            self._login_success,
            self._login_error,
        )

    def _login_success(self, _result: dict[str, Any]) -> None:
        """Handle successful login."""
        app = MDApp.get_running_app()
        app.start_realtime()
        self.status.text = "Signed in"
        self.manager.current = "chat_list"

    def _login_error(self, exc: Exception) -> None:
        """Show a login error."""
        self.status.text = f"Login failed: {exc}"

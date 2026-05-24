"""Screen implementation for LoginScreen."""

from __future__ import annotations

from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen

from client.screens.async_helpers import run_in_thread


class LoginScreen(MDScreen):
    """Login and forgot password screen."""

    def on_pre_enter(self, *args: object) -> None:
        """Create widgets lazily so Kivy properties are ready."""
        if self.children:
            return
        layout = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))
        layout.add_widget(Label(text="Ma:Vi", font_size=dp(32), size_hint_y=None, height=dp(72)))
        self.username = TextInput(hint_text="Username", multiline=False, size_hint_y=None, height=dp(48))
        self.password = TextInput(hint_text="Password", password=True, multiline=False, size_hint_y=None, height=dp(48))
        self.status = Label(text="", size_hint_y=None, height=dp(54))
        layout.add_widget(self.username)
        layout.add_widget(self.password)
        layout.add_widget(Button(text="Login", size_hint_y=None, height=dp(48), on_release=lambda *_: self.login()))
        layout.add_widget(Button(text="Create account", size_hint_y=None, height=dp(48), on_release=lambda *_: setattr(self.manager, "current", "register")))
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

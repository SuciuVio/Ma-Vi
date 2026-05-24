"""Screen implementation for RegisterScreen."""

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
from client.utils.validators import validate_email, validate_password, validate_username


class RegisterScreen(MDScreen):
    """Registration screen with live validation fields."""

    def on_pre_enter(self, *args: object) -> None:
        """Create widgets lazily so Kivy properties are ready."""
        if self.children:
            return
        layout = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))
        layout.add_widget(Label(text="Create account", font_size=dp(28), size_hint_y=None, height=dp(72)))
        self.username = TextInput(hint_text="Username", multiline=False, size_hint_y=None, height=dp(48))
        self.email = TextInput(hint_text="Email", multiline=False, size_hint_y=None, height=dp(48))
        self.password = TextInput(hint_text="Password", password=True, multiline=False, size_hint_y=None, height=dp(48))
        self.confirm = TextInput(hint_text="Confirm password", password=True, multiline=False, size_hint_y=None, height=dp(48))
        self.status = Label(text="", size_hint_y=None, height=dp(60))
        layout.add_widget(self.username)
        layout.add_widget(self.email)
        layout.add_widget(self.password)
        layout.add_widget(self.confirm)
        layout.add_widget(Button(text="Register", size_hint_y=None, height=dp(48), on_release=lambda *_: self.register()))
        layout.add_widget(Button(text="Back to login", size_hint_y=None, height=dp(48), on_release=lambda *_: setattr(self.manager, "current", "login")))
        layout.add_widget(self.status)
        self.add_widget(layout)

    def register(self) -> None:
        """Validate input and create a server account."""
        username = self.username.text.strip()
        email = self.email.text.strip()
        password = self.password.text
        errors = [
            validate_username(username),
            validate_email(email),
            validate_password(password),
            "Passwords do not match" if password != self.confirm.text else None,
        ]
        error = next((item for item in errors if item), None)
        if error:
            self.status.text = error
            return
        self.status.text = "Creating account..."
        app = MDApp.get_running_app()
        run_in_thread(
            lambda: app.auth.register(username, email, password),
            self._register_success,
            self._register_error,
        )

    def _register_success(self, _result: dict[str, Any]) -> None:
        """Return to login after account creation."""
        self.status.text = "Account created. You can sign in."
        self.manager.current = "login"

    def _register_error(self, exc: Exception) -> None:
        """Show registration errors."""
        self.status.text = f"Register failed: {exc}"

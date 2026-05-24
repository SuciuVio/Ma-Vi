"""Screen implementation for SearchUsersScreen."""

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


class SearchUsersScreen(MDScreen):
    """Live user search screen."""

    def on_pre_enter(self, *args: object) -> None:
        """Create widgets lazily so Kivy properties are ready."""
        if self.children:
            return
        layout = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))
        layout.add_widget(Label(text="Search Users", font_size=dp(28), size_hint_y=None, height=dp(72)))
        self.query = TextInput(hint_text="Search users", multiline=False, size_hint_y=None, height=dp(48))
        self.results = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.results.bind(minimum_height=self.results.setter("height"))
        self.status = Label(text="", size_hint_y=None, height=dp(54))
        layout.add_widget(self.query)
        layout.add_widget(Button(text="Search", size_hint_y=None, height=dp(48), on_release=lambda *_: self.search()))
        layout.add_widget(Label(text="Enter a username or email fragment", size_hint_y=None, height=dp(42)))
        layout.add_widget(self.results)
        layout.add_widget(self.status)
        layout.add_widget(Button(text="Back", size_hint_y=None, height=dp(48), on_release=lambda *_: setattr(self.manager, "current", "chat_list")))
        self.add_widget(layout)

    def search(self) -> None:
        """Search users through the server."""
        app = MDApp.get_running_app()
        if not app.auth.token:
            self.status.text = "Sign in first"
            return
        query = self.query.text.strip()
        self.status.text = "Searching..."
        run_in_thread(
            lambda: app.chat.search_users(app.auth.token, query),
            self._search_success,
            self._search_error,
        )

    def _search_success(self, users: list[dict[str, Any]]) -> None:
        """Render search results."""
        self.status.text = "Search complete"
        self.results.clear_widgets()
        if not users:
            self.results.add_widget(Label(text="No users found", size_hint_y=None, height=dp(42)))
            return
        for user in users[:20]:
            row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(48))
            row.add_widget(Label(text=f"{user['username']} ({user['status']})"))
            row.add_widget(Button(text="Chat", size_hint_x=None, width=dp(88), on_release=lambda _button, selected=user: self.start_chat(selected)))
            row.add_widget(Button(text="Add", size_hint_x=None, width=dp(88), on_release=lambda _button, selected=user: self.add_contact(selected)))
            self.results.add_widget(row)

    def _search_error(self, exc: Exception) -> None:
        """Show search errors."""
        self.status.text = f"Search failed: {exc}"

    def start_chat(self, user: dict[str, Any]) -> None:
        """Select a search result and open the chat screen."""
        app = MDApp.get_running_app()
        app.active_chat_user = user
        self.manager.current = "chat"

    def add_contact(self, user: dict[str, Any]) -> None:
        """Save a search result as contact."""
        app = MDApp.get_running_app()
        if not app.auth.token:
            self.status.text = "Sign in first"
            return
        self.status.text = "Adding contact..."
        run_in_thread(
            lambda: app.chat.add_contact(app.auth.token, int(user["id"])),
            lambda _contact: self._contact_added(user),
            self._contact_error,
        )

    def _contact_added(self, user: dict[str, Any]) -> None:
        """Show contact save success."""
        self.status.text = f"{user['username']} added to contacts"

    def _contact_error(self, exc: Exception) -> None:
        """Show contact save errors."""
        self.status.text = f"Add contact failed: {exc}"

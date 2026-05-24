"""Screen implementation for ChatListScreen."""

from __future__ import annotations

from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen

from client.screens.async_helpers import run_in_thread


class ChatListScreen(MDScreen):
    """Conversation list screen."""

    def on_pre_enter(self, *args: object) -> None:
        """Create widgets lazily so Kivy properties are ready."""
        if self.children:
            return
        layout = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))
        layout.add_widget(Label(text="Chats", font_size=dp(28), size_hint_y=None, height=dp(72)))
        self.status = Label(text="Sign in to load conversations", size_hint_y=None, height=dp(54))
        self.conversations = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.conversations.bind(minimum_height=self.conversations.setter("height"))
        layout.add_widget(self.status)
        layout.add_widget(self.conversations)
        layout.add_widget(Button(text="Refresh", size_hint_y=None, height=dp(48), on_release=lambda *_: self.refresh()))
        layout.add_widget(Button(text="Search", size_hint_y=None, height=dp(48), on_release=lambda *_: setattr(self.manager, "current", "search")))
        layout.add_widget(Button(text="Open chat", size_hint_y=None, height=dp(48), on_release=lambda *_: setattr(self.manager, "current", "chat")))
        layout.add_widget(Button(text="Profile", size_hint_y=None, height=dp(48), on_release=lambda *_: setattr(self.manager, "current", "profile")))
        self.add_widget(layout)

    def on_enter(self, *args: object) -> None:
        """Refresh conversations whenever the screen opens."""
        if self.children:
            self.refresh()

    def refresh(self) -> None:
        """Load conversations for the current user."""
        app = MDApp.get_running_app()
        if not app.auth.token:
            self.status.text = "Not signed in"
            return
        self.status.text = "Loading conversations..."
        run_in_thread(
            lambda: app.chat.list_conversations(app.auth.token),
            self._refresh_success,
            self._refresh_error,
        )

    def _refresh_success(self, items: list[dict[str, Any]]) -> None:
        """Render conversation summaries."""
        self.status.text = "Conversations loaded"
        self.conversations.clear_widgets()
        if not items:
            self.conversations.add_widget(Label(text="No conversations yet", size_hint_y=None, height=dp(42)))
            return
        for item in items[:20]:
            row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(54))
            label = f"{item.get('peer_username', 'Unknown')} - {item.get('last_message') or 'No messages yet'}"
            row.add_widget(Label(text=label))
            row.add_widget(Button(text="Open", size_hint_x=None, width=dp(96), on_release=lambda _button, selected=item: self.open_chat(selected)))
            self.conversations.add_widget(row)

    def _refresh_error(self, exc: Exception) -> None:
        """Show refresh errors."""
        self.status.text = f"Could not load conversations: {exc}"

    def open_chat(self, item: dict[str, Any]) -> None:
        """Open the selected conversation in ChatScreen."""
        app = MDApp.get_running_app()
        app.active_chat_user = {
            "id": item["peer_id"],
            "username": item["peer_username"],
            "public_key": item.get("peer_public_key"),
            "status": item.get("peer_status", "offline"),
        }
        self.manager.current = "chat"

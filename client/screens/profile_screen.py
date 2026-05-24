"""Screen implementation for ProfileScreen."""

from __future__ import annotations

from typing import Any

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen

from client.screens.async_helpers import run_in_thread


class ProfileScreen(MDScreen):
    """User profile screen."""

    def on_pre_enter(self, *args: object) -> None:
        """Create widgets lazily so Kivy properties are ready."""
        if self.children:
            return
        layout = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))
        layout.add_widget(Label(text="Profile", font_size=dp(28), size_hint_y=None, height=dp(72)))
        layout.add_widget(Label(text="Avatar placeholder", size_hint_y=None, height=dp(42)))
        self.fingerprint = Label(text="Your safety number is unavailable", size_hint_y=None, height=dp(54))
        self.contacts = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None)
        self.contacts.bind(minimum_height=self.contacts.setter("height"))
        self.status = Label(text="", size_hint_y=None, height=dp(54))
        layout.add_widget(self.fingerprint)
        layout.add_widget(Button(text="Load contacts", size_hint_y=None, height=dp(48), on_release=lambda *_: self.load_contacts()))
        layout.add_widget(self.contacts)
        layout.add_widget(Button(text="Settings", size_hint_y=None, height=dp(48), on_release=lambda *_: setattr(self.manager, "current", "settings")))
        layout.add_widget(Button(text="Logout", size_hint_y=None, height=dp(48), on_release=lambda *_: self.logout()))
        layout.add_widget(Button(text="Back", size_hint_y=None, height=dp(48), on_release=lambda *_: setattr(self.manager, "current", "chat_list")))
        layout.add_widget(self.status)
        self.add_widget(layout)

    def on_enter(self, *args: object) -> None:
        """Load contacts when profile opens."""
        if self.children:
            self.show_fingerprint()
            self.load_contacts()

    def show_fingerprint(self) -> None:
        """Show the local user's safety number when available."""
        app = MDApp.get_running_app()
        record = app.auth.local_key_record()
        if not record:
            self.fingerprint.text = "Your safety number is unavailable"
            return
        self.fingerprint.text = f"Your safety number: {record.get('fingerprint', 'unavailable')}"

    def load_contacts(self) -> None:
        """Fetch saved contacts."""
        app = MDApp.get_running_app()
        if not app.auth.token:
            self.status.text = "Sign in first"
            return
        self.status.text = "Loading contacts..."
        run_in_thread(
            lambda: app.chat.list_contacts(app.auth.token),
            self._contacts_loaded,
            self._contacts_error,
        )

    def _contacts_loaded(self, contacts: list[dict[str, Any]]) -> None:
        """Render saved contacts."""
        self.contacts.clear_widgets()
        self.status.text = "Contacts loaded"
        if not contacts:
            self.contacts.add_widget(Label(text="No contacts yet", size_hint_y=None, height=dp(42)))
            return
        for contact in contacts[:30]:
            row = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(48))
            label = f"{contact['username']} ({contact['status']})"
            if contact.get("favorite"):
                label = f"* {label}"
            row.add_widget(Label(text=label))
            row.add_widget(Button(text="Chat", size_hint_x=None, width=dp(96), on_release=lambda _button, selected=contact: self.open_contact(selected)))
            self.contacts.add_widget(row)

    def _contacts_error(self, exc: Exception) -> None:
        """Show contact loading errors."""
        self.status.text = f"Contacts failed: {exc}"

    def open_contact(self, contact: dict[str, Any]) -> None:
        """Open a contact in ChatScreen."""
        app = MDApp.get_running_app()
        app.active_chat_user = {
            "id": contact["contact_id"],
            "username": contact["username"],
            "public_key": contact.get("public_key"),
            "status": contact.get("status", "offline"),
            "last_seen": contact.get("last_seen", ""),
        }
        self.manager.current = "chat"

    def logout(self) -> None:
        """Clear the saved session and return to login."""
        app = MDApp.get_running_app()
        if app.realtime:
            app.realtime.stop()
            app.realtime = None
        app.auth.logout()
        app.active_chat_user = None
        self.manager.current = "login"

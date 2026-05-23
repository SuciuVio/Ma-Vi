"""KivyMD entry point for Ma:Vi."""

from __future__ import annotations

from typing import Any

from client.managers.auth_manager import AuthManager
from client.managers.audio_manager import AudioManager
from client.managers.chat_manager import ChatManager
from client.managers.file_manager import FileManager
from client.managers.websocket_manager import ClientWebSocketManager
from client.utils.logger import configure_client_logging

try:
    from kivy.uix.screenmanager import FadeTransition, ScreenManager
    from kivymd.app import MDApp
    from client.screens.login_screen import LoginScreen
    from client.screens.register_screen import RegisterScreen
    from client.screens.chat_list_screen import ChatListScreen
    from client.screens.chat_screen import ChatScreen
    from client.screens.search_users_screen import SearchUsersScreen
    from client.screens.profile_screen import ProfileScreen
    from client.screens.settings_screen import SettingsScreen
except ImportError as exc:
    raise SystemExit("Kivy/KivyMD are required to run the Ma:Vi client. Install requirements.txt first.") from exc


class MaviApp(MDApp):
    """Main Android application."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.auth = AuthManager()
        self.audio = AudioManager()
        self.chat = ChatManager()
        self.files = FileManager()
        self.active_chat_user: dict[str, Any] | None = None
        self.realtime: ClientWebSocketManager | None = None

    def start_realtime(self) -> None:
        """Start the authenticated WebSocket listener if possible."""
        if not self.auth.token:
            return
        if self.realtime:
            self.realtime.stop()
        self.realtime = ClientWebSocketManager(self.auth.token)
        self.realtime.start_background()

    def build(self) -> ScreenManager:
        """Build the screen manager and apply the default theme."""
        configure_client_logging()
        self.title = "Ma:Vi"
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Teal"
        manager = ScreenManager(transition=FadeTransition(duration=0.18))
        for screen in (
            LoginScreen(name="login"),
            RegisterScreen(name="register"),
            ChatListScreen(name="chat_list"),
            ChatScreen(name="chat"),
            SearchUsersScreen(name="search"),
            ProfileScreen(name="profile"),
            SettingsScreen(name="settings"),
        ):
            manager.add_widget(screen)
        if self.auth.refresh_token:
            self.auth.refresh_session()
        if self.auth.token:
            self.start_realtime()
            manager.current = "chat_list"
        return manager


if __name__ == "__main__":
    MaviApp().run()

"""Screen implementation for ChatScreen."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivymd.app import MDApp
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel
from kivymd.uix.screen import MDScreen
from kivymd.uix.textfield import MDTextField

from client.screens.async_helpers import run_in_thread
from network.encryption import get_key_fingerprint


class ChatScreen(MDScreen):
    """Realtime chat screen."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._listener_registered = False
        self._last_typing_sent = 0.0

    def on_pre_enter(self, *args: object) -> None:
        """Create widgets lazily so Kivy properties are ready."""
        if self.children:
            return
        layout = BoxLayout(orientation="vertical", spacing=dp(12), padding=dp(18))
        layout.add_widget(MDLabel(text="Chat", halign="center", font_style="H4", size_hint_y=None, height=dp(72)))
        layout.add_widget(MDLabel(text="End-to-end encrypted", halign="center", theme_text_color="Secondary"))
        self.recipient_label = MDLabel(text="No recipient selected", halign="center", theme_text_color="Secondary")
        self.fingerprint_label = MDLabel(text="Safety number unavailable", halign="center", theme_text_color="Secondary")
        self.receiver = MDTextField(hint_text="Receiver user id", mode="rectangle", input_filter="int")
        self.message_list = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None, padding=(0, dp(8), 0, dp(8)))
        self.message_list.bind(minimum_height=self.message_list.setter("height"))
        self.messages = ScrollView(do_scroll_x=False)
        self.messages.add_widget(self.message_list)
        self.empty_label = MDLabel(text="Messages appear here", halign="center", theme_text_color="Secondary", size_hint_y=None, height=dp(48))
        self.message_list.add_widget(self.empty_label)
        self.message = MDTextField(hint_text="Message", mode="rectangle")
        self.message.bind(text=lambda _field, _text: self._send_typing())
        self.file_path = MDTextField(hint_text="File path for transfer offer", mode="rectangle")
        self.transfer_status = MDLabel(text="", halign="center", theme_text_color="Secondary")
        self.active_call_id: int | None = None
        self.status = MDLabel(text="", halign="center", theme_text_color="Secondary")
        layout.add_widget(self.recipient_label)
        layout.add_widget(self.fingerprint_label)
        layout.add_widget(self.receiver)
        layout.add_widget(self.messages)
        layout.add_widget(self.message)
        layout.add_widget(MDRaisedButton(text="Send", pos_hint={"center_x": 0.5}, on_release=lambda *_: self.send()))
        layout.add_widget(MDRaisedButton(text="Voice Call", pos_hint={"center_x": 0.5}, on_release=lambda *_: self.start_call()))
        layout.add_widget(MDRaisedButton(text="End Call", pos_hint={"center_x": 0.5}, on_release=lambda *_: self.end_call()))
        layout.add_widget(MDRaisedButton(text="Mute", pos_hint={"center_x": 0.5}, on_release=lambda *_: self.toggle_mute()))
        layout.add_widget(MDRaisedButton(text="Speaker", pos_hint={"center_x": 0.5}, on_release=lambda *_: self.toggle_speaker()))
        layout.add_widget(self.file_path)
        layout.add_widget(MDRaisedButton(text="Offer File", pos_hint={"center_x": 0.5}, on_release=lambda *_: self.offer_file()))
        layout.add_widget(self.transfer_status)
        layout.add_widget(MDRaisedButton(text="Back", pos_hint={"center_x": 0.5}, on_release=lambda *_: setattr(self.manager, "current", "chat_list")))
        layout.add_widget(self.status)
        self.add_widget(layout)

    def on_enter(self, *args: object) -> None:
        """Populate the selected receiver when opened from search."""
        app = MDApp.get_running_app()
        if app.realtime and not self._listener_registered:
            app.realtime.add_listener(self._on_realtime_payload)
            self._listener_registered = True
        user = app.active_chat_user
        if user:
            self.receiver.text = str(user["id"])
            self.recipient_label.text = f"Chat with {user['username']}"
            self.fingerprint_label.text = self._fingerprint_text(user)
            self.status.text = ""
            self.load_history(int(user["id"]))

    def load_history(self, peer_id: int) -> None:
        """Load existing messages for the selected peer."""
        app = MDApp.get_running_app()
        if not app.auth.token:
            return
        self.status.text = "Loading history..."
        run_in_thread(
            lambda: app.chat.list_messages(app.auth.token, peer_id),
            self._history_success,
            self._history_error,
        )

    def send(self) -> None:
        """Send a message to the selected receiver."""
        app = MDApp.get_running_app()
        if not app.auth.token:
            self.status.text = "Sign in first"
            return
        if not self.receiver.text:
            self.status.text = "Enter receiver user id"
            return
        content = self.message.text.strip()
        if not content:
            self.status.text = "Write a message"
            return
        receiver_id = int(self.receiver.text)
        self.status.text = "Sending..."
        encrypted_payload = self._encrypt_for_active_peer(content)
        content_to_send = encrypted_payload["encrypted"] if encrypted_payload else content
        run_in_thread(
            lambda: app.chat.send_message(app.auth.token, receiver_id, content_to_send, encrypted_payload),
            self._send_success,
            self._send_error,
        )

    def _send_success(self, message: dict[str, Any]) -> None:
        """Render the sent message."""
        self.status.text = "Sent"
        self.message.text = ""
        app = MDApp.get_running_app()
        app.chat.add_message(message)
        self._append_rendered_message("Me", self._display_content(message))

    def _send_error(self, exc: Exception) -> None:
        """Show send errors."""
        self.status.text = f"Send failed: {exc}"

    def offer_file(self) -> None:
        """Create a file-transfer offer for the active receiver."""
        app = MDApp.get_running_app()
        if not app.auth.token:
            self.status.text = "Sign in first"
            return
        if not self.receiver.text:
            self.status.text = "Enter receiver user id"
            return
        path = self.file_path.text.strip()
        if not path:
            self.status.text = "Enter a file path"
            return
        receiver_id = int(self.receiver.text)
        self.status.text = "Preparing file offer..."
        run_in_thread(
            lambda: app.chat.offer_file(app.auth.token, receiver_id, self._file_metadata(path)),
            self._file_offer_success,
            self._file_offer_error,
        )

    def _file_offer_success(self, offer: dict[str, Any]) -> None:
        """Render a created file offer."""
        self.status.text = "File offer sent"
        self._append_rendered_message("Me", f"File offer: {offer['file_name']} ({offer['file_size']} bytes)")

    def _file_offer_error(self, exc: Exception) -> None:
        """Show file offer errors."""
        self.status.text = f"File offer failed: {exc}"

    def _history_success(self, messages: list[dict[str, Any]]) -> None:
        """Render loaded history."""
        app = MDApp.get_running_app()
        my_id = app.auth.user["id"] if app.auth.user else None
        self._clear_messages()
        if not messages:
            self._show_empty("No messages yet")
            self.status.text = ""
            return
        for message in messages:
            mine = message["sender_id"] == my_id
            label = "Me" if mine else self.recipient_label.text.removeprefix("Chat with ")
            self._add_message_bubble(label, self._display_content(message), mine, message)
        self.status.text = ""

    def _history_error(self, exc: Exception) -> None:
        """Show history loading errors."""
        self.status.text = f"History failed: {exc}"

    def _append_rendered_message(self, sender: str, content: str) -> None:
        """Append one message bubble to the transcript."""
        self._add_message_bubble(sender, content, sender == "Me")

    def _on_realtime_payload(self, payload: dict[str, Any]) -> None:
        """Render incoming realtime messages for the active conversation."""
        if payload.get("type") != "message":
            if payload.get("type") == "read_receipt":
                self._on_read_receipt(payload)
            elif payload.get("type") == "typing":
                self._on_typing(payload)
            elif payload.get("type") == "presence":
                self._on_presence(payload)
            elif payload.get("type") == "file_offer":
                self._on_file_offer(payload)
            elif payload.get("type") == "file_response":
                self._on_file_response(payload)
            elif payload.get("type") == "call_offer":
                self._on_call_offer(payload)
            elif payload.get("type") == "call_response":
                self._on_call_response(payload)
            elif payload.get("type") == "call_ended":
                self._on_call_ended(payload)
            return
        app = MDApp.get_running_app()
        active = app.active_chat_user
        current_user = app.auth.user
        message = payload.get("message", {})
        if not active or not current_user:
            return
        peer_id = int(active["id"])
        sender_id = int(message.get("sender_id", 0))
        receiver_id = int(message.get("receiver_id", 0))
        current_id = int(current_user["id"])
        belongs_to_chat = (sender_id == peer_id and receiver_id == current_id) or (sender_id == current_id and receiver_id == peer_id)
        if belongs_to_chat and sender_id != current_id:
            self._append_rendered_message(str(active["username"]), self._display_content(message))
            self.status.text = "New message"

    def _on_read_receipt(self, payload: dict[str, Any]) -> None:
        """Apply realtime read receipts to local messages."""
        app = MDApp.get_running_app()
        active = app.active_chat_user
        if not active or int(payload.get("reader_id", 0)) != int(active["id"]):
            return
        read_ids = {int(message_id) for message_id in payload.get("message_ids", [])}
        changed = False
        for message in app.chat.messages:
            if int(message.get("id", 0)) in read_ids:
                message["read"] = 1
                changed = True
        if changed:
            self._history_success(app.chat.messages)
            self.status.text = "Read"

    def _send_typing(self) -> None:
        """Notify the active peer that the user is typing."""
        app = MDApp.get_running_app()
        if not app.realtime or not self.receiver.text:
            return
        now = datetime.now().timestamp()
        if now - self._last_typing_sent < 1.5:
            return
        self._last_typing_sent = now
        app.realtime.send_json({"type": "typing", "receiver": int(self.receiver.text)})

    def _on_typing(self, payload: dict[str, Any]) -> None:
        """Show a short-lived typing indicator for the active peer."""
        app = MDApp.get_running_app()
        active = app.active_chat_user
        if not active or int(payload.get("sender", 0)) != int(active["id"]):
            return
        self.status.text = f"{active['username']} is typing..."
        Clock.schedule_once(lambda _dt: self._clear_typing_indicator(), 2.5)

    def _clear_typing_indicator(self) -> None:
        """Clear the typing indicator if it is still visible."""
        if self.status.text.endswith("is typing..."):
            self.status.text = ""

    def _on_presence(self, payload: dict[str, Any]) -> None:
        """Apply realtime presence updates to the active chat header."""
        app = MDApp.get_running_app()
        user = payload.get("user", {})
        if not user:
            return
        app.chat.set_presence(user)
        active = app.active_chat_user
        if active and int(active["id"]) == int(user["id"]):
            active["status"] = user.get("status", "offline")
            active["last_seen"] = user.get("last_seen", "")
            self.recipient_label.text = f"Chat with {active['username']} - {active['status']}"

    def _on_file_offer(self, payload: dict[str, Any]) -> None:
        """Render an incoming file offer."""
        app = MDApp.get_running_app()
        active = app.active_chat_user
        offer = payload.get("offer", {})
        if not active or int(payload.get("sender", 0)) != int(active["id"]):
            return
        self._add_file_offer_row(str(active["username"]), offer)
        self.status.text = "Incoming file offer"

    def _add_file_offer_row(self, sender: str, offer: dict[str, Any]) -> None:
        """Render an incoming file offer with accept/refuse actions."""
        if self.empty_label.parent is not None:
            self.message_list.remove_widget(self.empty_label)
        anchor = AnchorLayout(anchor_x="left", size_hint_y=None, height=dp(104))
        card = MDCard(
            orientation="vertical",
            padding=(dp(12), dp(8), dp(12), dp(8)),
            radius=[dp(18), dp(18), dp(18), dp(18)],
            size_hint=(0.82, None),
            height=dp(96),
            elevation=1,
            md_bg_color=(0.18, 0.18, 0.18, 1),
        )
        card.add_widget(MDLabel(text=sender, theme_text_color="Custom", text_color=(0.85, 1, 0.96, 1), font_style="Caption", size_hint_y=None, height=dp(18)))
        card.add_widget(MDLabel(text=f"File: {offer.get('file_name', 'file')} ({offer.get('file_size', 0)} bytes)", theme_text_color="Custom", text_color=(1, 1, 1, 1), size_hint_y=None, height=dp(30)))
        actions = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(36))
        actions.add_widget(MDRaisedButton(text="Accept", on_release=lambda *_: self.respond_file_offer(int(offer["id"]), True, offer)))
        actions.add_widget(MDRaisedButton(text="Refuse", on_release=lambda *_: self.respond_file_offer(int(offer["id"]), False, offer)))
        card.add_widget(actions)
        anchor.add_widget(card)
        self.message_list.add_widget(anchor)
        Clock.schedule_once(lambda _dt: setattr(self.messages, "scroll_y", 0), 0)

    def respond_file_offer(self, file_id: int, accepted: bool, offer: dict[str, Any]) -> None:
        """Accept or refuse a file offer."""
        app = MDApp.get_running_app()
        if not app.auth.token:
            self.status.text = "Sign in first"
            return
        self.status.text = "Sending file response..."
        peer = app.files.start_receive(str(file_id), decrypt_info=self._file_decrypt_info(offer)) if accepted else None
        if accepted:
            self._watch_transfer(str(file_id))
        run_in_thread(
            lambda: app.chat.respond_file(app.auth.token, file_id, accepted, peer),
            lambda offer: self._file_response_success(offer, accepted),
            self._file_response_error,
        )

    def _file_response_success(self, offer: dict[str, Any], accepted: bool) -> None:
        """Show local file response status."""
        action = "accepted" if accepted else "refused"
        self.status.text = f"File offer {action}"
        self._append_rendered_message("Me", f"{action.title()} file offer: {offer['file_name']}")

    def _file_response_error(self, exc: Exception) -> None:
        """Show file response errors."""
        self.status.text = f"File response failed: {exc}"

    def _on_file_response(self, payload: dict[str, Any]) -> None:
        """Render a response to an outgoing file offer."""
        app = MDApp.get_running_app()
        active = app.active_chat_user
        offer = payload.get("offer", {})
        if not active or int(payload.get("responder", 0)) != int(active["id"]):
            return
        if offer.get("status") == "accepted" and offer.get("peer_host") and offer.get("peer_port"):
            app.files.start_send(str(offer["id"]), str(offer.get("file_path", "")), str(offer["peer_host"]), int(offer["peer_port"]))
            self._watch_transfer(str(offer["id"]))
        self._append_rendered_message(
            str(active["username"]),
            f"{str(offer.get('status', 'updated')).title()} file offer: {offer.get('file_name', 'file')}",
        )
        self.status.text = "File response received"

    def start_call(self) -> None:
        """Start a voice-call offer."""
        app = MDApp.get_running_app()
        if not app.auth.token:
            self.status.text = "Sign in first"
            return
        if not self.receiver.text:
            self.status.text = "Enter receiver user id"
            return
        self.status.text = "Calling..."
        run_in_thread(
            lambda: app.chat.start_call(app.auth.token, int(self.receiver.text)),
            self._call_started,
            self._call_error,
        )

    def _call_started(self, call: dict[str, Any]) -> None:
        """Show outgoing call state."""
        self.active_call_id = int(call["id"])
        self._append_rendered_message("Me", "Voice call started")
        self.status.text = "Ringing..."

    def _call_error(self, exc: Exception) -> None:
        """Show call errors."""
        self.status.text = f"Call failed: {exc}"

    def _on_call_offer(self, payload: dict[str, Any]) -> None:
        """Render incoming call controls."""
        app = MDApp.get_running_app()
        active = app.active_chat_user
        call = payload.get("call", {})
        if not active or int(payload.get("caller", 0)) != int(active["id"]):
            return
        self.active_call_id = int(call["id"])
        self._add_call_offer_row(str(active["username"]), call)
        self.status.text = "Incoming call"

    def _add_call_offer_row(self, caller: str, call: dict[str, Any]) -> None:
        """Render accept/decline controls for an incoming call."""
        if self.empty_label.parent is not None:
            self.message_list.remove_widget(self.empty_label)
        anchor = AnchorLayout(anchor_x="left", size_hint_y=None, height=dp(104))
        card = MDCard(
            orientation="vertical",
            padding=(dp(12), dp(8), dp(12), dp(8)),
            radius=[dp(18), dp(18), dp(18), dp(18)],
            size_hint=(0.82, None),
            height=dp(96),
            elevation=1,
            md_bg_color=(0.18, 0.18, 0.18, 1),
        )
        card.add_widget(MDLabel(text=f"Incoming voice call from {caller}", theme_text_color="Custom", text_color=(1, 1, 1, 1), size_hint_y=None, height=dp(36)))
        actions = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(40))
        actions.add_widget(MDRaisedButton(text="Accept", on_release=lambda *_: self.respond_call(int(call["id"]), True)))
        actions.add_widget(MDRaisedButton(text="Decline", on_release=lambda *_: self.respond_call(int(call["id"]), False)))
        card.add_widget(actions)
        anchor.add_widget(card)
        self.message_list.add_widget(anchor)

    def respond_call(self, call_id: int, accepted: bool) -> None:
        """Accept or decline a call."""
        app = MDApp.get_running_app()
        if not app.auth.token:
            self.status.text = "Sign in first"
            return
        audio = app.audio.prepare_receiver(call_id, playback=app.audio.speaker) if accepted else None
        run_in_thread(
            lambda: app.chat.respond_call(app.auth.token, call_id, accepted, audio),
            lambda call: self._call_response_sent(call, accepted),
            self._call_error,
        )

    def _call_response_sent(self, call: dict[str, Any], accepted: bool) -> None:
        """Show local call response."""
        self.active_call_id = int(call["id"]) if accepted else None
        self.status.text = "Call active" if accepted else "Call declined"
        self._append_rendered_message("Me", "Accepted voice call" if accepted else "Declined voice call")

    def _on_call_response(self, payload: dict[str, Any]) -> None:
        """Render peer response to an outgoing call."""
        app = MDApp.get_running_app()
        active = app.active_chat_user
        call = payload.get("call", {})
        if not active or int(payload.get("responder", 0)) != int(active["id"]):
            return
        accepted = bool(payload.get("accepted", False))
        self.active_call_id = int(call["id"]) if accepted else None
        if accepted and call.get("audio_host") and call.get("audio_port") and call.get("audio_key"):
            app.audio.start_sender(int(call["id"]), str(call["audio_host"]), int(call["audio_port"]), str(call["audio_key"]))
        self.status.text = "Call active" if accepted else "Call declined"
        self._append_rendered_message(str(active["username"]), "Accepted voice call" if accepted else "Declined voice call")

    def end_call(self) -> None:
        """End the active call."""
        app = MDApp.get_running_app()
        if not app.auth.token or not self.active_call_id:
            self.status.text = "No active call"
            return
        call_id = self.active_call_id
        run_in_thread(
            lambda: app.chat.end_call(app.auth.token, call_id),
            self._call_ended_local,
            self._call_error,
        )

    def _call_ended_local(self, _call: dict[str, Any]) -> None:
        """Show local call ended state."""
        self.active_call_id = None
        app = MDApp.get_running_app()
        app.audio.end_call()
        self.status.text = "Call ended"
        self._append_rendered_message("Me", "Ended voice call")

    def _on_call_ended(self, payload: dict[str, Any]) -> None:
        """Render peer call ended event."""
        app = MDApp.get_running_app()
        active = app.active_chat_user
        if not active or int(payload.get("ender", 0)) != int(active["id"]):
            return
        self.active_call_id = None
        app.audio.end_call()
        self.status.text = "Call ended"
        self._append_rendered_message(str(active["username"]), "Ended voice call")

    def toggle_mute(self) -> None:
        """Toggle microphone mute."""
        app = MDApp.get_running_app()
        muted = app.audio.toggle_mute()
        self.status.text = "Muted" if muted else "Unmuted"

    def toggle_speaker(self) -> None:
        """Toggle playback output for future accepted calls."""
        app = MDApp.get_running_app()
        app.audio.speaker = not app.audio.speaker
        self.status.text = "Speaker on" if app.audio.speaker else "Speaker off"

    def _watch_transfer(self, transfer_id: str) -> None:
        """Poll and display transfer progress for a short-lived transfer."""
        app = MDApp.get_running_app()
        status = app.files.transfer_status(transfer_id)
        self.transfer_status.text = f"Transfer {transfer_id}: {status['status']} {status.get('progress', 0)}%"
        if status["status"] not in {"sent", "received", "failed", "unknown"}:
            Clock.schedule_once(lambda _dt: self._watch_transfer(transfer_id), 0.5)

    def _clear_messages(self) -> None:
        """Remove all rendered message rows."""
        self.message_list.clear_widgets()

    def _show_empty(self, text: str) -> None:
        """Show an empty-state row in the message list."""
        self.empty_label.text = text
        if self.empty_label.parent is None:
            self.message_list.add_widget(self.empty_label)

    def _add_message_bubble(self, sender: str, content: str, mine: bool, message: dict[str, Any] | None = None) -> None:
        """Render a message bubble aligned by sender."""
        if self.empty_label.parent is not None:
            self.message_list.remove_widget(self.empty_label)

        anchor = AnchorLayout(anchor_x="right" if mine else "left", size_hint_y=None, height=dp(88))
        bubble = MDCard(
            orientation="vertical",
            padding=(dp(12), dp(8), dp(12), dp(8)),
            radius=[dp(18), dp(18), dp(18), dp(18)],
            size_hint=(0.78, None),
            height=dp(80),
            elevation=1,
            md_bg_color=(0.11, 0.55, 0.46, 1) if mine else (0.18, 0.18, 0.18, 1),
        )
        bubble.add_widget(MDLabel(text=sender, theme_text_color="Custom", text_color=(0.85, 1, 0.96, 1), font_style="Caption", size_hint_y=None, height=dp(18)))
        bubble.add_widget(MDLabel(text=content, theme_text_color="Custom", text_color=(1, 1, 1, 1), size_hint_y=None, height=dp(32)))
        bubble.add_widget(
            MDLabel(
                text=self._message_meta(message, mine),
                halign="right",
                theme_text_color="Custom",
                text_color=(0.78, 0.95, 0.91, 1) if mine else (0.72, 0.72, 0.72, 1),
                font_style="Caption",
                size_hint_y=None,
                height=dp(18),
            )
        )
        anchor.add_widget(bubble)
        self.message_list.add_widget(anchor)
        Clock.schedule_once(lambda _dt: setattr(self.messages, "scroll_y", 0), 0)

    def _message_meta(self, message: dict[str, Any] | None, mine: bool) -> str:
        """Build compact timestamp and delivery metadata for a bubble."""
        if not message:
            return "now  delivered" if mine else "now"
        timestamp = self._format_time(str(message.get("timestamp", "")))
        if not mine:
            return timestamp
        if message.get("read"):
            status = "read"
        elif message.get("delivered"):
            status = "delivered"
        else:
            status = "sent"
        return f"{timestamp}  {status}"

    def _format_time(self, raw: str) -> str:
        """Format SQLite or ISO timestamps as HH:MM."""
        if not raw:
            return "now"
        try:
            value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            try:
                value = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return raw[:16]
        return value.strftime("%H:%M")

    def _fingerprint_text(self, user: dict[str, Any]) -> str:
        """Build safety-number display text for the active peer."""
        public_key = user.get("public_key")
        if not public_key:
            return "Safety number unavailable"
        try:
            return f"Safety number: {get_key_fingerprint(str(public_key))}"
        except Exception:
            return "Safety number unavailable"

    def _encrypt_for_active_peer(self, content: str) -> dict[str, str] | None:
        """Encrypt outgoing content when local and peer keys are available."""
        app = MDApp.get_running_app()
        active = app.active_chat_user
        key_record = app.auth.local_key_record()
        if not active or not active.get("public_key") or not key_record or not app.auth.password:
            return None
        try:
            private_key = app.chat.decrypt_private_key(key_record["encrypted_private_key"], app.auth.password)
            return app.chat.encrypt_for_user(content, private_key, str(active["public_key"]))
        except Exception:
            self.status.text = "Encryption unavailable, sending plain text"
            return None

    def _file_metadata(self, path: str) -> dict[str, Any]:
        """Build encrypted file metadata when E2E keys are available."""
        app = MDApp.get_running_app()
        aes_key = self._active_peer_aes_key()
        if aes_key:
            return app.files.encrypted_metadata_for(path, aes_key)
        return app.files.metadata_for(path)

    def _file_decrypt_info(self, offer: dict[str, Any]) -> dict[str, Any] | None:
        """Build decrypt info for an accepted encrypted file offer."""
        if not offer.get("encrypted_file"):
            return None
        aes_key = self._active_peer_aes_key()
        if not aes_key:
            return None
        return {
            "aes_key": aes_key,
            "nonce": offer["nonce"],
            "tag": offer["tag"],
            "original_file_name": offer.get("original_file_name") or str(offer.get("file_name", "file")).removesuffix(".mavi.enc"),
        }

    def _active_peer_aes_key(self) -> bytes | None:
        """Derive the active peer AES key if local credentials are available."""
        app = MDApp.get_running_app()
        active = app.active_chat_user
        key_record = app.auth.local_key_record()
        if not active or not active.get("public_key") or not key_record or not app.auth.password:
            return None
        try:
            private_key = app.chat.decrypt_private_key(key_record["encrypted_private_key"], app.auth.password)
            return app.chat.shared_aes_key(private_key, str(active["public_key"]))
        except Exception:
            return None

    def _display_content(self, message: dict[str, Any]) -> str:
        """Return decrypted message content when possible."""
        app = MDApp.get_running_app()
        active = app.active_chat_user
        key_record = app.auth.local_key_record()
        if not message.get("nonce") or not message.get("tag"):
            return str(message.get("content", ""))
        if not active or not active.get("public_key") or not key_record or not app.auth.password:
            return "[encrypted message]"
        try:
            private_key = app.chat.decrypt_private_key(key_record["encrypted_private_key"], app.auth.password)
            return app.chat.decrypt_from_user(message, private_key, str(active["public_key"]))
        except Exception:
            return "[could not decrypt]"

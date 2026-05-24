"""Screen implementation for ChatScreen."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import textwrap
from typing import Any

from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen

from client.screens.async_helpers import run_in_thread
from client.utils.paths import mavi_data_dir
from network.encryption import get_key_fingerprint


class ChatScreen(MDScreen):
    """Realtime chat screen."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._listener_registered = False
        self._last_typing_sent = 0.0
        self.selected_file_path = ""
        self._rendered_received_files: set[str] = set()
        self._incoming_file_offers: dict[str, dict[str, Any]] = {}

    def on_pre_enter(self, *args: object) -> None:
        """Create widgets lazily so Kivy properties are ready."""
        if self.children:
            return
        layout = BoxLayout(orientation="vertical", spacing=dp(5), padding=dp(8))

        header = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(52))
        header.add_widget(Button(text="Back", font_size=dp(13), size_hint_x=None, width=dp(72), on_release=lambda *_: setattr(self.manager, "current", "chat_list")))
        header_text = BoxLayout(orientation="vertical")
        self.recipient_label = Label(text="No recipient selected", font_size=dp(18))
        self.fingerprint_label = Label(text="")
        header_text.add_widget(self.recipient_label)
        header.add_widget(header_text)
        layout.add_widget(header)

        self.receiver = TextInput(hint_text="User id", input_filter="int", multiline=False)

        self.message_list = BoxLayout(orientation="vertical", spacing=dp(8), size_hint_y=None, padding=(0, dp(8), 0, dp(8)))
        self.message_list.bind(minimum_height=self.message_list.setter("height"))
        self.messages = ScrollView(do_scroll_x=False, size_hint_y=1)
        self.messages.add_widget(self.message_list)
        self.empty_label = Label(text="Messages appear here", size_hint_y=None, height=dp(48))
        self.message_list.add_widget(self.empty_label)
        layout.add_widget(self.messages)

        composer = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(44))
        self.message = TextInput(hint_text="Message", multiline=False, font_size=dp(16), size_hint_y=None, height=dp(44))
        self.message.bind(text=lambda _field, _text: self._send_typing())
        composer.add_widget(self.message)
        composer.add_widget(Button(text="Send", font_size=dp(13), size_hint_x=None, width=dp(76), on_release=lambda *_: self.send()))
        layout.add_widget(composer)

        call_tools = BoxLayout(orientation="horizontal", spacing=dp(4), size_hint_y=None, height=dp(36))
        call_tools.add_widget(Button(text="Call", font_size=dp(12), on_release=lambda *_: self.start_call()))
        call_tools.add_widget(Button(text="End", font_size=dp(12), on_release=lambda *_: self.end_call()))
        call_tools.add_widget(Button(text="Mute", font_size=dp(12), on_release=lambda *_: self.toggle_mute()))
        call_tools.add_widget(Button(text="Speaker", font_size=dp(12), on_release=lambda *_: self.toggle_speaker()))
        layout.add_widget(call_tools)

        file_tools = BoxLayout(orientation="horizontal", spacing=dp(6), size_hint_y=None, height=dp(38))
        self.file_label = Label(text="No file selected", font_size=dp(11))
        file_tools.add_widget(Button(text="Attach", font_size=dp(12), size_hint_x=None, width=dp(86), on_release=lambda *_: self.choose_file()))
        file_tools.add_widget(self.file_label)
        file_tools.add_widget(Button(text="Offer", font_size=dp(12), size_hint_x=None, width=dp(76), on_release=lambda *_: self.offer_file()))
        layout.add_widget(file_tools)

        self.transfer_status = Label(text="", font_size=dp(11), size_hint_y=None, height=dp(20))
        self.active_call_id: int | None = None
        self.status = Label(text="", font_size=dp(11), size_hint_y=None, height=dp(24))
        layout.add_widget(self.transfer_status)
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
            self.fingerprint_label.text = ""
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
        path = self.selected_file_path.strip()
        if not path:
            self.status.text = "Attach a file first"
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
        self._add_file_card("Me", offer, mine=True, local_path=self.selected_file_path, state="Offer sent")

    def _file_offer_error(self, exc: Exception) -> None:
        """Show file offer errors."""
        self.status.text = f"File offer failed: {exc}"

    def choose_file(self) -> None:
        """Open a platform file picker when available."""
        if self._choose_file_android():
            return
        self._choose_file_plyer()

    def _choose_file_android(self) -> bool:
        """Open Android's document picker and copy the selected content URI."""
        try:
            from android import activity
            from jnius import autoclass
        except Exception:
            return False
        try:
            intent_class = autoclass("android.content.Intent")
            python_activity = autoclass("org.kivy.android.PythonActivity")
            intent = intent_class(intent_class.ACTION_OPEN_DOCUMENT)
            intent.addCategory(intent_class.CATEGORY_OPENABLE)
            intent.setType("*/*")
            activity.bind(on_activity_result=self._on_android_file_result)
            python_activity.mActivity.startActivityForResult(intent, 6208)
            self.status.text = "Choose a file..."
            return True
        except Exception as exc:
            self.status.text = f"File picker failed: {exc}"
            return True

    def _choose_file_plyer(self) -> None:
        """Fallback file picker for non-Android platforms."""
        try:
            from plyer import filechooser
        except Exception:
            self.status.text = "File picker unavailable in this build"
            return
        try:
            filechooser.open_file(on_selection=self._file_selected)
            self.status.text = "Choose a file..."
        except Exception as exc:
            self.status.text = f"File picker failed: {exc}"

    def _file_selected(self, selection: list[str] | tuple[str, ...]) -> None:
        """Store the file selected from the platform picker."""
        if not selection or not selection[0] or str(selection[0]).lower() == "none":
            self.status.text = "No file selected"
            self.selected_file_path = ""
            self.file_label.text = "No file selected"
            return
        self._set_selected_file(str(selection[0]))
        self.status.text = ""

    def _on_android_file_result(self, request_code: int, result_code: int, intent: object) -> None:
        """Handle Android document picker result."""
        if request_code != 6208:
            return
        try:
            from android import activity
            from jnius import autoclass

            activity.unbind(on_activity_result=self._on_android_file_result)
            android_activity = autoclass("android.app.Activity")
            if result_code != android_activity.RESULT_OK or intent is None:
                self.status.text = "No file selected"
                return
            uri = intent.getData()
            if uri is None:
                self.status.text = "No file selected"
                return
            target = self._copy_android_uri(uri)
            self._set_selected_file(str(target))
        except Exception as exc:
            self.status.text = f"Attach failed: {exc}"

    def _copy_android_uri(self, uri: object) -> Path:
        """Copy a content URI into app-private storage and return its local path."""
        from jnius import autoclass

        python_activity = autoclass("org.kivy.android.PythonActivity")
        resolver = python_activity.mActivity.getContentResolver()
        filename = self._android_display_name(resolver, uri) or f"attachment-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        target_dir = mavi_data_dir() / "attachments"
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / self._safe_attachment_name(filename)

        input_stream = resolver.openInputStream(uri)
        if input_stream is None:
            raise OSError("Could not open selected file")
        try:
            with target.open("wb") as output:
                while True:
                    value = input_stream.read()
                    if value == -1:
                        break
                    output.write(bytes((int(value) & 0xFF,)))
        finally:
            input_stream.close()
        return target

    def _android_display_name(self, resolver: object, uri: object) -> str | None:
        """Read a display name from Android's content resolver."""
        try:
            from jnius import autoclass

            openable_columns = autoclass("android.provider.OpenableColumns")
            cursor = resolver.query(uri, None, None, None, None)
            if cursor is None:
                return None
            try:
                index = cursor.getColumnIndex(openable_columns.DISPLAY_NAME)
                if index >= 0 and cursor.moveToFirst():
                    return str(cursor.getString(index))
            finally:
                cursor.close()
        except Exception:
            return None
        return None

    def _safe_attachment_name(self, filename: str) -> str:
        """Return a local filename safe for app-private storage."""
        cleaned = "".join(char if char.isalnum() or char in "._- " else "_" for char in filename).strip()
        return cleaned or "attachment"

    def _set_selected_file(self, path: str) -> None:
        """Store selected file path and update compact UI text."""
        self.selected_file_path = path
        name = Path(path).name or "file"
        self.file_label.text = f"Selected: {name[:24]}"
        self.status.text = ""

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
        self._add_file_card(str(active["username"]), offer, mine=False, incoming=True, state="Incoming file")
        self.status.text = "Incoming file offer"

    def _add_file_offer_row(self, sender: str, offer: dict[str, Any]) -> None:
        """Render an incoming file offer with accept/refuse actions."""
        self._add_file_card(sender, offer, mine=False, incoming=True, state="Incoming file")

    def _add_file_card(
        self,
        sender: str,
        offer: dict[str, Any],
        mine: bool,
        local_path: str | None = None,
        incoming: bool = False,
        state: str = "",
    ) -> None:
        """Render a file attachment card with optional image preview."""
        if self.empty_label.parent is not None:
            self.message_list.remove_widget(self.empty_label)
        file_name = self._file_display_name(offer)
        preview_path = local_path if local_path and self._is_image_file(local_path, offer) and Path(local_path).exists() else None
        card_height = dp(220) if preview_path else dp(112)
        anchor = AnchorLayout(anchor_x="right" if mine else "left", size_hint_y=None, height=card_height + dp(8))
        card = BoxLayout(
            orientation="vertical",
            padding=(dp(10), dp(7), dp(10), dp(7)),
            spacing=dp(4),
            size_hint=(0.82, None),
            height=card_height,
        )
        self._paint_background(card, (0.08, 0.42, 0.34, 1) if mine else (0.20, 0.20, 0.20, 1))
        if not mine:
            card.add_widget(Label(text=sender, color=(0.52, 0.90, 0.80, 1), font_size=dp(11), size_hint_y=None, height=dp(16)))
        if preview_path:
            card.add_widget(Image(source=preview_path, allow_stretch=True, keep_ratio=True, size_hint_y=None, height=dp(128)))
        card.add_widget(Label(text=f"File: {file_name}", color=(1, 1, 1, 1), font_size=dp(14), size_hint_y=None, height=dp(24)))
        card.add_widget(Label(text=self._file_card_meta(offer, state), color=(0.72, 0.72, 0.72, 1), font_size=dp(10), size_hint_y=None, height=dp(18)))
        if incoming:
            actions = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(34))
            actions.add_widget(Button(text="Download", font_size=dp(11), on_release=lambda *_: self.respond_file_offer(int(offer["id"]), True, offer)))
            actions.add_widget(Button(text="Refuse", font_size=dp(11), on_release=lambda *_: self.respond_file_offer(int(offer["id"]), False, offer)))
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
            active = app.active_chat_user or {}
            self._incoming_file_offers[str(file_id)] = {"sender": str(active.get("username", "Peer")), "offer": offer}
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
        self._add_file_card("Me", offer, mine=True, state=f"{action.title()} file offer")

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
        self._add_file_card(str(active["username"]), offer, mine=False, state=str(offer.get("status", "updated")).title())
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
        card = BoxLayout(
            orientation="vertical",
            padding=(dp(12), dp(8), dp(12), dp(8)),
            size_hint=(0.88, None),
            height=dp(96),
        )
        card.add_widget(Label(text=f"Incoming voice call from {caller}", size_hint_y=None, height=dp(36)))
        actions = BoxLayout(orientation="horizontal", spacing=dp(8), size_hint_y=None, height=dp(40))
        actions.add_widget(Button(text="Accept", on_release=lambda *_: self.respond_call(int(call["id"]), True)))
        actions.add_widget(Button(text="Decline", on_release=lambda *_: self.respond_call(int(call["id"]), False)))
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
        if status["status"] == "received" and transfer_id not in self._rendered_received_files and status.get("file"):
            self._rendered_received_files.add(transfer_id)
            file_path = str(status["file"])
            incoming = self._incoming_file_offers.get(transfer_id, {})
            offer = dict(incoming.get("offer") or {})
            sender = str(incoming.get("sender") or "Peer")
            offer.update(
                {
                    "file_name": Path(file_path).name,
                    "file_size": Path(file_path).stat().st_size if Path(file_path).exists() else 0,
                    "file_type": "image/*" if self._is_image_file(file_path, offer) else offer.get("file_type", "application/octet-stream"),
                }
            )
            self._add_file_card(
                sender,
                offer,
                mine=False,
                local_path=file_path,
                state="Downloaded",
            )
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

        wrapped_content = self._wrap_message_text(content)
        content_lines = max(1, wrapped_content.count("\n") + 1)
        sender_lines = 0 if mine else 1
        bubble_height = dp(24 + (content_lines * 19) + (sender_lines * 17) + 16)
        anchor = AnchorLayout(anchor_x="right" if mine else "left", size_hint_y=None, height=bubble_height + dp(8))
        bubble = BoxLayout(
            orientation="vertical",
            padding=(dp(10), dp(6), dp(10), dp(5)),
            size_hint=(0.78, None),
            height=bubble_height,
        )
        self._paint_background(bubble, (0.08, 0.42, 0.34, 1) if mine else (0.20, 0.20, 0.20, 1))
        if not mine:
            bubble.add_widget(Label(text=sender, color=(0.52, 0.90, 0.80, 1), font_size=dp(11), size_hint_y=None, height=dp(17)))
        bubble.add_widget(
            Label(
                text=wrapped_content,
                color=(1, 1, 1, 1),
                font_size=dp(15),
                halign="left",
                valign="middle",
                size_hint_y=None,
                height=dp(content_lines * 19 + 4),
            )
        )
        bubble.add_widget(
            Label(
                text=self._message_meta(message, mine),
                color=(0.72, 0.86, 0.82, 1) if mine else (0.62, 0.62, 0.62, 1),
                font_size=dp(9),
                halign="right",
                size_hint_y=None,
                height=dp(14),
            )
        )
        anchor.add_widget(bubble)
        self.message_list.add_widget(anchor)
        Clock.schedule_once(lambda _dt: setattr(self.messages, "scroll_y", 0), 0)

    def _paint_background(self, widget: BoxLayout, color: tuple[float, float, float, float]) -> None:
        """Draw a lightweight rounded background behind a bubble."""
        with widget.canvas.before:
            Color(*color)
            background = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(14)])
        widget.bind(pos=lambda instance, _value: setattr(background, "pos", instance.pos))
        widget.bind(size=lambda instance, _value: setattr(background, "size", instance.size))

    def _wrap_message_text(self, content: str) -> str:
        """Wrap long chat text so it stays inside the screen."""
        lines: list[str] = []
        for source_line in str(content).splitlines() or [""]:
            wrapped = textwrap.wrap(source_line, width=30, break_long_words=True, replace_whitespace=False)
            lines.extend(wrapped or [""])
        return "\n".join(lines)

    def _file_display_name(self, offer: dict[str, Any]) -> str:
        """Return the user-facing file name for an offer."""
        return str(offer.get("original_file_name") or offer.get("file_name") or "file")

    def _file_card_meta(self, offer: dict[str, Any], state: str) -> str:
        """Build compact metadata for a file card."""
        size = int(offer.get("file_size") or 0)
        if size >= 1024 * 1024:
            size_text = f"{size / (1024 * 1024):.1f} MB"
        elif size >= 1024:
            size_text = f"{size / 1024:.1f} KB"
        else:
            size_text = f"{size} B"
        prefix = f"{state} - " if state else ""
        return f"{prefix}{size_text}"

    def _is_image_file(self, path_or_name: str, offer: dict[str, Any]) -> bool:
        """Return whether an attachment is likely displayable as an image."""
        file_type = str(offer.get("file_type") or "").lower()
        suffix = Path(path_or_name).suffix.lower()
        return file_type.startswith("image/") or suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

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
            fingerprint = get_key_fingerprint(str(public_key))
            return f"Safety: {fingerprint[:9]}...{fingerprint[-9:]}"
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

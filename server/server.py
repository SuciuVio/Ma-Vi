"""Ma:Vi aiohttp server entry point."""

from __future__ import annotations

import logging
from aiohttp import web

from server.db.database import Database
from server.handlers.api_handler import add_contact, contacts, conversations, end_call, favorite_contact, messages, offer_file, respond_call, respond_file, search_users, send_message, start_call
from server.handlers.auth_handler import login, refresh, register
from server.handlers.call_handler import calls_ws
from server.handlers.chat_handler import chat_ws
from server.handlers.file_handler import file_transfer_ws
from server.handlers.search_handler import SearchLimiter, search_ws
from server.utils.config import CONFIG
from server.utils.logger import configure_logging


async def health(request: web.Request) -> web.Response:
    """Return service health."""
    return web.json_response({"ok": True, "service": "mavi-server"})


async def user_detail(request: web.Request) -> web.Response:
    """Return a public user profile."""
    user = request.app["db"].get_user(int(request.match_info["user_id"]))
    return web.json_response({"ok": True, "user": user})


def create_app() -> web.Application:
    """Create and configure the aiohttp app."""
    app = web.Application()
    app["config"] = CONFIG
    app["db"] = Database(CONFIG.database_path)
    app["connections"] = {}
    app["file_connections"] = {}
    app["call_connections"] = {}
    app["search_limiter"] = SearchLimiter()
    app.add_routes(
        [
            web.get("/health", health),
            web.post("/api/auth/register", register),
            web.post("/api/auth/login", login),
            web.post("/api/auth/refresh", refresh),
            web.get("/api/users/{user_id}", user_detail),
            web.get("/api/search", search_users),
            web.get("/api/contacts", contacts),
            web.post("/api/contacts", add_contact),
            web.post("/api/contacts/favorite", favorite_contact),
            web.get("/api/conversations", conversations),
            web.get("/api/messages", messages),
            web.post("/api/messages", send_message),
            web.post("/api/files/offer", offer_file),
            web.post("/api/files/respond", respond_file),
            web.post("/api/calls/start", start_call),
            web.post("/api/calls/respond", respond_call),
            web.post("/api/calls/end", end_call),
            web.get("/ws/chat", chat_ws),
            web.get("/ws/search", search_ws),
            web.get("/ws/calls", calls_ws),
            web.get("/ws/file_transfer", file_transfer_ws),
        ]
    )
    return app


def main() -> None:
    """Run the server."""
    configure_logging(CONFIG.log_level)
    logging.getLogger(__name__).info("Starting Ma:Vi server on %s:%s", CONFIG.host, CONFIG.port)
    web.run_app(create_app(), host=CONFIG.host, port=CONFIG.port)


if __name__ == "__main__":
    main()

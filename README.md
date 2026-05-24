# Ma:Vi

Ma:Vi is an isolated messaging application project for Android. The main codebase is Python, with auxiliary languages and configuration files allowed when they make Android integration, build, testing, or tooling simpler.

## Features

- REST registration and login with bcrypt.
- Async WebSocket chat, search, call signaling, and file-transfer signaling.
- SQLite schema auto-initialized at server boot.
- X25519/AES-256-GCM encryption helpers.
- KivyMD client screens for login, registration, chat list, chat, search, profile, and settings.
- P2P TCP file transfer and UDP audio streaming primitives.
- Experimental next-generation FastAPI backend in `mavi_backend/`.
- Experimental Flutter mobile client in `mobile_flutter/`.

## Quick Start

```bash
cd C:\mavi_project
py -3.11 -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m server.server
```

Run the desktop client in another terminal:

```bash
cd C:\mavi_project
.venv\Scripts\python -m client.main
```

## Next Stack

The new direction is Flutter + FastAPI + SQLite:

- `mavi_backend/` is the new API/WebSocket backend.
- `mobile_flutter/` is the new Android client shell.
- SQLite remains the source of truth for users, messages, contacts, and attachments.
- Attachments are uploaded to the server and referenced from chat messages instead
  of using peer-to-peer file paths.
- Uploaded attachment files are temporary. `MAVI_ATTACHMENT_TTL_DAYS` controls
  how many days they remain available before server cleanup removes them.

## Android Build

The APK is client-only. The server runs separately. Buildozer excludes `server/`
and `tests/` from the APK and uses Android-safe requirements from
`buildozer.spec`. See `BUILD_ANDROID.md`.

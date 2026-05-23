# API

## REST

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/users/{id}`

## WebSocket

- `/ws/chat?token=...`
- `/ws/search?token=...`
- `/ws/calls?token=...`
- `/ws/file_transfer?token=...`

Chat messages use JSON envelopes with `type`, `receiver`, `content`, `timestamp`, and optional encrypted `payload`.

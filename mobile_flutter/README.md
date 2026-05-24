# Ma:Vi Flutter Client

This is the planned replacement mobile client for Ma:Vi.

The UI is inspired by common chat patterns from WhatsApp, Telegram, Signal, and Messenger:

- conversation-first navigation
- left/right message bubbles
- compact timestamps and delivery state
- attachment upload before sending the message
- image previews from server URLs

The implementation is original and talks to the FastAPI + SQLite backend in `mavi_backend`.

## Run

Install Flutter, then:

```bash
cd mobile_flutter
flutter pub get
flutter run --dart-define=MAVI_API_BASE=https://your-render-service.onrender.com
```

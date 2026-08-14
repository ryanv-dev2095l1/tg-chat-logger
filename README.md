# tg-chat-logger

Small daemon that listens to noisy Telegram alert channels, extracts stacktraces
and log levels from bot dumps, and saves them to local SQLite.

## Quick setup

1. Install dependencies:
```bash
pip install -e .
```

2. Create a config file `config.yaml`:
```yaml
telegram:
  api_id: 123456
  api_hash: "your_api_hash"
  session_name: "tg_logger"
  channel_ids:
    - -1001234567890

storage:
  db_path: "alerts.db"
```

3. First login (interactive for Telegram code):
```bash
tg-chat-logger --config config.yaml --auth-only
```

4. Run daemon:
```bash
tg-chat-logger --config config.yaml
```

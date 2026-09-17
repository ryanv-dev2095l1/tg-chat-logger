# tg-chat-logger

Small daemon that listens to noisy Telegram alert channels, extracts stacktraces
and log levels from bot dumps, and saves them to local SQLite and Prometheus.

We got tired of alert bots spamming raw Python tracebacks without structure,
so this strips noise, extracts error classes and service tags, and stores
the clean records.

## Setup

```bash
pip install -e .
```

Create `config.yaml`:

```yaml
telegram:
  api_id: 123456
  api_hash: "your_api_hash"
  session_path: "./data/session"
  channel_ids:
    - -1001234567890
    - -1009876543210

storage:
  db_path: "./data/alerts.db"

metrics:
  enabled: true
  port: 9108
  host: "0.0.0.0"
```

Generate session file on your dev box first:

```bash
tg-chat-logger --config config.yaml --auth-only
```

Then launch the worker:

```bash
tg-chat-logger --config config.yaml
```

## Prometheus metrics

When enabled, the scraper serves metrics at `http://<host>:<port>/metrics`:

- `tg_alerts_total{service="...", level="..."}`: Count of parsed alert messages.
- `tg_parser_errors_total`: Messages that failed regex extraction.
- `tg_messages_raw_total`: Total telegram events processed.

## Systemd example

```ini
[Unit]
Description=TG Chat Logger Daemon
After=network.target

[Service]
Type=simple
User=logger
WorkingDirectory=/opt/tg-chat-logger
ExecStart=/opt/tg-chat-logger/venv/bin/tg-chat-logger --config /etc/tg-chat-logger.yaml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

<!-- last-sync: 2026-09-17 -->

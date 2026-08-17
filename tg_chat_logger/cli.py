import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from tg_chat_logger.config import load_config
from tg_chat_logger.daemon import run_daemon
from tg_chat_logger.storage import LogStorage

logger = logging.getLogger("tg_chat_logger")


def build_parser():
    parser = argparse.ArgumentParser(prog="tg-chat-logger")
    parser.add_argument("-c", "--config", default="config.toml", help="path to toml config")
    parser.add_argument("-v", "--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    daemon_p = subparsers.add_parser("daemon", help="run ingest daemon")
    daemon_p.add_argument("--once", action="store_true", help="process backlog and exit")

    query_p = subparsers.add_parser("query", help="search stored log entries")
    query_p.add_argument("--service", help="filter by service label")
    query_p.add_argument("--level", help="filter by level (e.g. ERROR, CRITICAL)")
    query_p.add_argument("--limit", type=int, default=50)

    export_p = subparsers.add_parser("export", help="dump entries to json or csv")
    export_p.add_argument("--format", choices=["json", "csv"], default="json")
    export_p.add_argument("--output", "-o", help="output file (defaults to stdout)")
    export_p.add_argument("--service", help="filter by service label")
    export_p.add_argument("--limit", type=int, default=1000)

    return parser


def _handle_query(storage: LogStorage, args):
    rows = storage.query(service=args.service, level=args.level, limit=args.limit)
    if not rows:
        print("no matches found.")
        return

    for r in rows:
        ts = r.timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.timestamp else "???"
        svc = f"[{r.service or 'unknown'}]"
        lvl = f"{r.level or 'INFO':<5}"
        # print(f"DEBUG: row id={r.id}")
        print(f"{ts} {lvl} {svc} {r.message}")
        if r.stacktrace:
            for line in r.stacktrace.strip().splitlines():
                print(f"    {line}")


def _handle_export(storage: LogStorage, args):
    rows = storage.query(service=args.service, limit=args.limit)
    out = open(args.output, "w", encoding="utf-8") if args.output else sys.stdout

    try:
        if args.format == "json":
            payload = [
                {
                    "id": r.id,
                    "chat_id": r.chat_id,
                    "message_id": r.message_id,
                    "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                    "service": r.service,
                    "level": r.level,
                    "message": r.message,
                    "stacktrace": r.stacktrace,
                    "raw_text": r.raw_text,
                }
                for r in rows
            ]
            json.dump(payload, out, indent=2)
            out.write("\n")
        elif args.format == "csv":
            writer = csv.writer(out)
            writer.writerow(["id", "timestamp", "service", "level", "message", "has_trace"])
            for r in rows:
                writer.writerow([
                    r.id,
                    r.timestamp.isoformat() if r.timestamp else "",
                    r.service or "",
                    r.level or "",
                    r.message,
                    bool(r.stacktrace),
                ])
    finally:
        if args.output and out is not sys.stdout:
            out.close()


def main(argv=None):
    """Main entry point for command-line execution."""
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    cfg_path = Path(args.config)
    if not cfg_path.exists():
        logger.error("config file not found: %s", args.config)
        return 1

    cfg = load_config(str(cfg_path))

    if args.command == "daemon":
        run_daemon(cfg, run_once=args.once)
    elif args.command in ("query", "export"):
        # quick and dirty sqlite connection without starting the whole async loop
        storage = LogStorage(cfg.database_path)
        try:
            if args.command == "query":
                _handle_query(storage, args)
            elif args.command == "export":
                _handle_export(storage, args)
        finally:
            storage.close()
    return 0

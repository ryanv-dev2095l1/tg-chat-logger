import argparse
import logging
import sys
from tg_chat_logger.config import load_config
from tg_chat_logger.daemon import run_daemon

logger = logging.getLogger("tg_chat_logger")


def build_parser():
    parser = argparse.ArgumentParser(prog="tg-chat-logger")
    parser.add_argument("-c", "--config", default="config.toml", help="path to toml config")
    parser.add_argument("-v", "--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    daemon_p = subparsers.add_parser("daemon", help="run the ingest daemon")
    daemon_p.add_argument("--once", action="store_true", help="process backlog and exit")

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    cfg = load_config(args.config)
    if args.command == "daemon":
        run_daemon(cfg, run_once=args.once)
    return 0

import threading
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Tuple


class MetricsRegistry:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = defaultdict(float)
        self._gauges: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], float] = {}

    def inc(self, name: str, value: float = 1.0, **labels):
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._counters[key] += value

    def set_gauge(self, name: str, value: float, **labels):
        key = (name, tuple(sorted(labels.items())))
        with self._lock:
            self._gauges[key] = value

    def render(self) -> str:
        lines = []
        with self._lock:
            # format counters
            for (name, label_items), val in sorted(self._counters.items()):
                if label_items:
                    lbl_str = ",".join(f'{k}="{v}"' for k, v in label_items)
                    lines.append(f"{name}{{{lbl_str}}} {val}")
                else:
                    lines.append(f"{name} {val}")

            for (name, label_items), val in sorted(self._gauges.items()):
                if label_items:
                    lbl_str = ",".join(f'{k}="{v}"' for k, v in label_items)
                    lines.append(f"{name}{{{lbl_str}}} {val}")
                else:
                    lines.append(f"{name} {val}")

        lines.append("")
        return "\n".join(lines)


REGISTRY = MetricsRegistry()


class _MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            payload = REGISTRY.render().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # silent default logger to prevent spamming stderr on every scrape
        pass


def start_metrics_server(host: str = "0.0.0.0", port: int = 9102) -> HTTPServer:
    server = HTTPServer((host, port), _MetricsHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    return server

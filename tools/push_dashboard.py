"""Create or update the 'AC Adaptive LT2' dashboard on Home Assistant from dashboards/ac_adaptive_lt2.yaml.

CHANGES THE LIVE SITE. It refuses to run without --confirm.

    python tools/push_dashboard.py            # dry run: validates the file and prints what it would do
    python tools/push_dashboard.py --confirm  # creates the dashboard if missing, then saves its config

What it touches: only the storage dashboard with url_path `ac-adaptive-lt2` (it is created when missing).
No other dashboard, no entity, no climate service and no Gemini call. It talks to the HA WebSocket API
(`lovelace/dashboards/create`, `lovelace/config/save`) with the standard library only.

The token is read from credentials/ha_token.txt and is never printed. HTTP 530 or a connection error
means HA is down: it stops and does not retry.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ha_client import BASE_URL, HAUnreachable, _token  # noqa: E402

DASHBOARD_FILE = Path(__file__).resolve().parent.parent / "dashboards" / "ac_adaptive_lt2.yaml"
URL_PATH = "ac-adaptive-lt2"
TITLE = "AC Adaptive"
ICON = "mdi:air-conditioner"

# Card types that can change a device. The dashboard must never contain one.
FORBIDDEN_TYPES = {"thermostat", "custom:simple-thermostat", "custom:better-thermostat-ui-card",
                   "button", "entity-button", "light", "media-control", "tile", "entities",
                   "custom:mushroom-climate-card", "custom:mushroom-entity-card"}
ALLOWED_ACTIONS = {"none", "more-info", "navigate"}
# A JavaScript template in a button-card could call Home Assistant. These calls are never allowed.
FORBIDDEN_JS = ("callService", "callWS", "callApi", "fetch(", "XMLHttpRequest", "eval(", "new Function",
                "WebSocket", "localStorage", "window.", "document.", "hass.connection")
def load_dashboard() -> dict:
    return yaml.safe_load(DASHBOARD_FILE.read_text(encoding="utf-8"))


def walk(node):
    """Yield every dict in a nested config."""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def strings(node):
    """Yield every string in a nested config."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def read_only_problems(config: dict) -> list[str]:
    """Reasons this dashboard could change a device (empty list = read-only)."""
    problems = []
    for node in walk(config):
        kind = node.get("type")
        if kind in FORBIDDEN_TYPES:
            problems.append(f"controlling card type: {kind}")
        if kind == "custom:button-card":
            if "entity" in node:
                problems.append("custom:button-card with an entity (its default tap action would toggle it)")
            for key in ("tap_action", "hold_action", "double_tap_action"):
                if key not in node:
                    problems.append(f"custom:button-card without an explicit {key}")
        for key in ("tap_action", "hold_action", "double_tap_action", "press_action", "release_action",
                    "icon_tap_action", "icon_hold_action", "icon_double_tap_action"):
            action = node.get(key)
            if action is not None and action.get("action") not in ALLOWED_ACTIONS:
                problems.append(f"{key} = {action.get('action')}")
        if "service" in node or "perform_action" in node:
            problems.append("a card calls a service")
    for text in strings(config):
        for needle in FORBIDDEN_JS:
            if needle in text:
                problems.append(f"JavaScript uses {needle}")
    return problems


# ---- minimal WebSocket client (RFC 6455, text frames only) ----------------------------------------


class WebSocket:
    def __init__(self, url: str, timeout: int = 30):
        parts = urlparse(url)
        host, secure = parts.hostname, parts.scheme in ("https", "wss")
        port = parts.port or (443 if secure else 80)
        try:
            sock = socket.create_connection((host, port), timeout=timeout)
            if secure:
                sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        except OSError as err:
            raise HAUnreachable(f"connection error: {err}") from None
        self.sock = sock
        key = base64.b64encode(os.urandom(16)).decode()
        request = (f"GET /api/websocket HTTP/1.1\r\nHost: {host}\r\nUpgrade: websocket\r\n"
                   f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                   f"User-Agent: ac-adaptive/1.0\r\n\r\n")
        sock.sendall(request.encode())
        head = b""
        while b"\r\n\r\n" not in head:
            chunk = sock.recv(4096)
            if not chunk:
                raise HAUnreachable("connection closed during the WebSocket handshake")
            head += chunk
        status = head.split(b"\r\n", 1)[0].decode()
        if " 101 " not in status:
            code = status.split(" ")[1] if " " in status else "?"
            if code in ("502", "503", "504", "530"):
                raise HAUnreachable(f"HTTP {code}: Home Assistant looks down")
            raise RuntimeError(f"WebSocket handshake failed: {status}")
        accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest())
        if accept not in head:
            raise RuntimeError("WebSocket handshake failed: bad accept key")
        self.buffer = head.split(b"\r\n\r\n", 1)[1]

    def _read(self, count: int) -> bytes:
        while len(self.buffer) < count:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise HAUnreachable("connection closed")
            self.buffer += chunk
        data, self.buffer = self.buffer[:count], self.buffer[count:]
        return data

    def send(self, payload: dict) -> None:
        data = json.dumps(payload).encode()
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header += struct.pack(">H", length)
        else:
            header.append(0x80 | 127)
            header += struct.pack(">Q", length)
        mask = os.urandom(4)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + mask + masked)

    def receive(self) -> dict:
        message = b""
        while True:
            first, second = self._read(2)
            opcode, length = first & 0x0F, second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            data = self._read(length)
            if opcode == 0x8:
                raise HAUnreachable("connection closed by the server")
            if opcode == 0x9:  # ping: ignore, HA keeps the line open
                continue
            message += data
            if first & 0x80:
                return json.loads(message.decode())

    def close(self) -> None:
        try:
            self.sock.close()
        except OSError:
            pass


class HA:
    def __init__(self):
        self.ws = WebSocket(BASE_URL)
        self.next_id = 0
        hello = self.ws.receive()
        if hello.get("type") != "auth_required":
            raise RuntimeError("unexpected first message from Home Assistant")
        self.ws.send({"type": "auth", "access_token": _token()})
        answer = self.ws.receive()
        if answer.get("type") != "auth_ok":
            raise SystemExit("Home Assistant rejected the token in credentials/ha_token.txt")

    def call(self, message: dict):
        self.next_id += 1
        self.ws.send({"id": self.next_id, **message})
        while True:
            reply = self.ws.receive()
            if reply.get("id") == self.next_id:
                if not reply.get("success", False):
                    error = reply.get("error", {})
                    raise RuntimeError(f"{message['type']} failed: {error.get('code')} {error.get('message')}")
                return reply.get("result")


def main(argv: list[str]) -> int:
    confirm = "--confirm" in argv
    config = load_dashboard()
    problems = read_only_problems(config)
    if problems:
        print("The dashboard file is not read-only:")
        for problem in sorted(set(problems)):
            print("  -", problem)
        return 1
    cards = sum(len(view.get("cards", [])) + sum(len(sec.get("cards", [])) for sec in view.get("sections", []))
                for view in config["views"])
    print(f"{DASHBOARD_FILE.name}: {len(config['views'])} view(s), {cards} cards, read-only check passed")
    if not confirm:
        print(f"Dry run. Add --confirm to create/update the dashboard '{URL_PATH}' on {BASE_URL}.")
        return 0
    try:
        ha = HA()
        existing = {d["url_path"]: d for d in ha.call({"type": "lovelace/dashboards/list"})}
        if URL_PATH in existing:
            print(f"Dashboard '{URL_PATH}' exists; replacing its configuration.")
        else:
            ha.call({"type": "lovelace/dashboards/create", "url_path": URL_PATH, "title": TITLE,
                     "icon": ICON, "show_in_sidebar": True, "require_admin": False, "mode": "storage"})
            print(f"Created dashboard '{URL_PATH}'.")
        ha.call({"type": "lovelace/config/save", "url_path": URL_PATH, "config": config})
        if URL_PATH in existing and existing[URL_PATH]["title"] != TITLE:
            ha.call({"type": "lovelace/dashboards/update", "dashboard_id": existing[URL_PATH]["id"],
                     "title": TITLE})
            print(f"Renamed dashboard to '{TITLE}'.")
        print(f"Saved. Open {BASE_URL}/{URL_PATH}")
        ha.ws.close()
    except HAUnreachable as err:
        print("UNREACHABLE:", err)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

"""Small read-only Home Assistant REST client for ac-adaptive.

Reads the token from credentials/ha_token.txt in this repo. Never prints it.
Only GET requests are exposed here. Anything that changes the site (climate services,
ai_task.generate_data, package installs) must go through a separate, approved command.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE_URL = "https://aj9.iotera.cc"
TOKEN_FILE = Path(__file__).resolve().parent.parent / "credentials" / "ha_token.txt"
USER_AGENT = "ac-adaptive/1.0"


class HAUnreachable(RuntimeError):
    """HTTP 530 or a connection error: the HA server is down. Do not retry in a loop."""


def _token() -> str:
    token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit(f"{TOKEN_FILE} is empty. Paste a Home Assistant long-lived token into it.")
    return token


def get(path: str, timeout: int = 30):
    request = urllib.request.Request(
        BASE_URL + path,
        headers={"Authorization": "Bearer " + _token(), "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        if err.code in (502, 503, 504, 530):
            raise HAUnreachable(f"HTTP {err.code}: Home Assistant looks down") from None
        raise
    except urllib.error.URLError as err:
        raise HAUnreachable(f"connection error: {err.reason}") from None


def state(entity_id: str) -> dict:
    return get("/api/states/" + entity_id)


def main(argv: list[str]) -> int:
    """`python tools/ha_client.py [entity_id ...]` prints version and entity states."""
    try:
        print("Home Assistant", get("/api/config").get("version"))
        for entity_id in argv:
            s = state(entity_id)
            print(entity_id, "=", s["state"], "| changed", s["last_changed"])
    except HAUnreachable as err:
        print("UNREACHABLE:", err)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

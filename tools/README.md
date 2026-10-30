# tools/

Helper scripts for the live Home Assistant. Run them from the repo root: `python tools/<script>.py`.

| Script | What it does | Approval |
|--------|--------------|----------|
| `ha_client.py` | Read-only REST client. `python tools/ha_client.py [entity_id ...]` prints the HA version and the states | None (read-only) |
| `count_people_test.py` | Asks Gemini to count people in camera frames (default `camera.2nd_floor`), compares with a real count the user gives, flags low-confidence and "0 while Frigate sees people" answers, prints a PASS/FAIL verdict (rule in `docs/plan-and-test.md`) | **Explicit approval before every run**: it uses Gemini quota and sends frames to Google |
| `build_dashboard.py` | Writes `dashboards/ac_adaptive_lt2.yaml` from Python (offline, touches only this repo) | None |
| `push_dashboard.py` | Creates or updates the storage dashboard `ac-adaptive-lt2` over the HA WebSocket API. Without `--confirm` it only validates (dry run). Refuses a dashboard with a button-card that has an entity or lacks explicit actions, any action other than `none`, `more-info` or `navigate`, a thermostat or entity card, or JavaScript that mentions `callService`, `fetch(` and similar | **Explicit approval** with `--confirm`: it changes the live HA (that one dashboard only) |

Rules:

* The token is read from `credentials/ha_token.txt` (gitignored). Scripts must never print or log it.
* Scripts here are read-only unless their table row says otherwise. A script that calls a `climate` service or installs a package must say so in its docstring and refuse to run without a confirmation flag.
* HTTP 530 from the proxy means HA is down. Scripts raise `HAUnreachable`; do not retry in a loop.
* Temporary one-off scripts go in your own scratch folder, not here.

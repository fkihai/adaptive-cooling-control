# Adaptive Cooling Control (ac-adaptive)

Adjusts the air conditioner temperature and fan speed to the number of people in a room, on Home Assistant (HA) at <https://aj9.iotera.cc>. The first pilot is floor 2 ("Lantai 2").

How it works, in short: Frigate says whether the floor is occupied. While it is, Gemini counts the people in a camera frame every 10 minutes. The count becomes a level (empty, few, normal, busy), and each level maps to a temperature and fan speed per AC. An optional second package sends that setting to the ACs; each unit has its own switch, and middle and right are live while left stays off.

**Status:** see [docs/status.md](docs/status.md). Nothing here changes a real AC or the live HA until the user approves it.

## Contents

| Path | What it is |
|------|------------|
| [packages/](packages/) | The two HA packages that go to `/homeassistant/packages/`: `adaptive_cooling_lt2.yaml` (count and recommendations, never touches an AC) and `adaptive_cooling_lt2_control.yaml` (optional, one file for left, middle and right, one switch per unit) |
| [docs/implementation-guide.md](docs/implementation-guide.md) | How it works; installing, testing and tuning |
| [docs/plan-and-test.md](docs/plan-and-test.md) | Phases, exit criteria, test cases and results |
| [docs/working-rules.md](docs/working-rules.md) | Approvals, live HA access, quota and privacy, repo rules |
| [docs/status.md](docs/status.md), [docs/decisions.md](docs/decisions.md), [docs/live-site.md](docs/live-site.md) | Current status, decisions with their reasons, and facts about the live site |
| [tests/](tests/) | Offline tests on Home Assistant Core with fakes |
| [tools/](tools/) | Helper scripts for the live HA. See [tools/README.md](tools/README.md) |
| [run.py](run.py) | `python run.py check` and `python run.py test` |
| [AGENTS.md](AGENTS.md) | Instructions for coding agents |

`credentials/` holds the HA token and is not committed ([how to create it](credentials/README.md)).

## Run the offline tests

They need Python 3.14 and use no live HA, Gemini or AC.

```bash
python3.14 -m venv .venv
.venv/Scripts/python -m pip install -r tests/requirements-test.txt   # Windows; .venv/bin/python elsewhere
.venv/Scripts/python run.py check   # HA configuration check of both packages
.venv/Scripts/python run.py test    # all tests
```

Installing on the live HA is described in [docs/implementation-guide.md](docs/implementation-guide.md) step 4 and needs the user's approval first.

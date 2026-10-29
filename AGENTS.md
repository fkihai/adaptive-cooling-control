# Adaptive cooling control: agent instructions

**ac-adaptive** adjusts the air conditioner temperature and fan speed to the number of people in a room, on Home Assistant (HA). This repo holds the design, the HA YAML packages, the tests and helper scripts. The first pilot is **floor 2** ("Lantai 2").

## Start of every session

1. Read [docs/status.md](docs/status.md): what is live, what is in progress, what the user is waiting for.
2. Read [docs/working-rules.md](docs/working-rules.md) and the detail file for what you work on (see "Where things are").
3. Before you end a session in which something changed, update `docs/status.md` with absolute dates.

## Never, without the user's explicit approval

* Call any `climate.*` service that changes a real AC. No AC is controlled until the user has approved that named AC.
* Call `ai_task.generate_data` (Gemini quota; sends a camera frame to Google), or save camera frames to disk.
* Install or change a package on HA, create helpers, or restart HA.
* Change any HA configuration this project did not create (other automations, Frigate, LLM Vision, other packages).
* Print, log or copy the token in `credentials/ha_token.txt`.
* Retry in a loop on HTTP 530: the HA server is down. Stop and tell the user.

Do not infer one approval from another. Details: [docs/working-rules.md](docs/working-rules.md).

## Where things are

| File | Read it when |
|------|--------------|
| [docs/status.md](docs/status.md) | Start of every session |
| [docs/working-rules.md](docs/working-rules.md) | Approvals, live HA access, quota and privacy, repo rules |
| [docs/live-site.md](docs/live-site.md) | Before any call to the live HA: entities, quirks |
| [docs/decisions.md](docs/decisions.md) | You need the reason behind a design choice, or want to change one |
| [docs/implementation-guide.md](docs/implementation-guide.md) | How it works; installing, testing or tuning |
| [docs/plan-and-test.md](docs/plan-and-test.md) | Phases, exit criteria, test cases, results |
| [packages/](packages/) | The two HA packages (count; optional control for left, middle and right) |
| [tests/](tests/) and `run.py` | Offline tests: `python run.py check`, `python run.py test` |
| [tools/README.md](tools/README.md) | Before using or adding a helper script |
| [credentials/README.md](credentials/README.md) | SSH key, host, port and the `ssh`/`scp` commands |

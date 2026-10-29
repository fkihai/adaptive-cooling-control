# Working rules

Full rules for anyone (person or agent) working on ac-adaptive against the live Home Assistant (HA). The short list of rules that must never be missed is in [../AGENTS.md](../AGENTS.md).

## Live Home Assistant access

* REST API `https://aj9.iotera.cc/api/`, WebSocket `wss://aj9.iotera.cc/api/websocket`. Time zone Asia/Jakarta (WIB, UTC+7); give times in WIB. HA 2026.7.1.
* Read the token from `credentials/ha_token.txt` for each call (how to create it: [../credentials/README.md](../credentials/README.md)). Never print it, log it or copy it anywhere. `credentials/` is gitignored.
* Send a custom User-Agent (for example `ac-adaptive/1.0`); the site's proxy rejects the default urllib one.
* HTTP 530 from the proxy means the HA server is down (the tunnel has nothing behind it). Stop and tell the user; do not retry in a loop.

## SSH

* Terminal & SSH add-on, host alias `ha-lt2`, only from the office network. Address and port are kept only in the gitignored `credentials/ssh_config`; never write them in a tracked file. Use this repo's key; setup and commands are in [../credentials/README.md](../credentials/README.md). Always use `ssh -F credentials/ssh_config ha-lt2 ...` (it sets BatchMode, IdentitiesOnly and the pinned known_hosts).
* SSH is for reading `/homeassistant` and installing or updating **this project's** two packages in `/homeassistant/packages/`. Both still need the package-install approval.
* Never edit other files on the site over SSH (other packages, `configuration.yaml`, `automations.yaml`, add-on options, Frigate config, `secrets.yaml`) and never print file contents that can hold secrets.
* Never create a subdirectory inside `/homeassistant/packages/`. The site loads it with `!include_dir_named`; a directory there made reloads silently keep the old configuration on 2026-10-29. Keep backups in `/homeassistant/_backup_*` instead.

## Shared Home Assistant

This HA also runs other automations, Frigate, LLM Vision and other things this project did not create, and the Gemini quota is shared.

* Change only what this project created: the two packages in `packages/` and the helpers, sensors and automations they define.
* Do not edit, disable or reload anything else. In particular do not touch the Frigate configuration, LLM Vision settings, or other packages and automations.
* Do not depend on entities that belong to other automations (for example another automation's presence sensor): their owners may change them without notice. Read the raw sensor (`binary_sensor.2nd_floor_person_occupancy`) and build our own, as the count package does.

## What needs approval

| Action | Approval |
|--------|----------|
| Read states, history, services, registries, automation configs, the system log; run the configuration check | None |
| Install or change a package (includes saving a copy of the replaced file, the configuration check and the minimum reloads), create helpers | Once per concrete scope |
| Restart HA | Explicit |
| `ai_task.generate_data` (Gemini quota; sends a camera frame to Google) | Explicit, per run, with a call count |
| Turn the count switch on (starts scheduled Gemini calls) | Explicit |
| Any `climate.*` call that changes a real AC (temperature, fan, HVAC mode, power) | Explicit, per named AC |
| Save camera frames to disk | Explicit |
| Open a camera snapshot | Only when the user asks (it shows staff) |

Do not infer one approval from another. No AC is controlled until the user has approved that named AC, and the first command is observed at the physical unit.

## Quota and privacy

* Use the primary AI Task only (`ai_task.google_ai_task`). Do not use the second-account fallback or send test traffic through its key; other automations depend on it.
* Send frames straight from the camera. Do not store them unless the user approves; if stored, delete after 7 days.
* Tell the user before the first scheduled call that sends staff images to Google for a new purpose.

## Repo rules

* Every change to the YAML in `packages/` must also change the matching section of [implementation-guide.md](implementation-guide.md) in the same edit.
* Every YAML change must pass `python run.py check` and `python run.py test` before it is installed.
* Keep each fact in one place: how it works in the guide, phases and results in [plan-and-test.md](plan-and-test.md), today's state in [status.md](status.md), reasons in [decisions.md](decisions.md), site facts in [live-site.md](live-site.md).
* Put temporary scripts and outputs in your own scratch folder, not in the repo.
* Commit or push only when the user asks.

# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-30

First tagged release of the floor 2 pilot.

### Added

- People counting from a Frigate-triggered camera frame through the primary
  Gemini AI Task, with a 30-minute freshness guard and a safe level for stale
  counts.
- Level-to-setting recommendations for the three floor 2 ACs (Sharp Kiri, Sharp
  Tengah and LG Kanan), with per-AC temperature ranges and fan names.
- Optional live control package for left, middle and right: one control switch
  per unit, one shared apply script, and thin per-unit automations.
- Safety gates for work hours, occupancy, count freshness, fresh power reports,
  cooling mode, setpoint range, fan support, a 10-minute rate limit and a
  30-minute manual pause.
- Manual-change detection from Home Assistant user context, which turns the
  unit's control switch off and records the last manual change.
- 15-minute power check with a persistent notification when a fresh report
  shows the AC is no longer running.
- `AC Adaptive` dashboard with AC cards, 24-hour setpoint and people charts,
  activity timeline and 7-day summaries.
- Push notifications for settings sent by the automation and a daily weekday
  summary.
- `sensor.ac_lt2_activity`, a trigger-based template sensor that records sent
  settings, control switch changes and people peaks without calling services.
- Read-only HA client and dashboard build/push helper scripts.
- Offline test suite on Home Assistant Core with fake camera, AI Task, climate
  services and power sensors.

### Changed

- Work hours are Monday to Friday, 07:00-18:00 WIB.
- Normal level is 3 to 4 people: 18 C on the left Sharp, 20 C on the middle
  Sharp and the right LG, all at fan Medium.
- Control switches restore their last state after a Home Assistant restart.

### Fixed

- Late or unchanged power reports no longer switch control off; freshness uses
  `last_reported` instead of `last_changed`.
- Only the latest accepted count drives the AC, so a partially written count
  can no longer produce a stale target.
- Dashboard chart time axis renders `HH:mm` labels at ApexCharts' actual tick
  times; the three temperature series share one Y axis and aligned plots.
- Long dashboard notes wrap instead of being cut off.
- Test harness sets up the `script` domain so the shared apply script is found.

[1.0.0]: https://gitlab-work/intellivision/adaptive-cooling-control/-/tags/1.0.0

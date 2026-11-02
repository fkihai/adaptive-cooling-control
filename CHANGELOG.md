# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-11-02

### Added

- Independent Lantai 1 workspace pilot: two LG ACs with their own count and
  control packages generated from the Lantai 2 rules, separate helpers, work-hours
  schedule, activity history, phone pushes and per-AC bell IDs. Counting is live
  (first scheduled answer 5 people at 95% confidence) and LG Kiri control is live;
  LG Kanan stays off because the unit is off and its power plug is silent.
- The LT1 tab now has read-only summary, AC cards, 24-hour charts and a change
  timeline. Its two-unit layout omits the room temperature tile (no LT1 sensor).
  Added offline tests for the two floors, including a generator drift check.
- Dashboard tab order is LT1 then LT2. LT1 push notifications open `/lantai-1`
  and LT2 push notifications and summaries open `/lantai-2` explicitly.
- A setting sent by the automation is also shown in the Home Assistant
  notification bell, with the same title and text as the phone push. It uses one
  fixed `notification_id` per AC (`ac_lt2_left`, `ac_lt2_middle`,
  `ac_lt2_right`), so a new setting of an AC replaces that AC's entry (and its
  time) and other notifications are not buried by more than three entries. Nothing is
  shown for `armed`, a manual change or a user's own edit.

### Changed

- Dashboard: the "AC menyala" summary tile is replaced by a room temperature and
  humidity tile at the far right, read from the 2nd Floor Workspace sensor. It
  shows two 30 px values on one row and only the age of the report ("5 hari
  yang lalu"), in yellow after 3 hours, or "-" when the sensor is unavailable.
  No room name and no "data lama" label.
- Dashboard: the "Orang terbanyak per hari", "Perubahan setelan" and "Tentang
  data ini" cards are removed from the page. Only the UI changed; the data stays
  in `sensor.ac_lt2_activity` and the card code stays in the builder, unplaced.

## [1.1.0] - 2026-11-02

### Added

- `ac_lt2_manual_resume` turns a unit's control switch back on after a manual
  Home Assistant change, inside work hours only. Power-check and deliberate
  switch-offs are not resumed.
- The activity timeline groups events by day, with a header per date ("Hari
  ini", "Jumat · 30 Oktober 2026"). Events without a stored day count as today.
- Tests for the day grouping, for the daily peak outside work hours, and for no
  daily summary on a day that is not in the schedule.

### Changed

- Manual pause is now 60 minutes (was 30) in the apply guard and the status
  texts.
- The daily summary push no longer uses a fixed 18:05 and a weekday list. It is
  sent 5 minutes after `schedule.ac_adaptive_hours` turns off, so the schedule
  is the only place that says which days and hours count. With the current
  Monday to Friday 07:00-18:00 schedule it still goes out at 18:05.
- The activity card subtitle reads "Perubahan terbaru" and the empty text no
  longer says "hari ini".
- Documents refer to `schedule.ac_adaptive_hours` instead of "Mon-Fri".
- New people-to-setting rule, the same for the left, middle and right ACs:
  1 person 22 C, 2 to 3 people 20 C, 4 or more people 18 C, and an empty room
  27 C. The fan is High at every level (it was Low, Low, Medium, High).
  Settings: `few_max` 1, `normal_max` 3, `temperature` `[27, 22, 20, 18]`, `fan`
  `[High, High, High, High]`. The left Sharp is no longer colder than the other
  two at the normal level.
- Behaviour is unchanged: an empty room (27 C) is only a suggestion and no
  command is sent, a count of 0 while the 15-minute hold is on counts as "few"
  (22 C), and a stale count uses the normal level (20 C).
- Tests use 2 people as the normal level and 4 people as the busy level, and a
  new test checks that an empty room suggests 27 C but sends no command.

### Fixed

- The activity card no longer shows an earlier day's sends under a static "Hari
  ini" header (a Friday 17:20 command looked like Monday's).
- The 7-day people card no longer records a peak on days outside the schedule.
  On Saturday 2026-10-31 Frigate saw someone and `sensor.ac_lt2_people` showed
  Friday's last count, which was stored as that day's peak. A value now counts
  only while the schedule is on and the count is at most 30 minutes old.
  `sensor.ac_lt2_activity` also reacts to the count commit marker so the first
  count of a morning is not missed. AC control was never affected.

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

[1.2.0]: https://gitlab-work/intellivision/adaptive-cooling-control/-/tags/1.2.0
[1.1.0]: https://gitlab-work/intellivision/adaptive-cooling-control/-/tags/1.1.0
[1.0.0]: https://gitlab-work/intellivision/adaptive-cooling-control/-/tags/1.0.0

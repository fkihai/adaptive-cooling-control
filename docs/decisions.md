# Decisions

Each entry: the decision, the evidence, and what would change it. Dates are absolute.

## 2026-10-28: Gemini counts people, Frigate only triggers

* **Decision:** the people count used for AC levels comes from a Gemini image question. Frigate's occupancy sensor decides "someone is there / the room is empty" and triggers a count.
* **Evidence:** on 2026-10-28 around 11:20 WIB Frigate's `sensor.2nd_floor_person_count` showed 1 while the user said at least 4 people were present and all of them are in the camera's view. Over 2026-10-21 to 2026-10-28 working hours the count was 4 or more for about a minute a day. Frigate detects at 640x360 and drops a person who sits still after roughly 40 to 60 seconds, so seated staff are under-counted.
* **Cost:** about 50 calls a day for one floor, on the primary AI Task only.
* **Would change it if:** the count test shows Gemini is not accurate either, or the daily quota is a problem. Alternatives then: HD frames, a radar presence sensor, or a Frigate zone and model change (not in scope here).

## 2026-10-29: camera source is `camera.2nd_floor`; ignore a 0 while Frigate sees people

* **Decision:** Gemini gets its frame from `camera.2nd_floor`, the Frigate feed that other automations on the site already use. `camera.cctv_lt2` is not used. A Gemini count of 0 is ignored while `binary_sensor.2nd_floor_person_occupancy` is on.
* **Evidence:** the user says floor 2 has one physical camera, so `camera.2nd_floor` (Frigate feed) and `camera.cctv_lt2` (recorder feed) are presumed to be the same view; this was not compared on the same frame. With 4 people present, `camera.2nd_floor` gave 0, 4, 4 and then 4, 4, 4 (Frigate read 1 every time). The single 0 came with confidence 100, so the confidence threshold does not catch it. Per-round results: [plan-and-test.md](plan-and-test.md) phase 2.
* **Pass rule for a 3-round run:** at least 2 of 3 answers within 1 of the real count. Chosen with the user because the package uses only the latest accepted answer and ignores bad frames, so one wrong answer does not change the level (the earlier `max(prev, last)` rule was dropped on 2026-10-29, see below).
* **Would change it if:** the pilot shows repeated 0 or low counts from `camera.2nd_floor`; then compare `camera.cctv_lt2` (it may be sharper; its resolution was never checked) on the same head count.

## 2026-10-29: levels and recommended settings

* **Decision (with the user):** 4 levels. Empty 27 C / Low; few (1 to 2 people) 26 C / Low; normal (3 to 5) 20 C / Medium; busy (6 or more) 18 C / High. Every AC has its own entry (`left`, `middle`, `right`) with its own ranges, temperatures, fans and temperature limits, in one `SETTINGS` block of the package; the three start with the same numbers. Names in the package are English (the user asked for it).
* **Evidence:** floor 2 usually has 4 people a day (user); Gemini answered 3 or 4 for 4 people, so the "normal" range 3 to 5 holds both. The user said the room already feels cold and chose the low values 20 and 18 C; there is no comfort data behind them.
* **Limits:** the Sharp ACs cannot go below 18 C (LG: 16 C); each recommendation is clamped to its AC's own limits. The count package sends nothing, so the numbers can still change freely. Live control needs a comfort check and the user's approval per AC.
* **Would change it if:** the pilot shows the level flipping often, or staff report the recommended setting as too cold or too warm.
* **Superseded 2026-10-29** by "normal per AC" below: normal is 3 to 4 people, not 3 to 5, and the normal temperature now differs per AC.

## 2026-10-29: normal level is 3 to 4 people at 18 C (supersedes the 20 C normal; itself superseded by "normal per AC" below)

* **Decision (user, after the first accepted counts):** normal (3 to 4 people) now asks for 18 C with fan Medium; busy (5 or more) stays 18 C with fan High. Empty 27 C / Low and few (1 to 2) 26 C / Low are unchanged.
* **Why:** floor 2 usually has 4 people, and the user wants the coldest setting at that usual occupancy. 18 C is the Sharp's lowest setpoint, so normal and busy now differ only in fan speed.
* **Would change it if:** staff report 18 C as too cold or the room overcools; then raise the normal temperature again and re-run the offline tests before installing.

## 2026-10-29: live Sharp middle pilot, no shadow week

* **Decision:** prepare a separate optional control package for `climate.ac_sharp_lt_2_tengah`. Installation requires separate approval. Both the count switch and live-control switch stay off until individually enabled; the live-control switch reset off after a restart (superseded 2026-10-29: the switches now restore their last state, see below). The user decided no shadow week is needed; offline checks and the first-command approval still apply.
* **Constraints:** only while the Sharp is cooling and its plug is above 50 W with a fresh reading, during work hours with an occupied floor and a fresh accepted count. Only set temperature and fan; never send on/off. Record attempts before sending IR; do not resend an unchanged target automatically. Pause and disable on a direct HA user change; a physical remote cannot be detected. A power check after 15 minutes can confirm only that it is still on, not that it received the temperature/fan command. No automatic IR retries.
* **Evidence:** `climate.ac_sharp_lt_2_tengah` reports `Auto/Low/Medium/High` and 18–30 C. The power sensor reports about every 10 minutes and measures only on/off, not setpoint/fan. See [live-site.md](live-site.md).
* **Would change it if:** the first command fails at the physical unit, the sensor reports stale data, the counting automation is unreliable, or staff find the chosen setpoint uncomfortable. Turn the live switch off before changing control rules.

## 2026-10-28: own presence sensor

* **Decision:** build `binary_sensor.ac_lt2_occupied` from `binary_sensor.2nd_floor_person_occupancy` with its own off-delay.
* **Why:** HA already has `binary_sensor.floor2_staff_present`, a template owned by another automation package (Frigate occupancy plus a 390 s hold) whose hold time was still being tuned. Depending on it would let a change there alter AC behaviour without notice.
* **Data:** in 2026-10-21 to 2026-10-28 working hours the held sensor was off 1 to 86 minutes a day, raw Frigate occupancy 59 to 243 minutes a day.

## 2026-10-28: no auto-off in the pilot

* **Decision:** the count package computes and shows a recommended setting but never calls a `climate` service. The pilot never turns an AC off when the room is empty; level 0 means an energy-saving setting.
* **Why:** the ACs are controlled by Broadlink IR, which is one-way. HA cannot tell whether a command arrived, and manual remote changes are invisible except through the power sensor. A wrong "off" with people seated is worse than wasted energy.

## 2026-10-28: pilot scope

* Floor 2, temperature and fan speed. Floor 2 has three ACs: Sharp LT2 kiri, Sharp LT2 tengah and LG LT2. The first live AC will be Sharp LT2 tengah.

## 2026-10-29: normal per AC (left 18 C, middle and right 20 C)

* **Decision:** normal (3 to 4 people) is 18 C on the left Sharp and 20 C on the middle Sharp and the right LG, fan Medium on all three. Empty 27 C / Low, few (1 to 2) 26 C / Low and busy (5 or more) 18 C / High stay the same for every AC. `few_max` 2 and `normal_max` 4 are the same for all three.
* **State as deployed:** `packages/adaptive_cooling_lt2.yaml:97` (left `[27, 26, 18, 18]`), `:105` and `:113` (middle and right `[27, 26, 20, 18]`), fans `[Low, Low, Medium, High]` on all three. The split was already in the file when this entry was written; the reason for it was not recorded, so treat it as unconfirmed and ask the user before relying on it.
* **Why it matters:** the level table in the guide and the plan must show per-AC values. A single "normal = 18 C" statement is wrong for middle and right.
* **Would change it if:** staff report either unit as too cold or too warm; then change that AC's `temperature` list only, keep `min_temp`/`max_temp` unchanged, and re-run the offline checks before installing.

## 2026-11-02: new people-to-temperature rule, fan always High (supersedes "normal per AC")

* **Decision (user):** 0 people 27 C, 1 person 22 C, 2 to 3 people 20 C, 4 or more people 18 C, fan High at every level, the same for left, middle and right. In the settings: `few_max: 1`, `normal_max: 3`, `temperature: [27, 22, 20, 18]`, `fan: [High, High, High, High]`.
* **Behaviour deliberately unchanged (user: "behavior jangan diubah, cukup range-nya"):** level 0 (27 C) is only a suggestion; the control package still sends nothing while the room is empty. A count of 0 while the 15-minute hold keeps the room occupied is level 1 (22 C), and a stale count is level 2 (20 C). The right LG's 16 C floor and the Sharps' 18 C floor do not clip any of these values.
* **Why it matters:** the pilot AC settings are now colder at low occupancy (1 to 2 people: 26 C / Low before, 22 C or 20 C / High now) and 4 people is now the busy level, so expect more cooling and fan noise.
* **Would change it if:** staff report the rooms too cold or the fan too loud, or the power bill rises; change `temperature` and `fan` only.

## 2026-10-29: per-unit switches restore their last state (no `initial:`)

* **Decision:** none of the helpers created by the two packages has `initial:`, including `input_boolean.ac_lt2_left/middle/right_control_enabled` and `input_boolean.ac_adaptive_count_enabled`. After a restart HA restores the last state instead of forcing every switch off.
* **Why:** an `initial:` value is applied again on every restart and on every reload of the helper domain, so a restart during the working day would silently stop control (and an `initial: false` would look like a failure), and a reload would fight the user's choice.
* **Consequence:** the first install still starts with every switch off, because a new `input_boolean` has no saved state. Rolling back therefore means turning the switch off explicitly, not restarting HA.
* **Would change it if:** a restart is ever observed to re-enable control unexpectedly, or the user asks for a guaranteed-safe start. Then add `initial: false` to the three control switches and accept that a restart pauses control.

## 2026-10-30: dashboard is read-only; push only for what the automation sent

* **Decision (user):** a separate dashboard `AC Adaptive LT2` (url `ac-adaptive-lt2`, own storage dashboard, nothing existing is touched). Each AC card shows setpoint, mode and fan like the thermostat popup but with **no control**: a `modern-circular-gauge` plus Mushroom chips, every tap, hold and double-tap action set to `none`, and no thermostat, climate or button card. The dashboard file is checked for this by `tools/push_dashboard.py` (refuses to push otherwise) and by tests.
* **Why:** the stock thermostat card cannot be made read-only, and a click on the old dashboard icons already sent real IR commands on 2026-10-29. The value shown is the last setting HA sent, not a read-back (IR is one-way); the page says so.
* **Recommendation is shown only when it differs** (user): `sensor.ac_lt2_<position>_status` is `ok` while the AC matches the target, otherwise one plain sentence (control off, outside work hours, waiting for a count or power report, 10-minute gap, manual pause, "akan diubah ke ..."). The checks follow the guards of `script.ac_lt2_apply_setting`; a manual pause is tested before "control off" because a manual change switches control off.
* **Push notification (user: phone `cph2457`, only changes made by the automation):** `ac_lt2_notify_setting_sent` fires when `input_text.ac_lt2_<position>_last_applied` becomes `<temp>|<fan>` with no user in the context. `armed`, `manual change` and a user's own edit send nothing. The wording says "dikirim" (sent), not "changed", for the same IR reason. The phone is the `notify_service` variable at the top of the automation. `ac_lt2_daily_summary` sends one push 5 minutes after `schedule.ac_adaptive_hours` turns off (18:05 with the current Mon-Fri 07:00-18:00 hours; no weekday list of its own) with the number of settings sent per AC (`input_number.ac_lt2_<position>_changes`, reset to 0 after the summary; an `input_number` rather than a `counter` because the counter domain has no reload service and would have needed an HA restart).
* **History:** 24 hours of setpoints and people in one chart, a logbook of the sent settings, and two 7-day column charts (peak people per day, settings sent per day) as the summary.
* **Would change it if:** the user wants to control the ACs from this page (then it needs its own approval, a confirmation dialog and a different rule in `docs/working-rules.md`), or more phones need the push.

## 2026-10-30: dashboard redesign with button-card and an activity sensor

* **Decision (user):** follow the mockup `Dashboard AC Lantai 2` (Main.dc.html), with the AC cards showing only the current mode and the current fan, and smaller text. Page title "AC Lantai 2" (not "Kontrol AC", because the page cannot control anything). System font, no new global resource. The 7-day peak chart follows the mockup, including its sentence, and fills from the day the sensor is installed.
* **Why button-card:** the mockup's ring, tiles and timeline are not available in stock cards, and `modern-circular-gauge` scales its text with the card (the first version looked oversized). `custom:button-card` (v7.0.1, already installed) renders HTML from a JavaScript template, with fixed px sizes. It is used **without an entity** so its default toggle action cannot exist, and the push tool and tests enforce that.
* **Why a sensor for the activity:** a card cannot read the Logbook or build a 7-day summary on its own. `sensor.ac_lt2_activity` is a trigger-based template sensor (attributes survive a restart) that records events and daily numbers. It only records.
* **Would change it if:** button-card changes how templates see `states`, or the user wants the full list of mode and fan choices shown (the mockup has it; the user chose active-only).

## 2026-10-30: dashboard fixes after the first screenshots

* **Decision (user, with a reference image):** shorten the texts, stop cutting text off, make the charts shorter, keep chart and activity on one row, and drop the mode and fan chip row in favour of the mode inside the ring (the reference shows the ring with the mode label, the number and the fan).
* **Why the layout broke:** in a sections view a section of `column_span` N is a grid of 12 x N columns, and a card without `grid_options` gets only 12 of them. HA also counted only three columns on the user's screen, so a separate 3-column chart section and a 1-column timeline section could not share a row. Now the chart (24 of 36 columns) and the timeline (12) are one section, and `max_columns` is 3.
* **Why the text was cut:** the stock button-card styles give its fields `white-space: nowrap; overflow: hidden; text-overflow: ellipsis`. The builder overrides this on the custom field.
* **Status wording** lives in the control package (`sensor.ac_lt2_<position>_status`), so Activity and History show the same short text as the dashboard.

## 2026-10-30: a manual pause auto-resumes after 60 minutes, inside work hours

* **Decision (user):** a HA user change still turns that unit's control switch off, but `ac_lt2_manual_resume` turns it back on 60 minutes later so adaptive control continues. The resume runs only while `schedule.ac_adaptive_hours` is on (now Mon-Fri 07:00-18:00 WIB; the schedule is the only place that says which days and hours); outside work hours the switch stays off and the next work-hour check resumes it. The pause guard in `script.ac_lt2_apply_setting` and the status text use the same 60 minutes.
* **Why:** the user wants a manual adjustment to win for a while, not to stop adaptive control for the rest of the day. The previous rule needed someone to re-enable the switch by hand, which left the LG Kanan off for hours on 2026-10-30 after a 20 -> 19 C change at 09:52:54 WIB.
* **How the resume is scoped:** only a switch whose `last_applied` is `manual change` is resumed. That marker is written only by the manual-pause automation. A power-check switch-off keeps the last real setting in `last_applied`, and a unit switched off after arming keeps `armed`, so neither is resumed. The timer restarts on every new manual change because `last_manual` is rewritten.
* **Why work hours only:** the user asked to keep the normal rule scope. Turning the switch on outside work hours would not send a command anyway (the apply script is gated by the schedule), but it would make the on/off state look active when no control can happen. If a pause ends outside work hours, the switch is resumed at the next weekday 07:00.
* **Would change it if:** the user wants the resume at any hour, a different wait, or no automatic resume at all. Changing the wait means the same value in the resume automation, the apply guard and the three status templates.

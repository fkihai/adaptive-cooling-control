# Plan and test plan

This file is the working plan for ac-adaptive, so any session can resume from it. The design is in [implementation-guide.md](implementation-guide.md), the reasons in [decisions.md](decisions.md), the current state in [status.md](status.md), the working rules in [working-rules.md](working-rules.md). Update the **Progress** table below whenever a phase moves.

## Goal

Adjust the temperature and fan speed of the floor 2 air conditioners to the number of people in the room. The count comes from Gemini (Frigate undercounts), Frigate only says whether the room is occupied. The plan goes from offline tests to a pilot on one AC.

## Progress

| # | Phase | Status (2026-10-29) |
|---|-------|---------------------|
| 0 | Design, repo, draft package, helper scripts | Done |
| 1 | Fix `count_people_test.py` (Frigate `unavailable`, HA down, bad-frame flags) | Done 2026-10-29 (checked with a mocked client) |
| 2 | Gemini people-count accuracy test | **Passed with caveats 2026-10-29** at head count 4 on `camera.2nd_floor`. A run at 1 to 2 people is still wanted but does not block phase 3 |
| 3 | Read-only survey of the floor 2 ACs | Done 2026-10-29; two questions for the user remain (see phase 3) |
| 4 | Finalise the package from the test result | **Draft finalised 2026-10-29** (per-AC levels, temperatures and limits in one settings block, no `initial:` resets, English names) |
| 5 | Offline tests for the counting and control packages | **Done 2026-10-29**: HA 2026.7.1 config checks (count alone, then count + control; the separate right-control file was later merged away) and 54 tests pass; 11 deliberate rule breaks (mutations) are all caught. Covered by fakes only: real Frigate, Gemini, IR and the site's timing are not |
| 6 | Install counting and control packages with both switches off | **Done 2026-10-29**: installed over SSH at 13:28 WIB with matching `sha256sum`, `ha core check` passed, all entities and 5 automations present, both switches off, no Gemini call and no climate command. Superseded the same day by the 2-file consolidation (7 automations, 3 units) |
| 7 | Pilot (middle Sharp and right LG live; left armed but off) | **Running since 2026-10-29 14:31:20 WIB.** Middle and right live since 16:24:12 (currently `20\|Medium`); physical setting confirmed by the user; the 15-minute power check passed. Pending: the same-target drill, the rollback drill, and the optional count run at 1 to 2 people |
| 8 | Extend to other rooms and offices (plug and play) | **BLOCKED: planning only. Do not start any part of it until the user approves.** Starts only after phase 7 succeeds |

**Gate rule:** do not install either package before the offline configuration and control checks pass. The first live command also requires explicit named-AC approval and observation at the unit.

## What is known (2026-10-29)

* Frigate showed 1 person while 4 were present, every time (2026-10-28 and 2026-10-29); all of them are in the camera's view. Frigate detects at 640x360 and drops people who sit still. Details: [decisions.md](decisions.md).
* Floor 2 has one physical camera (user, 2026-10-29). `camera.2nd_floor` is the Frigate feed (also used by other automations on the site); `camera.cctv_lt2` is a generic camera on the site's camera recorder, presumed to show the same view.
* Floor 2 has three ACs, all Broadlink IR: Sharp LT2 kiri, Sharp LT2 tengah, LG LT2. Entities and power sensors: [live-site.md](live-site.md).
* On 2026-10-28 the HA server was down for several hours. When it came back, the indoor cameras stayed `unavailable` until about 15:48 WIB and `camera.1st_floor` dropped again at 16:09. Check camera health before every test.
* The default Python on the laptop is 3.10. Home Assistant 2026.x needs Python 3.14 for the offline tests (phase 5); see `tests/requirements-test.txt`.

## Phase 1: fix the test script (done)

`tools/count_people_test.py` now:

* shows `n/a` for Frigate when the sensor is `unavailable` or `unknown`, and keeps going;
* stops the whole run on HTTP 502/503/504/530 or a connection error (HA down), instead of continuing the rounds;
* marks `LOW CONF` (confidence under 70) and `REJECTED` (count 0 while Frigate's occupancy sensor is on), the same rules as the package;
* ends with a PASS/FAIL verdict using the rule in phase 2. A failed call counts as a miss.

Checked offline with a mocked `ha_client` for: the two real runs of 2026-10-29, Frigate unavailable, HA down mid-run and at the state read, low confidence, one failed call, two failed calls. No live call was made for the check.

## Phase 2: Gemini people-count accuracy test (passed with caveats)

**Purpose:** decide whether Gemini counts well enough. This is the go/no-go for the project.

**Approval:** the user approved 6 `ai_task.generate_data` calls on 2026-10-28; since then the user has run 10 calls on 2026-10-29 (1 spot check, 3 runs of 3), plus possibly one from the removed circle script at about 09:33 WIB (the AI Task was last used then; it may also have been another automation). Ask for explicit approval, with a call count, before the next run. Each run sends frames to Google and uses quota; frames are not saved and not opened.

**Preconditions (check read-only first):**

1. `python tools/ha_client.py` prints the HA version (server up, token valid).
2. `camera.2nd_floor` is `recording` and `sensor.2nd_floor_camera_fps` is above 0.
3. `ai_task.google_ai_task` is available.
4. The floor has the head count you want to test. Between about 09:00 and 11:00 WIB it is usually busy.
5. The user gives the real head count right before the run and nobody enters or leaves during the roughly 1.5 minutes it takes.

**Run:**

```bash
python tools/count_people_test.py --confirm-approved 3 <real head count> camera.2nd_floor
```

**Record the result** under "Results" below: date, real count, per-round Frigate and Gemini counts, confidence, mean absolute error.

**Exit criteria (agreed with the user, 2026-10-29):** one run is 3 rounds on one camera.

| Result of one run | Decision |
|-------------------|----------|
| At least 2 of 3 answers within 1 of the real count | Pass |
| Only 1 of 3 within 1, or none | Fail. Look at the answers, then try another time or another frame source (`camera.cctv_lt2`); do not retry the same wording on the same frames |
| A failed call (error, low confidence) | Counts as a miss |

Why this is not stricter: the package uses the higher of the last two accepted counts and ignores bad frames (low confidence, or 0 while Frigate sees the floor occupied), so a single wrong answer does not move the level. The first draft of the criteria (mean error at most 1 and no answer off by more than 2) would have failed run 1 for one bad frame; the user judged that too strict.

### Results

All times WIB, 2026-10-29. Frames were sent straight from the camera to Gemini (`ai_task.google_ai_task`); none were saved or opened by the agent. The user ran the scripts and gave the real head count.

**Run 0, 09:19: spot check, `camera.cctv_lt2`.** Real count 2 (the user confirmed this camera shows floor 2). One call took 22.7 s. Gemini 2, confidence 95; Frigate `sensor.2nd_floor_person_count` 0. One sample at a low head count, not an accuracy test.

**Run 1, 09:52 to 09:54: `camera.2nd_floor`, real count 4.** Gemini mean absolute error 1.33, Frigate 3.00. 2 of 3 within 1 (pass).

| Round | Gemini | Confidence | Frigate | Note |
|-------|--------|------------|---------|------|
| 1 | **0** | 100 | 1 | "No people visible". Wrong; the frame was probably bad (not verified, the frame was not kept) |
| 2 | 4 | 95 | 1 | |
| 3 | 4 | 100 | 1 | |

**Run 2, 09:55 to 09:57: `camera.2nd_floor`, real count 4.** Gemini mean absolute error 0.00, Frigate 3.00. 3 of 3 within 1 (pass).

| Round | Gemini | Confidence | Frigate |
|-------|--------|------------|---------|
| 1 | 4 | 95 | 1 |
| 2 | 4 | 95 | 1 |
| 3 | 4 | 95 | 1 |

**Run 3, 10:09 to 10:10: `camera.2nd_floor`, real count 4.** Gemini mean absolute error 0.33, Frigate 3.00. 3 of 3 within 1 (script verdict PASS).

| Round | Gemini | Confidence | Frigate |
|-------|--------|------------|---------|
| 1 | **3** | 100 | 1 |
| 2 | 4 | 100 | 1 |
| 3 | 4 | 100 | 1 |

**Reading.**

* All three runs pass the rule. Across the 9 answers on `camera.2nd_floor`, 7 were exactly right, one said 0 and one said 3; Frigate read 1 every time. Wrong answers carry confidence 100, so confidence cannot filter them.
* The answer of 0 with confidence 100 is why the package and the test script ignore a 0 while Frigate's raw occupancy sensor is on.
* `camera.2nd_floor` and `camera.cctv_lt2` were never compared on the same head count; the choice of `camera.2nd_floor` rests on the user's instruction and on other automations already using it, not on a measured difference.

**Caveats:** only head count 4 on `camera.2nd_floor` (plus one sample of 2 on `camera.cctv_lt2`); the same people in the morning. One answer of 0 came back with confidence 100. Treat the pass as "good enough to start the pilot", not as proof. Still wanted, after the user approves 3 more calls: one run at 1 to 2 people (for example around lunch), and one at 6 or more if it happens. This does not block phase 3.

## Phase 3: read-only survey of the floor 2 ACs

Read, do not change anything:

1. Which `climate` entity drives each physical AC. Check `climate.ac_lg_2_2` against `climate.ac_lg`; ask the user which unit is which if the entities do not say.
2. For each AC: current mode, setpoint, `fan_modes`, `min_temp` and `max_temp`.
3. The power pattern of the three power sensors over the last 7 days (on-threshold, typical watts per fan speed). This is the check for "did the command arrive".
4. Where the 26.3 C temperature sensor is. Ask the user.

Record the result in [live-site.md](live-site.md).

**Done 2026-10-29** (nothing changed on the site). Details and numbers are in live-site.md, section "Floor 2 AC survey". What it means for the plan:

* HA's setpoint and fan are assumed values (IR is one-way), so the pilot must treat them as unknown and not as a read-back.
* Power distinguishes on from off only (Sharp tengah about 1000 W, LG about 600 W, standby under 30 W). It does not show the fan speed or setpoint, so a command can only be checked as "still on".
* The power sensors report about every 10 minutes, so the "check after 2 minutes" rule in the pilot phase has to change (see phase 7).
* Sharp tengah is used on weekdays from the morning into the evening (about 15 h a day), which is where level changes would matter most.

**Remaining site questions:** the location of the 26.3 C temperature sensor and what the Sharp middle unit is physically set to. The user confirmed the LG right entity is `climate.ac_lg_2_2` and read 18 C for Sharp middle and 16 C for LG right on the dashboard; those are not physical read-backs.

## Phase 4: finalise the package

Edit `packages/adaptive_cooling_lt2.yaml` and the matching part of `implementation-guide.md` in the same change.

* **Done 2026-10-29 with the user:** camera `camera.2nd_floor`; levels empty / few (1 to 2) / normal (3 to 5) / busy (6 or more); recommended temperatures 27 / 26 / 20 / 18 C and fans Low / Low / Medium / High. Reason for the ranges: floor 2 usually has 4 people and Gemini answered 3 or 4 for 4 people, so both land in "normal". The temperatures are low on purpose (the user says the room already feels cold) and are a hypothesis to test, not proven comfortable.
* **Changed 2026-10-29 at the user's request, after the count test:** normal is now 3 to 4 people at **18 C** / Medium, and busy is 5 or more at 18 C / High, so 3 or more people ask for the Sharp's coldest setpoint. The old normal (3 to 5 at 20 C) is superseded. Levels below normal are unchanged: empty 27 C / Low, few (1 to 2) 26 C / Low. Both are superseded later the same day: normal is now 3 to 4 people, 18 C on the left and 20 C on middle and right (see [decisions.md](decisions.md), "normal per AC").
* **Per AC:** one settings block with an entry for each of `left` (Sharp kiri), `middle` (Sharp tengah) and `right` (LG kanan). Each has its own `few_max`, `normal_max`, `temperature`, `fan`, `min_temp` and `max_temp`, and its own level and recommendation sensors (`sensor.ac_lt2_<position>_...`). The three start with the same numbers. The people count stays one number for the room. All names are English.
* **Done:** the `initial:` values were removed from the helpers so a restart does not erase the last count; the zero-count safeguard is in.
* **Offline check done (no HA):** the template logic was rendered with a fake HA for 16 head-count cases (empty, each range edge, 3 then 4, occupied with count 0, stale at 30 and 31 minutes, empty beats stale) plus a per-AC independence check (change only the right AC) and a temperature-limit check. This does not replace phase 5 or the HA configuration check; the real template engine and the YAML load on HA 2026.7.1 are not yet verified. In particular, whether a `variables:` block in a template block reaches all its sensors, and whether the nested `ac_settings` mapping behaves, is only documented, not tested on 2026.7.1.
* **Still open:**
  * Check each AC's own `fan_modes` before control exists (the Sharp ACs and the LG all list `Auto/Low/Medium/High` today).
  * Sharp's lowest setpoint is 18 C, so the busy level is at its floor; LG goes down to 16 C.
  * Confirm that `ai_task.generate_data` with `structure` inside an automation returns `result.data` on HA 2026.7.1 (one live call, covered by the first accepted count in phase 7 or a separate approval).

## Phase 5: offline tests

* Environment: Python 3.14 in a venv, with Home Assistant pinned to the version the site runs (2026.7.1) or the nearest that works. Check `pip show homeassistant` before trusting a run. How to run: [implementation-guide.md](implementation-guide.md) step 3b.
* `tests/` has a test configuration (`tests/fixtures/`), fake camera and AI Task (`tests/fakes.py`), `run.py check` (count alone, then count + control) and `run.py test`: `test_control.py` (contract tests), `test_count_runtime.py` (counting cases below) and `test_control_runtime.py` (control cases below), all on real HA 2026.7.1 with a fake camera, AI Task, climate services and power sensor on a frozen clock (`conftest.py`). On 2026-10-29 all 54 tests passed. As a check on the tests themselves, 11 rules in the YAML were broken on purpose one at a time (power gate, rate limit, manual pause, power freshness, stale gate, de-duplication, manual change switching control off, zero-with-Frigate guard, confidence check, minimum gap, occupied hold); every break made a test fail. The YAML was restored afterwards.
* Fakes: the camera, the Frigate occupancy sensor, and the AI Task returning scripted answers. Use a simulated clock.

**Cases to cover:**

| Case | Expected |
|------|----------|
| Room empty for 15 minutes | `ac_lt2_occupied` off, level 0 |
| Occupied, count accepted | `ac_lt2_people` = higher of the last two counts, level from the thresholds |
| Count 4, then a failed answer | The last count stays, level unchanged |
| Answer with confidence below 70 | Not written |
| Count older than 30 minutes while occupied | Level 2 and `stale` true |
| Switch `ac_adaptive_count_enabled` off | No AI Task call |
| Outside `schedule.ac_adaptive_hours` (now Mon-Fri 07:00-18:00) | No AI Task call |
| Two triggers within 4 minutes | Only one call |
| Count above 50 | Clamped to 50 |
| Level to recommended temperature and fan mapping | Matches the table in the guide |
| Floor 2 occupancy dips for less than 15 minutes | `ac_lt2_occupied` stays on |

**Control-package cases covered (all with fakes):** control switch off sends nothing; first command is set_temperature then set_fan_mode and never power or HVAC mode; each gate blocks the command (count switch off, power at or below 50 W, standby 20 W, floor not occupied, count stale, AC not in cool mode, stale power reading, outside working hours, fan not offered by the AC); an unchanged target is not resent; a new target waits 10 minutes from the last attempt; a user change in HA switches control off, pauses 60 minutes and is resumed automatically only inside work hours; a state change without a user does not; a power-check switch-off is not resumed; re-enabling sends the current setting once; a failed command is recorded and not retried; the 15-minute power check keeps control on while the AC draws power, and pauses it with a notification when power drops, goes silent or is unavailable.

**Not covered:** a physical IR remote change (invisible by design), real Broadlink delivery, the real power sensor's 10-minute rhythm, real Gemini answers, and HA restart behaviour of the helpers. The helpers deliberately have no `initial:`, so HA restores their last state after a restart; no test asserts that.

Exit criteria: configuration check passes and all tests pass. **Met 2026-10-29.**

## Phase 6: install packages with both switches off (done 2026-10-29)

Approved and done on 2026-10-29 at 13:28 WIB. **This record describes the first version (count + middle control + right control, 3 files).** At 16:31 WIB the two control files were consolidated into one `adaptive_cooling_lt2_control.yaml` for all three units, with 7 automations and one shared script; the count package gained the same `recommended_setting` target for the left unit. Record: both files copied with `scp`, remote `sha256sum` equal to the repo (`3b105ad3...` count, `2cc3243c...` control), `ha core check` passed, helpers/schedule/template/automation reloaded, no restart needed. All planned entities exist and `input_boolean.ac_adaptive_count_enabled` and `input_boolean.ac_lt2_middle_control_enabled` are `off`. The AI Task was not used and no `climate` service was called during the install. Note: automation entity ids come from the alias, not the `id` (`automation.ac_floor_2_middle_apply_people_based_setting` etc.), so reference them by `id` in docs and tests. The steps are in [implementation-guide.md](implementation-guide.md) step 4; this phase is done when:

1. Both files are in `/homeassistant/packages/`, their `sha256sum` matches the repo files, and `ha core check` passes.
2. The new entities exist and `input_boolean.ac_adaptive_count_enabled` and `input_boolean.ac_lt2_middle_control_enabled` are both off (read-only check).
3. No Gemini call and no climate command happened during the install.

Turning on the count switch is a separate approval (Gemini quota, frames sent to Google). Turning on the control switch and sending the first command to Sharp middle need explicit named-AC approval.

**Rollback:** delete the files and run the same reloads. The packages do not touch any other automation.

## Phase 7: pilot on Sharp floor 2 middle (started 2026-10-29)

**Bug found and fixed 2026-10-29.** At 15:10 the control sent 26 C / Low while the accepted answer was 4. Cause: the package published `max(prev, last)` while the automation wrote `prev` before `last`, so a partially updated pair dipped to 2. A second defect: the 15-minute power check used `last_changed` (when the watts changed), so an unchanged 1006 W reading looked stale and switched control off at 15:25. Both are fixed in the repo and covered by tests: only the latest accepted answer is used, temperature and fan are read as one `recommended_setting` target, freshness uses `last_reported`, a late report holds commands instead of switching control off, and the automation rechecks every minute so a pending target is sent once data recovers. 54 tests pass. Deployed and enabled on middle and right at 16:24:12 WIB (18 C / High for 5 people); left stays off until its plug reports again.

**Record so far, 2026-10-29.** The count switch was turned on at 13:32. Three scheduled counts ran and the user confirmed them correct: 13:40 = 3, 13:50 = 4, 14:00 = 3, 14:10 = 4, 14:30 accepted, while Frigate kept reading 1. At 14:00 the user changed Sharp middle through the dashboard on purpose: the manual-pause automation recorded it (user context, 14:00:06 to 14:00:10) and the control switch stayed off, so no automatic command was sent. The control switch was turned on at **14:31:20**, after the 30-minute pause expired, and the first live command went out: `set_temperature` 18 then `set_fan_mode` Medium. `input_text.ac_lt2_middle_last_applied` = `18|Medium`, `input_datetime.ac_lt2_middle_last_command` = 14:31:20, and the climate entity shows `cool` 18 C / Medium. Pending: the 15-minute power check, the physical check at the unit, and the safety drills.

**Rest of 2026-10-29 (same pilot).** The 15-minute power check passed: control stayed on after 16:24, and both units kept a fresh report. The user confirmed at the physical units that the settings were applied. At 16:31 the control file was consolidated to all three units (see the bug entry above) and deployed with matching `sha256sum`; at 16:41 the reloads were found not to apply, because a backup directory had been created inside `/homeassistant/packages/` (the folder is loaded with `!include_dir_named`). After moving it to `/homeassistant/_backup_20261029_1655`, every domain reloaded and the new entities appeared: `script.ac_lt2_apply_setting`, the left switch and helpers, and `automation.ac_floor_2_arm_the_three_units`. State at 16:42: people 3, middle and right `20|Medium` already applied at 16:34, left switch off, no duplicate command. At 16:50 one Gemini call took 78 seconds (trigger 16:50:00, result 16:51:18) with a single trigger and a single write, so it was latency, not a retry. Six old automation entities (`ac_lt2_middle/right_arm`, `..._manual_pause`, `..._check_power`) remain in the registry as `unavailable` after the consolidation; they do not run. The 17:0x docs audit corrected the level table, the switch restore behaviour, the 20-minute freshness and the entity/test counts in this file and the guide.

Needs explicit approval for each named AC. Both packages are installed since 13:28 WIB; the control package is now one file for left, middle and right. Middle and right were approved and switched on at 16:24:12; left stays off until its plug reports power again. A fresh install starts with every switch off, and a restart restores the last state.

* Work hours only, occupied, recent accepted count, and the unit in `cool` with a power reading over 50 W whose `last_reported` is younger than 20 minutes. Each automation targets only its own AC entity.
* At most one attempt every 10 minutes; no repeat when the last attempted automatic target is the same (also after a service failure). The last attempt and target are recorded before the first IR command. The climate entity's apparent setpoint is never treated as a physical read-back.
* Each unit has its own switch. A fresh install starts off; after a restart HA restores the last state because the helpers have no `initial:`. A direct HA user change turns that unit's switch off and blocks further automatic attempts for 60 minutes; inside work hours, `ac_lt2_manual_resume` then turns the switch back on so adaptive control continues. Power-check switch-offs and switches turned off deliberately are not resumed. A physical remote cannot be detected; turn the switch off manually after using one.
* After 15 minutes check that the power sensor still reports over 50 W and is fresh. Otherwise turn the master switch off and notify. **No automatic retry:** power confirms only on/off and cannot confirm temperature or fan. The 2-minute check and retry from the original plan were discarded after the power-sensor survey.
* Send only temperature and fan, never on/off. Check the unit's own range (Sharp 18–30 C, LG 16–30 C) and a supported fan mode before each attempt.

Test with the user present: approve and observe the first command at the physical unit, then verify power and comfort. Finish offline tests for both packages before installation. Installing the packages is not permission for scheduled Gemini calls or AC commands; each has its own approval.

**Daily read-only check during the pilot:** how many Gemini calls ran and how many were accepted, the level over time, any `stale` periods, and whether the power check paused control. The user gives a few real head counts a day at known times (a note is enough) to compare with `sensor.ac_lt2_people`.

**Quota:** about 50 to 60 calls a day. Stop and tell the user if the AI Task starts failing or other automations that use it are affected.

**Pilot is going well when:**

* The level matches the real head count in at least 90 percent of the user's checks.
* No `stale` period longer than 1 hour while the floor was occupied, outside camera or server outages.
* Staff do not report the recommended setting as too cold or too warm.
* No effect on other automations that use the same AI Task.

## Lantai 1 workspace pilot (approved scope 2026-11-02; prepared locally, not deployed)

* Scope: `camera.1st_floor` covers only 1st Floor Workspace; Front Office and meeting rooms are excluded. The two ACs are LG Kiri (`climate.ac_lg_lt_1_kiri`, power `sensor.0x60b763fffe1e5fc6_power`) and LG Kanan (`climate.ac_lg_lt_1_kanan`, power `sensor.0x60b763fffe1e380d_power`). Kanan is currently off and its power plug last reported 2026-10-28. The current controls do not send IR to an off AC; keep both control switches off until each unit is approved separately.
* `python tools/build_floor1_packages.py` generates `packages/adaptive_cooling_lt1.yaml` and `packages/adaptive_cooling_lt1_control.yaml` from the LT2 rules, omitting the middle unit. Both LGs use 16–30 °C; Kiri fan `High`, Kanan fan `high`. Independent schedule `schedule.ac_lt1_hours` starts Mon–Fri 07:00–18:00 WIB. The count timer is staggered five minutes behind LT2. The same phone and per-AC bell notifications use floor-specific tags and IDs. LT1 is the second tab in the existing dashboard and has no room-temperature tile because no LT1 sensor was found.
* Offline acceptance: `run.py check` for LT1 alone, LT2 alone and combined; runtime tests for off right AC, mapping, fan names, schedule, no empty-room command, left fake IR, manual pause and notification path; generator drift test; existing LT2 tests all pass. **Result 2026-11-02: 154 tests pass, configuration checks and dashboard dry run pass.**
* Installation approved and done 2026-11-02: both LT1 packages uploaded with matching SHA-256 hashes (`dd486775...` count, `08fb8739...` control); backup metadata `/homeassistant/_backup_20261102_pre_lt1` outside `packages/`; `ha core check` passed; reloaded only input_boolean, input_number, input_datetime, input_text, schedule, template, script and automation. LT1 counting and both control switches remained off. LT2 state snapshots were unchanged. Dashboard saved and read back with **LT1 | LT2** order, four sections each. The LT2 phone push and daily summary URL were separately updated (user approved) to `/ac-adaptive-lt2/lantai-2` since the root now opens LT1; its backup is `/homeassistant/_backup_20261102_pre_lt2_link`, `ha core check` passed and only automation was reloaded.
* Counting enabled 2026-11-02 15:26 WIB at the user's request (no separate three-call trial; logic is a copy of LT2). First scheduled count 15:35:13 returned 5 people at confidence 95; the user judged the counts good. Count runs at :05/:15/:25/:35/:45/:55 during work hours while occupied.
* **Control live for LG Kiri 2026-11-02 15:45:26 WIB (user approval for this named AC).** First IR: 16 °C -> 18 °C, fan High (target `18|High` for 5-6 people), status `ok`, one `changes today` count, one `ac_lt1_left` bell entry and one phone push. Physical confirmation by the user pending.
* **LG Kanan still off and not controlled.** The AC is off and its power plug last reported 2026-10-28, so it stays waiting for its own approval once it is running and reporting again. Do not infer its approval from LG Kiri.

## Phase 8: extend to other rooms and offices (plug and play)

> **BLOCKED. Planning notes only (written 2026-10-29).** Nothing below is approved or started. Do not build the generator, change the packages, rename entities or touch Home Assistant Areas for this phase until the user explicitly approves it. It also waits for phase 7 (the Sharp middle pilot) to succeed.

**Goal:** adding a room must not need hand-written YAML. An agent or a person follows the same steps and gets the same result.

**Decisions so far**

* **One Home Assistant per office** (user, 2026-10-29). The repo keeps one folder per office with that office's HA URL, token file, room data and generated packages. The Gemini quota is counted per office.
* **The unit is a room (an HA Area)**, not a floor. The site already has separate rooms with their own ACs (meeting rooms, floor 1, floor 2). To confirm with the user before starting.
* **Who adds rooms:** an agent or a person (user, 2026-10-29).

**Approach**

1. **Write the logic once**, as templates for the count package and for the per-AC control package. A data file (`sites.yaml`) holds only per-room data: camera, occupancy sensor, ACs with their power sensors and on-threshold, level settings, work hours. Anything not written falls back to a global default.
2. **`python run.py build`** generates the packages per room. **`python run.py test`** runs the whole test suite for every generated package. The generated package for floor 2 must be identical in behaviour to the one installed during phase 7 (same tests pass, same entities) before any other room is added.
3. **`python run.py discover <office> <area>`** (read-only) finds the room's devices from the HA Area and from device names, proposes the AC-to-power-plug pairs and the "AC is on" threshold from 7 days of power history, and runs a readiness check: camera alive, occupancy sensor present, every AC has a plug that reports, fan modes readable. A human confirms before anything is written to `sites.yaml`.

**Steps to add a room**

1. Put the room's devices in the right HA Area (changes HA; needs approval).
2. Run `discover` and confirm its result.
3. Run the Gemini count test for the room (needs approval, 3 calls per run).
4. Run `build` and `test`.
5. Install with every switch off (needs approval).
6. Turn on the count switch, then each AC's control switch, each with its own approval and the first command observed at the unit.

**What has to change in the current packages first**

* Entity names are floor 2 only (`ac_lt2_*`, `schedule.ac_adaptive_hours`). Decide a scheme such as `ac_<office>_<room>_*` and migrate floor 2 once.
* Control exists for Sharp middle only. It must become one control switch per AC, so each AC still needs its own approval.
* Work hours must be a per-office setting.
* A daily cap on Gemini calls per office (floor 2 alone uses about 50 to 60 a day on a quota shared with other automations).

**Prerequisite found on the live site (read-only check, 2026-10-29): HA Areas are not tidy yet.** HA has the floors `lantai_1` and `lantai_2` but no Area is attached to a floor. The entities this project uses are mostly in no Area:

| Entity | Area now |
|--------|----------|
| `camera.2nd_floor`, `binary_sensor.2nd_floor_person_occupancy` | none |
| `climate.ac_sharp_lt_2_kiri`, `climate.ac_sharp_lt_2_tengah` | none |
| the three AC power plugs (`sensor.0x60b763fffe1e451c_power`, `...1f48ee_power`, `...1e67ae_power`) | none |
| `climate.ac_lg_2_2` | 2nd Floor Workspace |
| `climate.ac_sharp_lt_2` (old leftover, state `unknown`) | 2nd Floor Workspace |
| `sensor.0xa4c13813795610e2_power` (Almo Smart Socket 3, not an AC plug) | 2nd Floor Workspace |

Looking devices up by Area today would return the leftover AC and the wrong plug and miss the real ones. The three AC plugs do have clear device names ("AC Sharp Kiri LT 2", "AC Sharp Tengah LT 2", "AC LG LT 2"), which `discover` can use to pair a plug with an AC. Tidying Areas changes the live HA and other automations may use them, so it needs the user's approval when the phase starts.

**Later, only if needed:** a custom integration with setup from the HA UI, so a technician can add a room without a laptop. It means rewriting the logic in Python and its tests, so it is not planned before the template approach has proven itself.

**Exit criteria (proposed):** a second room is added by following only the steps above, with no hand-written YAML, and its tests pass; the floor 2 packages still behave as in phase 7.

## Approvals at a glance

Full rules: [working-rules.md](working-rules.md).

| Action | Approval |
|--------|----------|
| Read states, history, registries | None |
| Gemini calls (`ai_task.generate_data`) | Explicit, per run |
| Install or change the package, config check, reloads | Once per concrete scope |
| Restart HA | Explicit |
| Switch the count automation on | Explicit |
| Any `climate.*` command | Explicit, per named AC |
| Open a camera image | Only when the user asks |
| Change any HA configuration this project did not create | Never |

## Resume checklist

1. Read [status.md](status.md) and this file's Progress table.
2. `python tools/ha_client.py` to check the server and token. HTTP 530 means the server is down; stop.
3. Check the floor 2 camera and Gemini (phase 2 preconditions).
4. Continue at the first phase that is not done.
5. At the end, update the Progress table and `status.md`.

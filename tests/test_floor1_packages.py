"""Offline invariants: isolated floor 1 generated from floor 2, no accidental duplicates."""

from pathlib import Path
import sys

import yaml


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_floor1_packages as builder  # noqa: E402


def test_generated_files_stay_in_sync_with_floor2_rules():
    for filename, generated in builder.generate().items():
        installed = yaml.safe_load((ROOT / "packages" / filename).read_text(encoding="utf-8"))
        assert installed == generated, f"{filename}: rerun python tools/build_floor1_packages.py"


def test_floor1_is_isolated_from_floor2():
    count, control = [builder.generate()[name] for name in (builder.COUNT, builder.CONTROL)]
    ids = [a["id"] for a in count["automation"] + control["automation"]]
    assert len(ids) == len(set(ids))
    assert len(control["input_boolean"]) == 2
    assert len([a for a in control["automation"] if a["id"].endswith("_apply")]) == 2
    assert all("lt1" in x for x in ids)
    assert set(count["template"][1]["variables"]["ac_settings"]) == {"left", "right"}
    assert set(count["template"][1]["variables"]["ac_settings"]["right"]["fan"]) == {"high"}
    assert count["template"][1]["variables"]["ac_settings"]["left"]["fan"] == ["High"] * 4
    for data in (count, control):
        text = str(data)
        assert "ac_lt2" not in text and "middle" not in text
        assert "ac_adaptive_hours" not in text
    assert count["automation"][0]["variables"]["camera_entity"] == "camera.1st_floor"
    assert control["automation"][-2]["variables"]["dashboard_path"] == "/ac-adaptive-lt2/lantai-1"


def test_floor1_deployed_entity_ids_do_not_collide_with_floor2():
    lt1, lt2 = [], []
    for floor, target in (("lt1", lt1), ("lt2", lt2)):
        for name in (f"adaptive_cooling_{floor}.yaml", f"adaptive_cooling_{floor}_control.yaml"):
            data = yaml.safe_load((ROOT / "packages" / name).read_text(encoding="utf-8"))
            for domain in ("input_boolean", "input_datetime", "input_text", "input_number", "schedule", "script"):
                target.extend(f"{domain}.{x}" for x in data.get(domain, {}))
            target.extend(f"automation.{a['id']}" for a in data.get("automation", []))
            for template in data.get("template", []):
                for kind in ("sensor", "binary_sensor"):
                    target.extend(f"{kind}.{e['unique_id']}" for e in template.get(kind, []))
    assert not set(lt1) & set(lt2)

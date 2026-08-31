#!/usr/bin/env python3
"""
AI Horses - validate.py

Checks a card file before you commit it. Catches structural errors and the
method rules the schema alone cannot enforce.

Usage:
    python validate.py CARDS/CT-2026-08-29-E.json
"""

import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA_DIR = os.path.join(HERE, "SCHEMA")


def parse_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def main():
    if len(sys.argv) != 2:
        print("Usage: python validate.py CARDS/<file>.json")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"Not found: {path}")
        sys.exit(1)

    try:
        card = json.load(open(path, encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL - not valid JSON: {exc}")
        sys.exit(1)
    print("JSON parses.")

    errors, warnings = [], []

    # Schema check, if jsonschema is available.
    try:
        import jsonschema
        schema = json.load(open(os.path.join(SCHEMA_DIR, "card.schema.json"), encoding="utf-8"))
        try:
            jsonschema.validate(card, schema)
            print("Schema validates.")
        except jsonschema.ValidationError as exc:
            errors.append(f"schema: {exc.message} (at {'/'.join(str(p) for p in exc.path)})")
    except ImportError:
        warnings.append("jsonschema not installed - structural check skipped "
                        "(pip install jsonschema)")

    # Filename must match card_id.
    expected = f"{card.get('card_id', '')}.json"
    if os.path.basename(path) != expected:
        errors.append(f"filename is {os.path.basename(path)}, card_id expects {expected}")

    # published_at must precede the first post time.
    pub = parse_dt(card.get("published_at", ""))
    posts = [parse_dt(r["post_time"]) for r in card.get("races", []) if r.get("post_time")]
    posts = [p for p in posts if p]
    if pub and posts:
        first = min(posts)
        if pub >= first:
            errors.append(f"published_at ({pub}) is not before first post ({first}). "
                          f"This is the whole audit claim - fix it.")
        else:
            mins = (first - pub).total_seconds() / 60
            if mins >= 120:
                print(f"Published {mins / 60:.1f} h before first post.")
            else:
                print(f"Published {mins:.0f} min before first post.")

    # Race-level method rules.
    seen = set()
    for r in card.get("races", []):
        n = r.get("race_number")
        if n in seen:
            errors.append(f"race {n} appears more than once")
        seen.add(n)
        tag = f"race {n}"

        if r.get("no_play"):
            if r.get("confidence") != "no_play":
                errors.append(f"{tag}: no_play is true but confidence is "
                              f"'{r.get('confidence')}'")
            if not r.get("no_play_reason"):
                errors.append(f"{tag}: no_play with no reason given")
            continue

        sels = r.get("selections", [])
        if not sels:
            errors.append(f"{tag}: played race with no selections")
        if len(sels) < 3:
            warnings.append(f"{tag}: only {len(sels)} selections - intended?")

        progs = [s.get("program") for s in sels]
        if len(set(progs)) != len(progs):
            errors.append(f"{tag}: duplicate program number in selections")

        for s in sels:
            if not (s.get("reservation") or "").strip():
                errors.append(f"{tag}: #{s.get('program')} has no reservation")

        alt = r.get("alternate")
        if not alt:
            errors.append(f"{tag}: no named alternate")
        else:
            if alt.get("program") in progs:
                errors.append(f"{tag}: alternate #{alt['program']} is also a selection")
            if not alt.get("left_off_because"):
                errors.append(f"{tag}: alternate has no left_off_because")

        if r.get("confidence") == "no_play":
            errors.append(f"{tag}: confidence is no_play but no_play is false")
        if r.get("read_quality") == "weak" and r.get("confidence") == "single":
            warnings.append(f"{tag}: read_quality weak but confidence single - "
                            f"check that is deliberate")

    # Ticket arithmetic.
    for t in card.get("tickets", []):
        legs = t.get("structure", [])
        label = f"{t.get('type')} races {t.get('races')}"
        if len(legs) != len(t.get("races", [])):
            errors.append(f"{label}: {len(legs)} legs for {len(t.get('races', []))} races")
        combos = 1
        for leg in legs:
            combos *= len(leg)
        expected_cost = round(combos * t.get("base", 0), 2)
        if abs(expected_cost - t.get("cost", 0)) > 0.005:
            errors.append(f"{label}: cost says ${t.get('cost')}, "
                          f"{combos} combos x ${t.get('base')} = ${expected_cost}")

    # Report.
    print()
    for w in warnings:
        print(f"  WARN  {w}")
    for e in errors:
        print(f"  FAIL  {e}")

    played = sum(1 for r in card.get("races", []) if not r.get("no_play"))
    noplay = sum(1 for r in card.get("races", []) if r.get("no_play"))
    print(f"\n{card.get('card_id')}: {len(card.get('races', []))} races "
          f"({played} played, {noplay} no-play)")

    if errors:
        print(f"\n{len(errors)} error(s). Do not commit until these are fixed.")
        sys.exit(1)
    print("\nClean. Safe to commit.")


if __name__ == "__main__":
    main()

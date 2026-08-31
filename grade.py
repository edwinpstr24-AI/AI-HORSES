#!/usr/bin/env python3
"""
AI Horses - grade.py

Grades one published card against official Equibase chart results.

Usage:
    python grade.py CARDS/CT-2026-08-29-E.json

You read the winner off the Equibase chart and type it in. Nothing is
scraped: Equibase terms prohibit automated access, and a commercial
product should not be built on top of that.

Writes RESULTS/<card_id>.result.json and never touches the card file.
That separation is the whole audit argument.
"""

import json
import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "RESULTS")
SCHEMA_DIR = os.path.join(HERE, "SCHEMA")


# ---------------------------------------------------------------- helpers

def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def validate(instance, schema_name):
    """Validate if jsonschema is installed. Skip quietly if not."""
    try:
        import jsonschema
    except ImportError:
        return None
    schema = load_json(os.path.join(SCHEMA_DIR, schema_name))
    jsonschema.validate(instance, schema)
    return True


def effective_race(race, revisions):
    """
    Apply any revision that changed this race, so grading judges the
    selections that were actually live at post time - not the originals.
    Returns (selection_programs, alternate_program, confidence, was_revised).
    """
    programs = [s["program"] for s in race.get("selections", [])]
    alt = race.get("alternate", {}).get("program")
    confidence = race["confidence"]
    no_play = race["no_play"]
    revised = False

    for rev in revisions:
        for change in rev.get("changes", []):
            if change.get("race_number") != race["race_number"]:
                continue
            revised = True
            if change.get("now_no_play"):
                no_play = True
                confidence = "no_play"
            if change.get("new_selections"):
                programs = [s["program"] for s in change["new_selections"]]
            if change.get("new_confidence"):
                confidence = change["new_confidence"]

    return programs, alt, confidence, no_play, revised


def ask(prompt, allow_blank=True):
    while True:
        val = input(prompt).strip()
        if val or allow_blank:
            return val


# ---------------------------------------------------------------- grading

def grade_race(race, revisions):
    n = race["race_number"]
    programs, alt, confidence, no_play, revised = effective_race(race, revisions)

    print(f"\n--- Race {n} | {race['distance']} {race['surface']} | {race['race_type']}")

    if no_play:
        print("    NO PLAY at publication. Excluded from the rate.")
        if race.get("no_play_reason"):
            print(f"    Reason: {race['no_play_reason']}")
        return {
            "race_number": n,
            "outcome": "no_play",
            "confidence_at_publication": confidence,
            "revision_applied": revised,
            "note": race.get("no_play_reason", ""),
        }

    print(f"    Selections: {', '.join(programs)}    Alternate: {alt}")
    if revised:
        print("    (revised after scratches - grading the revised set)")

    winner = ask("    Winning program number  [or C=cancelled, X=skip]: ", allow_blank=False)

    if winner.upper() == "C":
        return {
            "race_number": n,
            "outcome": "cancelled",
            "confidence_at_publication": confidence,
            "revision_applied": revised,
        }
    if winner.upper() == "X":
        return {
            "race_number": n,
            "outcome": "scratched_out",
            "confidence_at_publication": confidence,
            "revision_applied": revised,
        }

    winner = winner.upper()
    horse = ask("    Winning horse name (optional): ")
    payoff_raw = ask("    Win payoff on $2 (optional): ")

    if winner in [p.upper() for p in programs]:
        outcome = "hit"
        print("    -> HIT")
    elif alt and winner == alt.upper():
        outcome = "alternate_won"
        print("    -> MISS - but the named alternate won. Tracked separately.")
    else:
        outcome = "miss"
        print("    -> MISS")

    entry = {
        "race_number": n,
        "winner_program": winner,
        "outcome": outcome,
        "confidence_at_publication": confidence,
        "revision_applied": revised,
    }
    if horse:
        entry["winner_horse"] = horse
    if payoff_raw:
        try:
            entry["win_payoff"] = float(payoff_raw)
        except ValueError:
            pass

    eng = race.get("engine_output", {}).get("ranked", [])
    if eng:
        eng_top3 = [e["program"].upper() for e in eng if e["rank"] <= 3]
        entry["engine_outcome"] = "hit" if winner in eng_top3 else "miss"
        if entry["engine_outcome"] != ("hit" if outcome == "hit" else "miss"):
            verdict = "engine had him" if entry["engine_outcome"] == "hit" else "engine missed him"
            print(f"    ({verdict} - judgment and scores disagreed)")
    else:
        entry["engine_outcome"] = "no_engine_data"

    if outcome in ("miss", "alternate_won"):
        note = ask("    Post-mortem - why was he not in the three? ")
        if note:
            entry["note"] = note

    return entry


def grade_tickets(card):
    tickets = card.get("tickets", [])
    if not tickets:
        return []
    out = []
    print("\n--- Tickets")
    for t in tickets:
        label = f"{t['type']} races {t['races']}  cost ${t['cost']:.2f}"
        print(f"\n    {label}")
        returned = ask("    Returned $ (0 if it died): ", allow_blank=False)
        try:
            returned = float(returned)
        except ValueError:
            returned = 0.0
        rec = {
            "type": t["type"],
            "races": t["races"],
            "cost": t["cost"],
            "returned": returned,
        }
        if returned == 0:
            leg = ask("    Died in which leg (1-based)? ")
            if leg.isdigit():
                rec["alive_through_leg"] = int(leg) - 1
        out.append(rec)
    return out


def totals(race_results, ticket_results):
    counted = [r for r in race_results if r["outcome"] in ("hit", "miss", "alternate_won")]
    hits = [r for r in counted if r["outcome"] == "hit"]
    alt_wins = [r for r in counted if r["outcome"] == "alternate_won"]

    by_conf = {}
    for r in counted:
        c = r.get("confidence_at_publication", "unknown")
        b = by_conf.setdefault(c, {"played": 0, "hits": 0})
        b["played"] += 1
        if r["outcome"] == "hit":
            b["hits"] += 1
    for b in by_conf.values():
        b["rate"] = round(b["hits"] / b["played"], 4) if b["played"] else 0.0

    t = {
        "races_carded": len(race_results),
        "races_played": len(counted),
        "no_plays": sum(1 for r in race_results if r["outcome"] == "no_play"),
        "hits": len(hits),
        # Winner-in-top-3. NOT a win rate - the method targets coverage.
        "coverage_rate": round(len(hits) / len(counted), 4) if counted else 0.0,
        "alternate_wins": len(alt_wins),
        "by_confidence": by_conf,
    }

    eng = [r for r in counted if r.get("engine_outcome") in ("hit", "miss")]
    if eng:
        eng_hits = sum(1 for r in eng if r["engine_outcome"] == "hit")
        t["engine_played"] = len(eng)
        t["engine_hits"] = eng_hits
        t["engine_coverage_rate"] = round(eng_hits / len(eng), 4)

    if ticket_results:
        cost = sum(x["cost"] for x in ticket_results)
        ret = sum(x["returned"] for x in ticket_results)
        t["ticket_cost"] = round(cost, 2)
        t["ticket_return"] = round(ret, 2)
        t["roi"] = round((ret - cost) / cost, 4) if cost else 0.0

    return t


# ---------------------------------------------------------------- main

def main():
    if len(sys.argv) != 2:
        print("Usage: python grade.py CARDS/<card_id>.json")
        sys.exit(1)

    card_path = sys.argv[1]
    if not os.path.exists(card_path):
        print(f"Not found: {card_path}")
        sys.exit(1)

    card = load_json(card_path)
    try:
        if validate(card, "card.schema.json"):
            print("Card validates against schema.")
    except Exception as exc:
        print(f"WARNING - card does not validate: {exc}")
        if ask("Continue anyway? [y/N]: ").lower() != "y":
            sys.exit(1)

    print(f"\nGrading {card['card_id']} - {card['track']['name']} {card['race_date']}")
    print("Source of truth: official Equibase chart. Nothing else.")

    revisions = card.get("revisions", [])
    race_results = [grade_race(r, revisions) for r in card["races"]]
    ticket_results = grade_tickets(card)

    result = {
        "card_id": card["card_id"],
        "graded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "equibase_official_chart",
        "races": race_results,
        "totals": totals(race_results, ticket_results),
    }
    if ticket_results:
        result["tickets"] = ticket_results

    try:
        validate(result, "result.schema.json")
    except Exception as exc:
        print(f"WARNING - result does not validate: {exc}")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, f"{card['card_id']}.result.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")

    t = result["totals"]
    print("\n" + "=" * 52)
    print(f"  {card['card_id']}")
    print(f"  Played {t['races_played']} of {t['races_carded']}  ({t['no_plays']} no-play)")
    print(f"  Winner in top 3: {t['hits']}/{t['races_played']}  = {t['coverage_rate']:.1%}")
    if t["alternate_wins"]:
        print(f"  Alternate won:   {t['alternate_wins']}")
    for conf, b in sorted(t["by_confidence"].items()):
        print(f"    {conf:<10} {b['hits']}/{b['played']}  {b['rate']:.1%}")
    if "engine_played" in t:
        print(f"  Engine alone:    {t['engine_hits']}/{t['engine_played']}  "
              f"= {t['engine_coverage_rate']:.1%}")
    if "roi" in t:
        print(f"  Tickets: ${t['ticket_cost']:.2f} out, ${t['ticket_return']:.2f} back, ROI {t['roi']:+.1%}")
    print("=" * 52)
    print(f"\nWritten: {out_path}")
    print("Commit and push it. The card file was not modified.")


if __name__ == "__main__":
    main()

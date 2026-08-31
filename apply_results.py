#!/usr/bin/env python3
"""
AI Horses - apply_results.py

Takes a winners file (chart facts only - who won, what it paid) and grades the
card against it. The hit/miss determination happens HERE, in code, by comparing
the winner against the committed selections. Nothing upstream gets to decide it.

Usage:
    python apply_results.py winners.json
    python apply_results.py winners.json --dry-run

Winners file shape - see RESULTS-TEMPLATE.json:
    {"card_id": "...", "chart_url": "...",
     "winners": [{"race": 1, "program": "7", "horse": "...", "win_payoff": 8.40},
                 {"race": 8, "cancelled": true}],
     "tickets": [{"type":"pick4","races":[5,6,7,8],"returned":0,"alive_through_leg":2}]}

No-play races are read from the card and excluded automatically - the winners
file does not need to mention them.
"""

import json
import os
import sys
from datetime import datetime, timezone

import grade as G  # reuse the same logic the interactive grader uses

HERE = os.path.dirname(os.path.abspath(__file__))
CARDS = os.path.join(HERE, "CARDS")
RESULTS = os.path.join(HERE, "RESULTS")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    if len(args) != 1:
        sys.exit("Usage: python apply_results.py winners.json [--dry-run]")

    win_path = args[0]
    if not os.path.exists(win_path):
        sys.exit(f"Not found: {win_path}")
    wf = json.load(open(win_path, encoding="utf-8"))

    cid = wf.get("card_id")
    if not cid:
        sys.exit("Winners file has no card_id.")
    card_path = os.path.join(CARDS, f"{cid}.json")
    if not os.path.exists(card_path):
        sys.exit(f"No card at {card_path}")
    card = json.load(open(card_path, encoding="utf-8"))

    by_race = {}
    for w in wf.get("winners", []):
        by_race[w["race"]] = w

    revisions = card.get("revisions", [])
    race_results = []
    unmatched = []

    for race in card["races"]:
        n = race["race_number"]
        programs, alt, confidence, no_play, revised = G.effective_race(race, revisions)

        if no_play:
            race_results.append({
                "race_number": n, "outcome": "no_play",
                "confidence_at_publication": confidence,
                "revision_applied": revised,
                "note": race.get("no_play_reason", ""),
            })
            continue

        w = by_race.get(n)
        if not w:
            unmatched.append(n)
            continue

        if w.get("cancelled"):
            race_results.append({
                "race_number": n, "outcome": "cancelled",
                "confidence_at_publication": confidence,
                "revision_applied": revised,
            })
            continue

        winner = str(w["program"]).strip().upper()
        upper = [p.upper() for p in programs]

        # The verdict is computed, never supplied.
        if winner in upper:
            outcome = "hit"
        elif alt and winner == alt.upper():
            outcome = "alternate_won"
        else:
            outcome = "miss"

        entry = {
            "race_number": n,
            "winner_program": winner,
            "outcome": outcome,
            "confidence_at_publication": confidence,
            "revision_applied": revised,
        }
        if w.get("horse"):
            entry["winner_horse"] = w["horse"]
        if isinstance(w.get("win_payoff"), (int, float)):
            entry["win_payoff"] = float(w["win_payoff"])

        eng = race.get("engine_output", {}).get("ranked", [])
        if eng:
            top3 = [e["program"].upper() for e in eng if e["rank"] <= 3]
            entry["engine_outcome"] = "hit" if winner in top3 else "miss"
        else:
            entry["engine_outcome"] = "no_engine_data"

        if w.get("note"):
            entry["note"] = w["note"]

        race_results.append(entry)

    if unmatched:
        print(f"WARNING - no result given for race(s): "
              f"{', '.join(map(str, unmatched))}. They are omitted, not guessed.")

    ticket_results = []
    card_tickets = {(t["type"], tuple(t["races"])): t for t in card.get("tickets", [])}
    for t in wf.get("tickets", []):
        key = (t["type"], tuple(t["races"]))
        src = card_tickets.get(key)
        if not src:
            print(f"WARNING - ticket {t['type']} {t['races']} is not on the card. Skipped.")
            continue
        rec = {"type": src["type"], "races": src["races"],
               "cost": src["cost"], "returned": float(t.get("returned", 0))}
        if "alive_through_leg" in t:
            rec["alive_through_leg"] = t["alive_through_leg"]
        ticket_results.append(rec)

    result = {
        "card_id": cid,
        "graded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "equibase_official_chart",
        "races": race_results,
        "totals": G.totals(race_results, ticket_results),
    }
    if ticket_results:
        result["tickets"] = ticket_results

    t = result["totals"]
    print(f"\n{cid}")
    for r in race_results:
        if r["outcome"] == "no_play":
            print(f"  R{r['race_number']}: no play")
        elif r["outcome"] == "cancelled":
            print(f"  R{r['race_number']}: cancelled")
        else:
            tag = {"hit": "HIT", "miss": "miss",
                   "alternate_won": "miss (alternate won)"}[r["outcome"]]
            eng = ""
            if r.get("engine_outcome") == "hit" and r["outcome"] != "hit":
                eng = "   <- engine had him"
            elif r.get("engine_outcome") == "miss" and r["outcome"] == "hit":
                eng = "   <- engine did not"
            print(f"  R{r['race_number']}: won by #{r['winner_program']} "
                  f"{r.get('winner_horse','')} - {tag}{eng}")

    print(f"\n  Winner in top 3: {t['hits']}/{t['races_played']} = {t['coverage_rate']:.1%}")
    if "engine_played" in t:
        print(f"  Engine alone:    {t['engine_hits']}/{t['engine_played']} "
              f"= {t['engine_coverage_rate']:.1%}")

    misses = [r for r in race_results if r["outcome"] in ("miss", "alternate_won")
              and not r.get("note")]
    if misses:
        print(f"\n  {len(misses)} miss(es) with no post-mortem. Add a \"note\" to "
              f"those races in the winners file - misses get published with "
              f"the reasoning, same as hits.")

    if dry:
        print("\nDry run. Nothing written.")
        return

    os.makedirs(RESULTS, exist_ok=True)
    out = os.path.join(RESULTS, f"{cid}.result.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")
    print(f"\nWritten: {out}")
    print("Run build_pages.py and record.py, then commit and push.")


if __name__ == "__main__":
    main()

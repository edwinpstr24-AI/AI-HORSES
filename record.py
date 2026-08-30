#!/usr/bin/env python3
"""
AI Horses - record.py

Reads every file in RESULTS/ and rebuilds RECORD.md - the public running
record. Run it after each grading, then commit and push.

Usage:
    python record.py
"""

import glob
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "RESULTS")
OUT = os.path.join(HERE, "RECORD.md")

CONF_ORDER = ["single", "standard", "spread"]


def pct(hits, played):
    return f"{hits / played:.1%}" if played else "-"


def main():
    paths = sorted(glob.glob(os.path.join(RESULTS_DIR, "*.result.json")))
    if not paths:
        print("No graded results in RESULTS/ yet.")
        return

    results = [json.load(open(p, encoding="utf-8")) for p in paths]

    played = hits = no_plays = alt_wins = 0
    by_conf = {}
    cost = ret = 0.0
    has_tickets = False

    for r in results:
        t = r["totals"]
        played += t["races_played"]
        hits += t["hits"]
        no_plays += t.get("no_plays", 0)
        alt_wins += t.get("alternate_wins", 0)
        for c, b in t.get("by_confidence", {}).items():
            agg = by_conf.setdefault(c, {"played": 0, "hits": 0})
            agg["played"] += b["played"]
            agg["hits"] += b["hits"]
        if "ticket_cost" in t:
            has_tickets = True
            cost += t["ticket_cost"]
            ret += t["ticket_return"]

    L = []
    L.append("# AI Horses - Public Record\n")
    L.append("Every card is committed to this repository **before first post** and is ")
    L.append("never edited afterward. The git commit timestamp is the proof. ")
    L.append("Results are graded the following morning against the official Equibase ")
    L.append("chart, which is treated as ground truth over any other source.\n")
    L.append("The headline number is **winner-in-top-3**, not a win rate. Selections ")
    L.append("are built for coverage in multi-race exotics - the objective is that the ")
    L.append("winner appears somewhere in the three. Order inside the three carries no ")
    L.append("meaning and is not graded.\n")
    L.append("No-play races are excluded from the rate entirely. Declining to play is a ")
    L.append("decision, not an absence, and it is recorded as one.\n")
    L.append(f"*Rebuilt {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} "
             f"from {len(results)} graded card(s).*\n")

    L.append("## Overall\n")
    L.append("| | |")
    L.append("|---|---|")
    L.append(f"| Cards graded | {len(results)} |")
    L.append(f"| Races played | {played} |")
    L.append(f"| No-play races | {no_plays} |")
    L.append(f"| **Winner in top 3** | **{hits}/{played} = {pct(hits, played)}** |")
    L.append(f"| Named alternate won | {alt_wins} |")
    if has_tickets and cost:
        L.append(f"| Ticket outlay | ${cost:,.2f} |")
        L.append(f"| Ticket return | ${ret:,.2f} |")
        L.append(f"| **ROI** | **{(ret - cost) / cost:+.1%}** |")
    L.append("")

    L.append("## By confidence tier\n")
    L.append("If `single` does not outperform `spread` over a real sample, the tiers ")
    L.append("are decoration and this table is where that shows up.\n")
    L.append("| Tier | Played | Hits | Rate |")
    L.append("|---|---|---|---|")
    ordered = [c for c in CONF_ORDER if c in by_conf] + \
              [c for c in sorted(by_conf) if c not in CONF_ORDER]
    for c in ordered:
        b = by_conf[c]
        L.append(f"| {c} | {b['played']} | {b['hits']} | {pct(b['hits'], b['played'])} |")
    L.append("")

    L.append("## Card by card\n")
    L.append("| Card | Played | Hits | Rate | No-play |")
    L.append("|---|---|---|---|---|")
    for r in results:
        t = r["totals"]
        L.append(f"| `{r['card_id']}` | {t['races_played']} | {t['hits']} | "
                 f"{pct(t['hits'], t['races_played'])} | {t.get('no_plays', 0)} |")
    L.append("")

    misses = [(r["card_id"], rc) for r in results for rc in r["races"]
              if rc["outcome"] in ("miss", "alternate_won") and rc.get("note")]
    if misses:
        L.append("## Misses\n")
        L.append("Published at the same size as the hits.\n")
        for card_id, rc in misses:
            tag = " *(named alternate won)*" if rc["outcome"] == "alternate_won" else ""
            L.append(f"- **{card_id} R{rc['race_number']}** - won by "
                     f"#{rc.get('winner_program', '?')}{tag}. {rc['note']}")
        L.append("")

    L.append("---\n")
    L.append("Informational only. No outcome is guaranteed. 18+ or 21+ depending on ")
    L.append("your jurisdiction. AI Horses accepts no wagers and holds no funds.\n")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))

    print(f"Wrote {OUT}")
    print(f"  {len(results)} card(s), {hits}/{played} = {pct(hits, played)} winner-in-top-3")
    print("Commit and push.")


if __name__ == "__main__":
    main()

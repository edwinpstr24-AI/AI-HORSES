#!/usr/bin/env python3
"""
AI Horses - record.py

Rebuilds README.md - the public running record - from everything in RESULTS/
plus every published card in CARDS/. Run it after each grading, and after
adding a card, then commit and push.

Writes the file even when nothing is graded yet, so a published card always
appears somewhere.
"""

import glob
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "RESULTS")
CARDS_DIR = os.path.join(HERE, "CARDS")
VIEW_DIR = os.path.join(HERE, "CARDS-VIEW")
OUT = os.path.join(HERE, "README.md")

CONF_ORDER = ["single", "standard", "spread"]


def pct(hits, played):
    return f"{hits / played:.1%}" if played else "-"


def card_link(cid):
    if os.path.exists(os.path.join(VIEW_DIR, f"{cid}.md")):
        return f"[{cid}](CARDS-VIEW/{cid}.md)"
    return f"`{cid}`"


def main():
    results = [json.load(open(p, encoding="utf-8"))
               for p in sorted(glob.glob(os.path.join(RESULTS_DIR, "*.result.json")))]
    graded_ids = {r["card_id"] for r in results}

    pending = []
    for p in sorted(glob.glob(os.path.join(CARDS_DIR, "*.json"))):
        cid = json.load(open(p, encoding="utf-8"))["card_id"]
        if cid not in graded_ids:
            pending.append(cid)

    played = hits = no_plays = alt_wins = 0
    eng_played = eng_hits = 0
    cost = ret = 0.0
    has_tickets = False
    by_conf = {}

    for r in results:
        t = r["totals"]
        played += t["races_played"]
        hits += t["hits"]
        no_plays += t.get("no_plays", 0)
        alt_wins += t.get("alternate_wins", 0)
        eng_played += t.get("engine_played", 0)
        eng_hits += t.get("engine_hits", 0)
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

    if pending:
        L.append("## Published, not yet graded\n")
        for cid in pending:
            L.append(f"- {card_link(cid)}")
        L.append("")

    if not results:
        L.append("## Record\n")
        L.append("No cards graded yet. The first graded card populates this section.\n")
    else:
        L.append("## Overall\n")
        L.append("| | |")
        L.append("|---|---|")
        L.append(f"| Cards graded | {len(results)} |")
        L.append(f"| Races played | {played} |")
        L.append(f"| No-play races | {no_plays} |")
        L.append(f"| **Winner in top 3** | **{hits}/{played} = {pct(hits, played)}** |")
        L.append(f"| Named alternate won | {alt_wins} |")
        if eng_played:
            L.append(f"| Scoring engine alone | {eng_hits}/{eng_played} = "
                     f"{pct(eng_hits, eng_played)} |")
        if has_tickets and cost:
            L.append(f"| Ticket outlay | ${cost:,.2f} |")
            L.append(f"| Ticket return | ${ret:,.2f} |")
            L.append(f"| **ROI** | **{(ret - cost) / cost:+.1%}** |")
        L.append("")

        if eng_played:
            L.append("## Engine vs. final selections\n")
            L.append("The scoring workbook produces a ranked top 4 before any judgment is ")
            L.append("applied. Both are graded. If the final selections do not beat the raw ")
            L.append("engine over a real sample, the judgment layer is not earning its place.\n")
            L.append("| | Played | Hits | Rate |")
            L.append("|---|---|---|---|")
            L.append(f"| Scoring engine, top 3 | {eng_played} | {eng_hits} | "
                     f"{pct(eng_hits, eng_played)} |")
            L.append(f"| Final selections | {played} | {hits} | {pct(hits, played)} |")
            L.append("")

        if by_conf:
            L.append("## By confidence tier\n")
            L.append("If `single` does not outperform `spread` over a real sample, the tiers ")
            L.append("are decoration and this table is where that shows up.\n")
            L.append("| Tier | Played | Hits | Rate |")
            L.append("|---|---|---|---|")
            ordered = [c for c in CONF_ORDER if c in by_conf] + \
                      [c for c in sorted(by_conf) if c not in CONF_ORDER]
            for c in ordered:
                b = by_conf[c]
                L.append(f"| {c} | {b['played']} | {b['hits']} | "
                         f"{pct(b['hits'], b['played'])} |")
            L.append("")

        L.append("## Card by card\n")
        L.append("| Card | Played | Hits | Rate | No-play |")
        L.append("|---|---|---|---|---|")
        for r in results:
            t = r["totals"]
            L.append(f"| {card_link(r['card_id'])} | {t['races_played']} | {t['hits']} | "
                     f"{pct(t['hits'], t['races_played'])} | {t.get('no_plays', 0)} |")
        L.append("")

        misses = [(r["card_id"], rc) for r in results for rc in r["races"]
                  if rc["outcome"] in ("miss", "alternate_won") and rc.get("note")]
        if misses:
            L.append("## Misses\n")
            L.append("Published at the same size as the hits.\n")
            for cid, rc in misses:
                tag = " *(named alternate won)*" if rc["outcome"] == "alternate_won" else ""
                L.append(f"- **{cid} R{rc['race_number']}** - won by "
                         f"#{rc.get('winner_program', '?')}{tag}. {rc['note']}")
            L.append("")

    L.append("---\n")
    L.append("Informational only. No outcome is guaranteed. 18+ or 21+ depending on ")
    L.append("your jurisdiction. AI Horses accepts no wagers and holds no funds.\n")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))

    print(f"Wrote {OUT}")
    if results:
        print(f"  {len(results)} graded, {hits}/{played} = {pct(hits, played)} winner-in-top-3")
    else:
        print("  0 graded")
    if pending:
        print(f"  {len(pending)} published, not yet graded: {', '.join(pending)}")
    print("Commit and push.")


if __name__ == "__main__":
    main()

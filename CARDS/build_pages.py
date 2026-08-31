#!/usr/bin/env python3
"""
AI Horses - build_pages.py

Generates one readable page per card in CARDS-VIEW/, derived entirely from
CARDS/*.json and RESULTS/*.result.json. Nothing here is written by hand or by
a chat - if it appears on the page, it is in the committed data.

Usage:
    python build_pages.py            # rebuild every card page
    python build_pages.py CT-2026-08-29-E
"""

import glob
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CARDS = os.path.join(HERE, "CARDS")
RESULTS = os.path.join(HERE, "RESULTS")
VIEW = os.path.join(HERE, "CARDS-VIEW")

CONF_LABEL = {"single": "single", "standard": "standard",
              "spread": "spread", "no_play": "no play"}


def load(path):
    return json.load(open(path, encoding="utf-8"))


def fmt_date(card):
    try:
        d = datetime.fromisoformat(card["race_date"])
        return d.strftime("%a %-d %b %Y")
    except Exception:
        return card.get("race_date", "")


def lead_time(card):
    try:
        pub = datetime.fromisoformat(card["published_at"].replace("Z", "+00:00"))
        posts = [datetime.fromisoformat(r["post_time"].replace("Z", "+00:00"))
                 for r in card["races"] if r.get("post_time")]
        if not posts:
            return None
        mins = (min(posts) - pub).total_seconds() / 60
        if mins < 0:
            return None
        return f"{mins / 60:.1f} h" if mins >= 120 else f"{mins:.0f} min"
    except Exception:
        return None


def race_result(result, n):
    if not result:
        return None
    for r in result.get("races", []):
        if r.get("race_number") == n:
            return r
    return None


def build(card, result):
    L = []
    cid = card["card_id"]
    cfg = card["track"]["configuration"]

    L.append(f"# {card['track']['name']} — {fmt_date(card)}"
             f"{', evening' if card['day_evening'] == 'E' else ''}\n")

    bits = [cfg["shape"], cfg["framework"].replace("_", "-")]
    lt = lead_time(card)
    if lt:
        bits.append(f"published {lt} before first post")
    L.append(" · ".join(bits) + "\n")

    if result:
        t = result["totals"]
        L.append(f"**{t['hits']} of {t['races_played']} — winner in top 3**")
        if t.get("no_plays"):
            L.append(f" · {t['no_plays']} no-play")
        if "engine_coverage_rate" in t:
            L.append(f" · engine alone {t['engine_hits']}/{t['engine_played']}")
        L.append("\n")
    else:
        L.append("*Not yet graded.*\n")

    dp = card.get("day_picks", {})
    if dp:
        parts = []
        if "best_bet" in dp:
            b = dp["best_bet"]
            parts.append(f"Best bet: race {b.get('race', '?')} #{b['program']}")
        if "longshot_of_day" in dp:
            b = dp["longshot_of_day"]
            parts.append(f"Longshot of the day: race {b.get('race', '?')} #{b['program']}")
        L.append(" · ".join(parts) + "\n")

    L.append("---\n")

    for race in card["races"]:
        n = race["race_number"]
        res = race_result(result, n)
        head = f"## Race {n} — {race['distance']} {race['race_type'].lower()}"
        L.append(head)

        tags = [CONF_LABEL.get(race["confidence"], race["confidence"])]
        if race.get("read_quality") == "weak":
            tags.append("weak read")
        if race.get("scratch_risk") in ("medium", "high"):
            tags.append(f"{race['scratch_risk']} scratch risk")
        L.append(f"*{' · '.join(tags)}*\n")

        if race.get("no_play"):
            L.append(f"**No play.** {race.get('no_play_reason', '')}\n")
            L.append("---\n")
            continue

        winner = (res or {}).get("winner_program", "").upper()

        L.append("| | Horse | Reservation |")
        L.append("|---|---|---|")
        for s in race.get("selections", []):
            mark = " ✓" if winner and s["program"].upper() == winner else ""
            name = s.get("horse", "")
            if s.get("coverage_only"):
                name += " *(coverage only)*"
            L.append(f"| **{s['program']}**{mark} | {name} | {s.get('reservation', '')} |")
        L.append("")

        alt = race.get("alternate")
        if alt:
            mark = " ✓" if winner and alt["program"].upper() == winner else ""
            ml = f" ({alt['ml']})" if alt.get("ml") else \
                 (f" ({alt['morning_line']})" if alt.get("morning_line") else "")
            L.append(f"**Alternate — {alt['program']}{mark} {alt.get('horse', '')}{ml}.** "
                     f"{alt.get('reason', '')} Left off: {alt.get('left_off_because', '')}\n")

        eng = race.get("engine_output", {}).get("ranked", [])
        if eng:
            row = "  ·  ".join(
                f"{e['rank']}. #{e['program']}" + (f" ({e['score']:g})" if "score" in e else "")
                for e in eng)
            L.append(f"**Scoring engine:** {row}")
            ls = race.get("engine_output", {}).get("longshot")
            if ls:
                L.append(f" · longshot #{ls['program']}")
            L.append("\n")

        if res:
            oc = res.get("outcome")
            if oc == "hit":
                verdict = "Hit."
            elif oc == "alternate_won":
                verdict = "Miss — the named alternate won."
            elif oc == "miss":
                verdict = "Miss."
            else:
                verdict = oc.replace("_", " ").capitalize() + "."
            payoff = f" · ${res['win_payoff']:.2f}" if res.get("win_payoff") else ""
            L.append(f"**Won by #{res.get('winner_program', '?')} "
                     f"{res.get('winner_horse', '')}**{payoff} — {verdict}")
            if res.get("engine_outcome") == "hit" and oc != "hit":
                L.append(" The scoring engine had him and the final selections did not.")
            elif res.get("engine_outcome") == "miss" and oc == "hit":
                L.append(" The scoring engine did not have him.")
            if res.get("note"):
                L.append(f"\n\n{res['note']}")
            L.append("\n")

        fades = race.get("fades", [])
        if fades:
            L.append("<details><summary>Reservation audit — horses left off</summary>\n")
            for f in fades:
                L.append(f"- **#{f['program']} {f.get('horse', '')}** — {f['case_for']} "
                         f"Still off: {f['why_still_off']}")
            L.append("\n</details>\n")

        L.append("---\n")

    L.append(f"Card file: [`CARDS/{cid}.json`](../CARDS/{cid}.json)")
    if result:
        L.append(f" · Result: [`RESULTS/{cid}.result.json`](../RESULTS/{cid}.result.json)")
    L.append("\n\nInformational only. No outcome is guaranteed. "
             "18+ or 21+ depending on your jurisdiction. "
             "AI Horses accepts no wagers and holds no funds.\n")

    return "\n".join(L)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    paths = sorted(glob.glob(os.path.join(CARDS, "*.json")))
    if not paths:
        sys.exit("No cards in CARDS/.")

    os.makedirs(VIEW, exist_ok=True)
    built = 0
    for p in paths:
        card = load(p)
        cid = card["card_id"]
        if only and cid != only:
            continue
        rp = os.path.join(RESULTS, f"{cid}.result.json")
        result = load(rp) if os.path.exists(rp) else None
        out = os.path.join(VIEW, f"{cid}.md")
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(build(card, result))
        state = "graded" if result else "ungraded"
        print(f"  {cid}.md  ({state})")
        built += 1

    if not built:
        sys.exit(f"No card matching {only}")
    print(f"\n{built} page(s) in CARDS-VIEW/. Run record.py, then commit and push.")


if __name__ == "__main__":
    main()

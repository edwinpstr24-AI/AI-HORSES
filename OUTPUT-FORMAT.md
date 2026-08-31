# AI Horses — card output format

How to get a finished card out of a handicapping chat as a file you can drop
straight into `CARDS/` — no retyping.

---

## The paste-in prompt

Handicap the card as normal. When the selections are final, paste this:

> Now output the whole card as a single JSON file matching the AI Horses card
> schema. Filename `<TRACK>-<YYYY-MM-DD>-<D|E>.json`. Give it to me as a
> downloadable file, not as text in the chat.
>
> Rules:
> - Every selection needs a `reservation`. No exceptions.
> - `published_at` must be before the first post time, in UTC.
> - No-play races: set `no_play: true`, `confidence: "no_play"`, give a
>   `no_play_reason`, and omit `selections` and `alternate`.
> - Every played race needs exactly one `alternate` with both `reason` and
>   `left_off_because`.
> - `fades` is the Step 8 reservation audit — any horse left off that had a
>   real case. Empty array if none.
> - `coverage_only: true` on any horse that is in the three for ticket
>   coverage but is not a horse to bet.
> - Leave `engine.version` at whatever the last card used unless the scoring
>   changed.
> - Do not invent post times, payoffs, or figures. Omit what you don't have.
>
> Template follows. Match its structure exactly.

Then paste the contents of `TEMPLATE.json` underneath it.

---

## Filename

```
CT-2026-08-29-E.json      Charles Town, Aug 29 2026, evening
SAR-2026-08-30-D.json     Saratoga, Aug 30 2026, day
```

Track code = the Equibase `trackId`. Must match `card_id` inside the file.

---

## Field notes

**`track.configuration`** — Step 0, recorded per card. `framework` is either
`position_dominated` (bullrings, extra-turn tracks) or `figure_dominated`
(wide galloping ovals). Never mixed on one card.

**`track.bias`** — omit the whole block when no bias table with a disclosed
sample was available. Never state a bias without its sample size.

**`engine`** — `factors_blank` lists every factor with no source. Currently
the six Top Ratings fields. Bump `version` only when the scoring itself
changes; that's what lets the record segment cleanly pre-fix and post-fix.

**`read_quality`** — `strong` / `adequate` / `weak`. Say plainly when a read
is weak. It gets published.

**`scratch_risk`** — `high` when the field is thin enough that one more
scratch changes the race.

**`tickets`** — `structure` is program numbers per leg in race order.
`cost` = `base` × product of leg widths. State it so it can be played as
written.

**`revisions`** — append-only. After scratches, add a revision entry; never
edit the races above it. The grader will judge the revised set and flag that
it did.

---

## Before you commit

1. Run `python validate.py CARDS/<file>.json` — catches structural errors.
2. Check `published_at` is genuinely before first post.
3. Commit and push. One commit, before the races run.
4. Never edit the file again.

---

## Making it automatic

Add this to your project instructions so you don't have to paste the prompt
every time:

> When selections for a card are final, also output the card as a JSON file
> matching the AI Horses card schema, named `<TRACK>-<YYYY-MM-DD>-<D|E>.json`,
> as a downloadable file. Every selection must carry a reservation.

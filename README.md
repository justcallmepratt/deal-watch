# Deal Watch

Scheduled deal alerts that stay quiet unless a price is worth acting on.

**Status:** prototype running as scheduled AI agents since November 2026. This repo holds the
write-up and a small, tested rules engine extracted from it.

## The idea

Checking deal sites by hand during a sale is slow, and most "deals" are noise. I wanted something
that looks for deals matching what I plan to buy, writes them to one sheet, and only notifies me
when it matters.

## The MVP

Two parts:

1. **The prototype (no code):** scheduled agents with web search. Each run reads the sheet,
   researches, writes new finds and stays silent unless a rule fires. The prompt is in
   [`prompts/sale-run.md`](prompts/sale-run.md).
2. **The rules engine (this repo's code):** [`dealwatch.py`](dealwatch.py) is the decision logic
   pulled out of the prompt into plain Python, so it can be tested and reused when the collector
   stops being an agent.

```bash
python3 dealwatch.py examples/deals.csv --today 2026-11-24 --out sheet.csv
python3 -m unittest discover -s tests
```

```
Deal Watch run for 2026-11-24
  kept 6, removed 4, rejected 2
  removed:  Example office chair (reliability not checked for a $399.00 item)
  removed:  Example air fryer (poor record: recall 2025, example recall notice)
  removed:  Example monitor arm (expired 2026-11-15)
  removed:  Example headphones (price last seen 2026-11-12)
  rejected: Example power station (no source link)
  rejected: Example desk lamp (no price)
  note:     Example desk organiser (built-to-last claim has no reason, not counted)
Alerts:
  - Example 4-bay NAS: $527.99 (was $729.99), on your wishlist
    https://example.com/nas
  - Example mechanical keyboard: $65.00 (was $140.00), 53.6% off
    https://example.com/keyboard
  - Example cast iron skillet: $29.95 (was $44.95), 33.4% off
    https://example.com/skillet
Check by hand (sources disagree, no alert sent):
  - Example robot vacuum: $199.00 here, $349.00 elsewhere
    https://example.com/vacuum
```

The cable in the example saves a dollar, so it stays on the sheet and sends nothing. The robot
vacuum is on the wishlist, but a second source shows a much higher price, so it waits for a
person instead of sending an alert.

### Columns

Required: `item, price, regular_price, source_url, seen_on, expires_on, wishlist` (dates are
`YYYY-MM-DD`). Optional, and a sheet without them still works:

| Column | What it holds | What the code does with it |
|---|---|---|
| `reliability` | A note that starts with `good`, `mixed`, `poor`, `recall` or `defect`, then the source | Poor record, recall or defect: removed. $75 or more and mixed or not checked: removed unless it is on the wishlist or saves $100 or 30%. Any other text counts as not checked, never as good. |
| `built_to_last` | `yes` or `no` | A `yes` counts only with a reason in `built_to_last_why`; otherwise it is cleared and noted. |
| `built_to_last_why` | Warranty, repairability or long-term evidence | Kept on the sheet. |
| `other_price` | The same item's price from a second source | More than 10% apart: kept, but no alert, listed to check by hand. |

Python 3.10 or later, standard library only.

## Set up with Claude

Open this folder in Claude Code and say **"Follow PROMPT.md."** [`PROMPT.md`](PROMPT.md) has Claude
ask what you plan to buy, fill in your profile from [`profile.example.md`](profile.example.md), make
the sheet, and schedule one run per sale. It asks before creating any task and tests the first
run with `dealwatch.py`.

## How we solved it

| Problem | What we did |
|---|---|
| Too many alerts | Notify only for a wishlist match, or a saving of $100 or 30% or more. Quiet runs just update the sheet. |
| Made-up prices | A row needs a price and the link it was read from, or it is rejected. Nothing is estimated. |
| Stale deals | A price older than 3 days is dropped. A deal past its end date is removed. |
| Deals that fit me, not a list of links | The first run worked from bookmarks. Later runs pick from stated preferences: planned purchases, durability, the maker's reliability record. |
| Sheets that grow forever | One tab per sale. The tab and its task are retired 14 days after the sale ends. |
| Deals from makers with a bad record | Anything with a poor record, a recall or a known defect is dropped. An item of $75 or more needs a checked record, unless the saving is large or it is on the wishlist. An unknown rating never counts as good. |
| "Built to last" as a sales pitch | The flag counts only with a reason: warranty, repairability or long-term evidence. |
| Sources that disagree | If a second source's price is more than 10% away, the deal stays on the sheet but sends no alert until someone checks it. |
| One big purchase | A separate daily task watches a single laptop configuration, new and refurbished, so it never gets lost among the smaller deals. |
| Does an unattended run work at all? | Fired the first task by hand as a test before trusting the schedule. It wrote 11 deals. |

### What didn't work

- **Some large retailers block automated readers.** The prototype does not work around that. It uses
  those prices only when recent deal coverage states them. A real build should use sources
  that allow it, such as retailer product APIs or a price-history service.
- **"Regular" prices can be inflated.** Percent-off is only as honest as the list price, so the
  sheet sorts by dollars saved and the write-ups judge by the deal price.
- **Agent-reported prices need spot checks.** One reported price was about half of what the maker's own
  page showed, and was dropped. Most rows were never re-checked by hand.

### One thing the data showed

Looking at three generations of the same laptop line: a fall launch got its first real discount
(about 10 to 12.5%) by its first Black Friday, the same price came back before Christmas, and the
next big drop only came when a successor launched. Three generations from deal coverage is a small
sample, not a price-tracker dataset.

## Alternatives

Open-source tools I looked at in November 2026. None of them picks deals from a wishlist or checks
the maker's reliability record. Each one watches product links you give it.

| Project | Licence | Overlap | Differs from Deal Watch |
|---|---|---|---|
| [PriceBuddy](https://github.com/jez500/pricebuddy) | GPL-3.0 | Closest match: price history, target-price and %-drop alerts, cross-store comparison, REST API, CLI and MCP server | Scrapes store pages; no deal end dates or stale-price rule |
| [changedetection.io](https://github.com/dgtlmoon/changedetection.io) | Apache-2.0 | Mature page-change watcher with price graphs, $ and % thresholds, many notification channels | General-purpose; supports proxies for blocked sites |
| [Discount Bandit](https://github.com/Cybrarist/Discount-Bandit) | none found | Rich alert rules, such as "lowest in X days" and "official sellers only" | No licence file, so not reusable as-is |
| [Huginn](https://github.com/huginn/huginn) | MIT | General scheduled-agent platform that can watch for deals | All price logic would have to be built on top |

Ideas worth taking: a "lowest in X days" alert once prices are stored, accepting a price only when
two ways of reading it agree, and [Apprise](https://github.com/caronc/apprise) for notifications.
For the collector, the Best Buy Products API (it returns regular and sale prices), the Keepa API
(paid, Amazon history) and the Amazon Creators API are candidates. Each one's terms on storing
prices need checking first; Best Buy's limit caching.

## What's next

1. Replace the agent collector with a scheduled Spring Boot job that reads from sources with an API.
2. Publish each check as a "price observed" event to Kafka and store it in Postgres.
3. Move these rules into a Kafka consumer that sends the alerts.
4. A public price-history page on my site.

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
python3 -m unittest discover tests
```

```
Deal Watch run for 2026-11-24
  kept 3, removed 2, rejected 2
  removed:  Example monitor arm (expired 2026-11-15)
  removed:  Example headphones (price last seen 2026-11-12)
  rejected: Example power station (no source link)
  rejected: Example desk lamp (no price)
Alerts:
  - Example 4-bay NAS: $527.99 (was $729.99), on your wishlist
    https://example.com/nas
  - Example mechanical keyboard: $65.00 (was $140.00), 53.6% off
    https://example.com/keyboard
```

The cable in the example saves a dollar, so it stays on the sheet and sends nothing.

Python 3.10 or later, standard library only.

## How we solved it

| Problem | What we did |
|---|---|
| Too many alerts | Notify only for a wishlist match, or a saving of $100 or 30% or more. Quiet runs just update the sheet. |
| Made-up prices | A row needs a price and the link it was read from, or it is rejected. Nothing is estimated. |
| Stale deals | A price older than 3 days is dropped. A deal past its end date is removed. |
| Deals that fit me, not a list of links | The first run worked from bookmarks. Later runs pick from stated preferences: planned purchases, durability, the maker's reliability record. |
| Sheets that grow forever | One tab per sale. The tab and its task are retired 14 days after the sale ends. |
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

## What's next

1. Replace the agent collector with a scheduled Spring Boot job that reads from sources with an API.
2. Publish each check as a "price observed" event to Kafka and store it in Postgres.
3. Move these rules into a Kafka consumer that sends the alerts.
4. A public price-history page on my site.

#!/usr/bin/env python3
"""Deal Watch MVP: decide which recorded deals stay on the sheet and which earn an alert.

Input is a CSV of price observations (one row per deal someone actually saw).
Output is a cleaned CSV plus a short list of alerts.

Rules, in order:
  1. No source link or no price -> rejected. A price is never estimated.
  2. Past its end date -> removed as expired.
  3. Seen more than MAX_AGE_DAYS ago -> removed as stale.
  4. Maker has a poor record, an open recall or a known defect -> removed.
  5. Costs RELIABILITY_CHECK_USD or more and the maker's record is mixed or
     not checked -> removed, unless it is a wishlist item or the saving is large.
  6. A second source's price differs by more than PRICE_DISAGREE_PCT -> kept,
     but it never alerts; it is listed to check by hand instead.
  7. "Built to last" counts only with a stated reason (warranty, repairability,
     long-term evidence). A bare claim is cleared and noted.
  8. Still listed -> alert only if it is a wishlist item, or it saves
     at least MIN_SAVING_USD or at least MIN_SAVING_PCT.

The reliability, built-to-last and second-price columns are optional, so a
sheet without them still works. An unknown or missing rating is never read as
a good one.

No dependencies beyond the Python standard library.
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from datetime import date, timedelta

MAX_AGE_DAYS = 3
MIN_SAVING_USD = 100.0
MIN_SAVING_PCT = 30.0
RELIABILITY_CHECK_USD = 75.0
PRICE_DISAGREE_PCT = 10.0

FIELDS = ["item", "price", "regular_price", "source_url", "seen_on", "expires_on", "wishlist"]
OPTIONAL_FIELDS = ["reliability", "built_to_last", "built_to_last_why", "other_price"]

GOOD, MIXED, POOR, UNCHECKED = "good", "mixed", "poor", "not checked"
_POOR_WORDS = ("poor", "recall", "open recall", "defect", "known defect")


@dataclass
class Deal:
    item: str
    price: float
    regular_price: float | None
    source_url: str
    seen_on: date
    expires_on: date | None
    wishlist: bool
    reliability: str = UNCHECKED
    reliability_note: str = ""
    built_to_last: bool = False
    built_to_last_why: str = ""
    other_price: float | None = None

    @property
    def saving_usd(self) -> float:
        if self.regular_price is None:
            return 0.0
        return round(self.regular_price - self.price, 2)

    @property
    def saving_pct(self) -> float:
        if not self.regular_price:
            return 0.0
        return round(100 * self.saving_usd / self.regular_price, 1)

    @property
    def large_saving(self) -> bool:
        return self.saving_usd >= MIN_SAVING_USD or self.saving_pct >= MIN_SAVING_PCT

    @property
    def sources_disagree(self) -> bool:
        if self.other_price is None:
            return False
        low, high = sorted((self.price, self.other_price))
        return high > 0 and 100 * (high - low) / high > PRICE_DISAGREE_PCT


def _money(text: str) -> float | None:
    text = (text or "").strip().replace("$", "").replace(",", "")
    return float(text) if text else None


def _day(text: str) -> date | None:
    text = (text or "").strip()
    return date.fromisoformat(text) if text else None


def _yes(text: str) -> bool:
    return (text or "").strip().lower() in {"yes", "y", "true", "1"}


def reliability_rating(text: str) -> str:
    """Read the rating from the start of a note such as "good, Wirecutter 2025".

    Only a note that starts with a known word counts. Anything else, including
    an empty cell or "reliability not checked", is treated as not checked.
    """
    word = (text or "").strip().lower()
    if word.startswith(GOOD):
        return GOOD
    if word.startswith(MIXED):
        return MIXED
    if word.startswith(_POOR_WORDS):
        return POOR
    return UNCHECKED


def parse_row(row: dict) -> tuple[Deal | None, str | None]:
    """Return (deal, None) or (None, reason it was rejected)."""
    item = (row.get("item") or "").strip()
    if not item:
        return None, "no item name"
    url = (row.get("source_url") or "").strip()
    if not url.startswith(("http://", "https://")):
        return None, "no source link"
    try:
        price = _money(row.get("price", ""))
        regular = _money(row.get("regular_price", ""))
        other = _money(row.get("other_price", ""))
        seen = _day(row.get("seen_on", ""))
        expires = _day(row.get("expires_on", ""))
    except ValueError as err:
        return None, f"unreadable value ({err})"
    if price is None:
        return None, "no price"
    if seen is None:
        return None, "no date seen"
    note = (row.get("reliability") or "").strip()
    return Deal(
        item, price, regular, url, seen, expires, _yes(row.get("wishlist", "")),
        reliability=reliability_rating(note), reliability_note=note,
        built_to_last=_yes(row.get("built_to_last", "")),
        built_to_last_why=(row.get("built_to_last_why") or "").strip(),
        other_price=other,
    ), None


def reliability_problem(deal: Deal) -> str | None:
    """Return why the maker's record keeps this deal off the sheet, or None."""
    if deal.reliability == POOR:
        return f"poor record: {deal.reliability_note}"
    if deal.price < RELIABILITY_CHECK_USD or deal.reliability == GOOD:
        return None
    if deal.wishlist or deal.large_saving:
        return None
    if deal.reliability == MIXED:
        return "mixed record and the saving is small"
    return f"reliability not checked for a ${deal.price:,.2f} item"


def review(rows: list[dict], today: date) -> dict:
    """Sort rows into kept / removed / rejected and pick the alerts."""
    kept: list[Deal] = []
    removed: list[tuple[str, str]] = []
    rejected: list[tuple[str, str]] = []
    notes: list[tuple[str, str]] = []
    for row in rows:
        deal, why = parse_row(row)
        if deal is None:
            rejected.append(((row.get("item") or "?").strip() or "?", why))
            continue
        if deal.expires_on and deal.expires_on < today:
            removed.append((deal.item, f"expired {deal.expires_on.isoformat()}"))
            continue
        if deal.seen_on < today - timedelta(days=MAX_AGE_DAYS):
            removed.append((deal.item, f"price last seen {deal.seen_on.isoformat()}"))
            continue
        problem = reliability_problem(deal)
        if problem:
            removed.append((deal.item, problem))
            continue
        if deal.built_to_last and not deal.built_to_last_why:
            deal.built_to_last = False
            notes.append((deal.item, "built-to-last claim has no reason, not counted"))
        kept.append(deal)
    kept.sort(key=lambda d: d.saving_usd, reverse=True)
    alerts = [d for d in kept if worth_an_alert(d)]
    check = [d for d in kept if d.sources_disagree]
    return {"kept": kept, "removed": removed, "rejected": rejected,
            "alerts": alerts, "check": check, "notes": notes}


def worth_an_alert(deal: Deal) -> bool:
    if deal.sources_disagree:
        return False
    return deal.wishlist or deal.large_saving


def alert_reason(deal: Deal) -> str:
    if deal.wishlist:
        return "on your wishlist"
    if deal.saving_usd >= MIN_SAVING_USD:
        return f"saves ${deal.saving_usd:,.2f}"
    return f"{deal.saving_pct:g}% off"


def _cents(value: float | None) -> str:
    return "" if value is None else f"{value:.2f}"


def write_sheet(deals: list[Deal], out) -> None:
    writer = csv.writer(out)
    writer.writerow(["item", "price", "regular_price", "saving_usd", "saving_pct",
                     "source_url", "seen_on", "expires_on", "wishlist",
                     "reliability", "built_to_last", "built_to_last_why", "other_price"])
    for d in deals:
        writer.writerow([
            d.item, f"{d.price:.2f}", _cents(d.regular_price),
            f"{d.saving_usd:.2f}", f"{d.saving_pct:g}", d.source_url,
            d.seen_on.isoformat(),
            d.expires_on.isoformat() if d.expires_on else "",
            "yes" if d.wishlist else "no",
            d.reliability_note or UNCHECKED,
            "yes" if d.built_to_last else "no", d.built_to_last_why,
            _cents(d.other_price),
        ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Clean a deals CSV and list the deals worth an alert.")
    parser.add_argument("deals_csv", help="CSV with columns: " + ", ".join(FIELDS)
                        + " (optional: " + ", ".join(OPTIONAL_FIELDS) + ")")
    parser.add_argument("--today", help="run as if today were this date (YYYY-MM-DD)")
    parser.add_argument("--out", help="write the cleaned sheet to this CSV file")
    args = parser.parse_args(argv)

    today = date.fromisoformat(args.today) if args.today else date.today()
    with open(args.deals_csv, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result = review(rows, today)

    if args.out:
        with open(args.out, "w", newline="", encoding="utf-8") as handle:
            write_sheet(result["kept"], handle)

    print(f"Deal Watch run for {today.isoformat()}")
    print(f"  kept {len(result['kept'])}, removed {len(result['removed'])}, "
          f"rejected {len(result['rejected'])}")
    for item, why in result["removed"]:
        print(f"  removed:  {item} ({why})")
    for item, why in result["rejected"]:
        print(f"  rejected: {item} ({why})")
    for item, why in result["notes"]:
        print(f"  note:     {item} ({why})")
    if result["alerts"]:
        print("Alerts:")
        for d in result["alerts"]:
            was = f" (was ${d.regular_price:,.2f})" if d.regular_price else ""
            print(f"  - {d.item}: ${d.price:,.2f}{was}, {alert_reason(d)}")
            print(f"    {d.source_url}")
    else:
        print("No alerts. Quiet run.")
    if result["check"]:
        print("Check by hand (sources disagree, no alert sent):")
        for d in result["check"]:
            print(f"  - {d.item}: ${d.price:,.2f} here, ${d.other_price:,.2f} elsewhere")
            print(f"    {d.source_url}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

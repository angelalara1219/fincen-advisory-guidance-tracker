"""Pull FinCEN alerts, advisories, notices, and SAR key terms into one CSV.

Two public FinCEN pages are the source of truth:

  * Alerts/Advisories/Notices/Bulletins/Fact Sheets
    https://www.fincen.gov/resources/advisoriesbulletinsfact-sheets
  * SAR Advisory Key Terms
    https://www.fincen.gov/resources/suspicious-activity-report-sar-advisory-key-terms

New items are appended to data/fincen_tracker.csv. Existing rows are never
rewritten, except to fill in a SAR key term that FinCEN published later.
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass, asdict, fields
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE = "https://www.fincen.gov"
ADVISORIES_URL = f"{BASE}/resources/advisoriesbulletinsfact-sheets"
KEY_TERMS_URL = f"{BASE}/resources/suspicious-activity-report-sar-advisory-key-terms"

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "fincen_tracker.csv"
README_PATH = ROOT / "README.md"

# Only track items issued on or after this date. Older history is easy to
# backfill by lowering it, but most of it is no longer actionable.
SINCE = date(2025, 1, 1)

HEADERS = {"User-Agent": "fincen-sar-tracker/1.0 (public-data research script)"}

# FinCEN numbers look like FIN-2026-Alert009, FIN-2026-A002, FIN-2026-NTC1,
# FIN-2025-CTA1. A few older ones are written FinCEN-2023-Alert006.
NUMBER_RE = re.compile(r"\bFIN(?:CEN)?-(\d{4})-([A-Z]+\d+)\b", re.IGNORECASE)

SECTION_TYPES = {
    "alerts": "Alert",
    "advisories": "Advisory",
    "notices": "Notice",
    "bulletins": "Bulletin / Fact Sheet",
}


@dataclass
class Item:
    date_issued: str
    fincen_number: str
    type: str
    title: str
    sar_key_term: str
    link: str
    first_seen: str


COLUMNS = [f.name for f in fields(Item)]


# ---------------------------------------------------------------- helpers

def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def normalize_number(text: str) -> str:
    """'FinCEN Advisory FIN-2026-A002' -> 'FIN-2026-A002'."""
    m = NUMBER_RE.search(text or "")
    if not m:
        return ""
    year, suffix = m.groups()
    if suffix.lower().startswith("alert"):
        suffix = "Alert" + suffix[5:]
    else:
        suffix = suffix.upper()
    return f"FIN-{year}-{suffix}"


def parse_date(text: str) -> str:
    """FinCEN mixes 10/30/2026, 09/8/2025 and 12/2020. Return ISO or ''."""
    text = (text or "").strip()
    for fmt in ("%m/%d/%Y", "%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def clean(text: str) -> str:
    return " ".join((text or "").split())


def section_type(table) -> str:
    heading = table.find_previous(["h2", "h3"])
    label = heading.get_text(" ", strip=True).lower() if heading else ""
    for key, value in SECTION_TYPES.items():
        if key in label:
            return value
    return "Other"


# ---------------------------------------------------------------- parsing

def parse_advisories(html: str, today: str) -> list[Item]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[Item] = []
    for table in soup.find_all("table"):
        kind = section_type(table)
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            first, when, desc = cells[0], cells[1], cells[2]
            iso = parse_date(when.get_text())
            if not iso or date.fromisoformat(iso) < SINCE:
                continue
            link_tag = first.find("a", href=True)
            link = urljoin(BASE, link_tag["href"]) if link_tag else ""
            first_text = clean(first.get_text(" "))
            if "spanish" in first_text.lower():
                continue  # translations duplicate the English item
            number = normalize_number(first_text)
            # Bulletins/fact sheets put the title in the first cell
            # and a short description in the third.
            title = clean(desc.get_text(" ")) if number else re.sub(
                r"\s*PDF Only\s*$", "", first_text)
            items.append(Item(iso, number, kind, title, "", link, today))
    return items


def parse_key_terms(html: str) -> dict[str, str]:
    """Map each FinCEN number to the key term FinCEN asks filers to use."""
    soup = BeautifulSoup(html, "html.parser")
    terms: dict[str, str] = {}
    for row in soup.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        term = clean(cells[1].get_text(" "))
        links = cells[3].find_all("a")
        # Only the first linked number is the product that introduced the
        # term; the rest are related earlier advisories.
        if not links or not term:
            continue
        number = normalize_number(links[0].get_text())
        if number and number not in terms:
            terms[number] = term
        # Some rows label the link with the key term instead of the number
        # (e.g. FIN-2025-CVCKIOSK), so also index by the PDF's file name.
        href = links[0].get("href", "")
        if href:
            terms.setdefault(link_key(href), term)
    return terms


def link_key(url: str) -> str:
    return "url:" + url.rstrip("/").rsplit("/", 1)[-1].lower()


# ---------------------------------------------------------------- storage

def load_csv(path: Path = CSV_PATH) -> list[Item]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return [Item(**{c: row.get(c, "") for c in COLUMNS}) for row in csv.DictReader(f)]


def save_csv(items: list[Item], path: Path = CSV_PATH) -> None:
    items = sorted(items, key=lambda i: (i.date_issued, i.fincen_number), reverse=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))


def item_key(item: Item) -> str:
    return item.fincen_number or item.link.lower().rstrip("/")


def merge(existing: list[Item], scraped: list[Item], terms: dict[str, str]) -> tuple[list[Item], list[Item]]:
    by_key = {item_key(i): i for i in existing}
    added: list[Item] = []
    for item in scraped:
        item.sar_key_term = (terms.get(item.fincen_number)
                             or (terms.get(link_key(item.link)) if item.link else "")
                             or "")
        key = item_key(item)
        if key in by_key:
            current = by_key[key]
            if not current.sar_key_term and item.sar_key_term:
                current.sar_key_term = item.sar_key_term
            continue
        by_key[key] = item
        added.append(item)
    return list(by_key.values()), added


# ---------------------------------------------------------------- README

README_START = "<!-- LATEST:START -->"
README_END = "<!-- LATEST:END -->"


def latest_table(items: list[Item], n: int = 5) -> str:
    rows = sorted((i for i in items if i.fincen_number),
                  key=lambda i: i.date_issued, reverse=True)[:n]
    lines = ["| Date | FinCEN No. | Title | SAR key term |", "|---|---|---|---|"]
    for i in rows:
        title = f"[{i.title}]({i.link})" if i.link else i.title
        term = f"`{i.sar_key_term}`" if i.sar_key_term else "—"
        lines.append(f"| {i.date_issued} | {i.fincen_number} | {title} | {term} |")
    return "\n".join(lines)


def update_readme(items: list[Item], path: Path = README_PATH) -> None:
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if README_START not in text or README_END not in text:
        return
    head, rest = text.split(README_START, 1)
    _, tail = rest.split(README_END, 1)
    block = f"{README_START}\n{latest_table(items)}\n{README_END}"
    path.write_text(head + block + tail, encoding="utf-8")


# ---------------------------------------------------------------- main

def run() -> int:
    today = date.today().isoformat()
    scraped = parse_advisories(fetch(ADVISORIES_URL), today)
    terms = parse_key_terms(fetch(KEY_TERMS_URL))
    if not scraped:
        print("No items parsed; FinCEN's page layout may have changed.", file=sys.stderr)
        return 1
    items, added = merge(load_csv(), scraped, terms)
    save_csv(items)
    update_readme(items)
    print(f"Parsed {len(scraped)} items, {len(terms)} key terms. New: {len(added)}")
    for i in added:
        print(f"  + {i.date_issued}  {i.fincen_number or i.type}  {i.title}")
    return 0


if __name__ == "__main__":
    sys.exit(run())

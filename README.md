# FinCEN Advisory & Guidance Tracker

A small, self-updating log of FinCEN alerts, advisories, notices, and guidance, with the SAR key term for each one pulled into a single table.

## Why I built this

If you've worked a SAR queue, you know the drill. FinCEN drops a new alert, it asks you to put a specific key term in Field 2 and the narrative, and that term lives on page 9 of a PDF. Multiply that by a dozen alerts a year and keeping your team's quick-reference sheet current turns into its own little part-time job.

So I automated it. Once a week, a GitHub Action checks FinCEN's public pages, adds anything new to [`data/fincen_tracker.csv`](data/fincen_tracker.csv), and updates the table below. The commit history doubles as a dated record of when each item showed up.

— Angela Lara, CAMS

## Latest from FinCEN

<!-- LATEST:START -->
| Date | FinCEN No. | Title | SAR key term |
|---|---|---|---|
| 2026-10-30 | FIN-2026-NTC2 | [FinCEN Notice on the Use of Charities and Non-Profit Organizations for Illicit Activity](https://www.fincen.gov/system/files/2026-10/FinCEN-Notice-Illicit-Activity-Charities-Non-Profit-Org.pdf) | `FIN2026NPO` |
| 2026-10-30 | FIN-2026-Alert009 | [FinCEN Alert on Risks Associated with Foreign-Agent-Directed Transactions](https://www.fincen.gov/system/files/2026-10/FinCEN-Alert-Foreign-Agent-Directed-Transactions.pdf) | `FIN2026FOREIGNAGENT` |
| 2026-10-15 | FIN-2026-Alert008 | [FinCEN Alert to Counter Iranian Abuse of Religious Charity Networks](https://www.fincen.gov/system/files/2026-10/FinCEN-Alert-Iranian-Charity-Network-Abuse.pdf) | `FIN-2026-IRANCHARITYABUSE` |
| 2026-10-01 | FIN-2026-Alert007 | [FinCEN Alert on the A7 Network](https://www.fincen.gov/system/files/2026-10/FinCEN-Alert-A7-Network.pdf) | `FIN-2026-A7NETWORK` |
| 2026-09-08 | FIN-2026-Alert006 | [FinCEN Alert to Counter Iranian Procurement Efforts for its Commercial Aviation Industry](https://www.fincen.gov/system/files/2026-09/FinCEN-Alert-Iranian-Commercial-Aviation.pdf) | `FIN-2026-IRANAIR` |
<!-- LATEST:END -->

Full list: [`data/fincen_tracker.csv`](data/fincen_tracker.csv)

## What's in the data

| Column | What it is |
|---|---|
| `date_issued` | Date FinCEN issued the item |
| `fincen_number` | e.g. `FIN-2026-Alert009`, `FIN-2026-A002`, `FIN-2026-NTC2` (blank for bulletins and fact sheets) |
| `type` | Alert, Advisory, Notice, or Bulletin / Fact Sheet |
| `title` | FinCEN's title |
| `sar_key_term` | The term FinCEN asks filers to use in SAR Field 2 and the narrative |
| `link` | The official FinCEN document |
| `first_seen` | The date this tracker first picked it up |

## How it works

```
FinCEN advisories page ─┐
                        ├─> scraper.py ─> data/fincen_tracker.csv ─> README table
FinCEN SAR key terms ───┘        ▲
                                 └── GitHub Action, every Monday
```

1. `fincen_tracker/scraper.py` reads two public pages: [Alerts/Advisories/Notices/Bulletins/Fact Sheets](https://www.fincen.gov/resources/advisoriesbulletinsfact-sheets) and [SAR Advisory Key Terms](https://www.fincen.gov/resources/suspicious-activity-report-sar-advisory-key-terms).
2. It matches each item to its key term by FinCEN number, and appends anything it hasn't seen before. Existing rows are left alone, except to fill in a key term FinCEN posts later.
3. [`.github/workflows/update.yml`](.github/workflows/update.yml) runs the tests, then the scraper, and commits only when something changed.

If FinCEN redesigns its site and nothing parses, the run fails loudly instead of quietly wiping the data.

## Run it yourself

```bash
pip install -r requirements.txt
python -m fincen_tracker.scraper
python -m unittest discover -s tests
```

You can also kick off a run from the **Actions** tab with **Run workflow**.

## Notes

- Public FinCEN data only. Nothing here comes from any employer or non-public source.
- This is a convenience tool, not legal advice. Always confirm filing instructions against the original FinCEN document.
- Tracking starts in 2025. Change `SINCE` in `scraper.py` to backfill older items.

## License

MIT

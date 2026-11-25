# Confluence History Checker

Confluence keeps version numbers. It does not keep who moved, trashed or purged your pages, and a purge leaves nothing. This checker shows you what your native record actually contains.

A free command-line tool that walks the pages and blog posts of one Confluence Cloud space, reads each item's native version history from the Confluence REST API, and writes a history health report: title, type, version count, first and most recent version dates, most recent editor, and a flag on every item whose native version list is the only history record that exists for it. It tells you, in one run, exactly how thin your native record is before you need it.

## Run it

You need Python 3 (standard library only, nothing to install) and an Atlassian API token, which you can create at id.atlassian.com under Manage profile, Security, API tokens.

```bash
git clone https://github.com/tyler-odell-sentrada/confluence-history-checker.git
cd confluence-history-checker
export CONFLUENCE_SITE="https://your-site.atlassian.net"
export CONFLUENCE_EMAIL="you@example.com"
export CONFLUENCE_API_TOKEN="your-api-token"

# One space, CSV to stdout
python3 confluence_history_checker.py --space DOCS

# Markdown report to a file
python3 confluence_history_checker.py --space DOCS --format markdown -o report.md
```

Sample output (Markdown):

```markdown
| Title | Type | Versions | First version | Latest version | Latest editor | History record |
| --- | --- | --- | --- | --- | --- | --- |
| Onboarding Guide | page | 14 | 2025-11-02 | 2026-01-19 | Ada Admin | native version list only |
| Release Notes 2026 | blogpost | 3 | 2026-01-05 | 2026-01-06 | Ben Builder | native version list only |
```

Every row carries the same flag, and that is the finding: for each of these items, the version list above is the entire history record Confluence holds.

## What it cannot do

These are facts about Confluence's native API, not features held back:

- **It cannot say who moved, trashed or purged a page.** Confluence does not record content moves in its audit log, and the trash names no deleter. There is nothing for any script to read.
- **It cannot see a purged page at all.** A purge leaves no API trace: no title, no actor, no body. If a page was purged before you run this checker, it is simply absent, and the report cannot tell you it ever existed.
- **It keeps no snapshots and restores nothing.** The report describes the version history; it does not preserve it.
- **It records nothing continuously.** It can only report the version history Confluence still holds at the moment you run it. History that disappears between runs disappears unrecorded.

## The app that keeps the record continuously

[Content History & Recovery for Confluence](https://marketplace.atlassian.com/apps/1774130015?utm_source=github&utm_medium=free-tool&utm_campaign=confluence-history-checker) records every page change, move, trash and purge with who did it, from the moment it is installed, and keeps a recycle bin that puts pages back where they belong, including recreating purged pages from snapshot. It runs entirely inside Atlassian's infrastructure. If knowing who touched your content, and getting purged pages back, is the record you actually need, that is the tool built for it.

## Housekeeping

- Runs entirely on your own credentials and your own machine. No data leaves your Confluence site; the script talks only to your site and writes only to the output you choose.
- No telemetry, no run limits, no nag screens.
- Licence: MIT (see LICENSE).

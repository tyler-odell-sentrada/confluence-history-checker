#!/usr/bin/env python3
"""Report what a Confluence space's native version history actually holds.

Walks the pages and blog posts of one Confluence Cloud space with your own
credentials, reads each item's native version history from the Confluence
REST API, and writes a history health report: title, type, version count,
first and most recent version dates, most recent editor, and a flag showing
that the native version list is the only history record that exists for the
item.

Nothing is uploaded anywhere. The script talks only to your own Confluence
site and writes only to the output file (or stdout) you choose.

Environment variables:
    CONFLUENCE_SITE       e.g. https://your-site.atlassian.net
    CONFLUENCE_EMAIL      the email of your Atlassian account
    CONFLUENCE_API_TOKEN  an API token from https://id.atlassian.com/manage-profile/security/api-tokens

Usage:
    python3 confluence_history_checker.py --space DOCS
    python3 confluence_history_checker.py --space DOCS --format markdown -o report.md

Limits of the native API (facts, not features):
    Confluence does not record who moved, trashed or purged a page, and a
    purge leaves no API trace at all. This checker can only report the
    version history Confluence still holds at run time.
"""

import argparse
import base64
import csv
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

CONTENT_PAGE_SIZE = 100
ONLY_RECORD_FLAG = "native version list only"


class ConfluenceError(Exception):
    """Raised when the Confluence API returns an error response."""


def build_auth_header(email, token):
    raw = "{}:{}".format(email, token).encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def make_fetcher(site, email, token):
    """Return a fetch(path) -> dict callable bound to one Confluence site."""
    site = site.rstrip("/")
    headers = {
        "Authorization": build_auth_header(email, token),
        "Accept": "application/json",
    }

    def fetch(path):
        url = site + path
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:300]
            raise ConfluenceError("HTTP {} for {}: {}".format(exc.code, path, body))
        except urllib.error.URLError as exc:
            raise ConfluenceError("could not reach {}: {}".format(site, exc.reason))

    return fetch


def list_space_content(fetch, space_key):
    """Return all pages and blog posts in the space (id, title, type)."""
    items = []
    start = 0
    while True:
        params = urllib.parse.urlencode(
            {
                "spaceKey": space_key,
                "type": "page,blogpost",
                "status": "current",
                "start": start,
                "limit": CONTENT_PAGE_SIZE,
            }
        )
        page = fetch("/wiki/rest/api/content?" + params)
        results = page.get("results", [])
        for result in results:
            items.append(
                {
                    "id": result.get("id", ""),
                    "title": result.get("title", ""),
                    "type": result.get("type", ""),
                }
            )
        start += len(results)
        if not results or not (page.get("_links") or {}).get("next"):
            return items


def fetch_versions(fetch, content_id):
    """Return every version record for one content item, oldest first."""
    versions = []
    start = 0
    while True:
        params = urllib.parse.urlencode({"start": start, "limit": 200})
        path = "/wiki/rest/api/content/{}/version?{}".format(
            urllib.parse.quote(str(content_id), safe=""), params
        )
        page = fetch(path)
        results = page.get("results", [])
        versions.extend(results)
        start += len(results)
        if not results or not (page.get("_links") or {}).get("next"):
            break
    versions.sort(key=lambda v: v.get("number", 0))
    return versions


def summarise(item, versions):
    """Build one report row from a content item and its version list."""
    if versions:
        first = versions[0]
        latest = versions[-1]
        first_date = first.get("when", "")
        latest_date = latest.get("when", "")
        latest_by = latest.get("by") or {}
        latest_editor = latest_by.get("displayName") or latest_by.get("email") or ""
        count = len(versions)
    else:
        first_date = ""
        latest_date = ""
        latest_editor = ""
        count = 0
    return {
        "title": item.get("title", ""),
        "type": item.get("type", ""),
        "version_count": count,
        "first_version_date": first_date,
        "latest_version_date": latest_date,
        "latest_editor": latest_editor,
        "history_record": ONLY_RECORD_FLAG,
    }


def build_report(fetch, space_key):
    rows = []
    for item in list_space_content(fetch, space_key):
        versions = fetch_versions(fetch, item["id"])
        rows.append(summarise(item, versions))
    rows.sort(key=lambda r: r["title"].lower())
    return rows


REPORT_FIELDS = [
    "title",
    "type",
    "version_count",
    "first_version_date",
    "latest_version_date",
    "latest_editor",
    "history_record",
]


def rows_to_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=REPORT_FIELDS)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def rows_to_markdown(rows):
    lines = [
        "| Title | Type | Versions | First version | Latest version | Latest editor | History record |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        cells = [
            str(row["title"]).replace("|", "\\|"),
            str(row["type"]),
            str(row["version_count"]),
            str(row["first_version_date"]),
            str(row["latest_version_date"]),
            str(row["latest_editor"]),
            str(row["history_record"]),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def main(argv=None, fetch=None):
    parser = argparse.ArgumentParser(
        description="Report what a Confluence space's native version history holds."
    )
    parser.add_argument("--space", required=True, help="the space key, e.g. DOCS")
    parser.add_argument("--format", choices=["csv", "markdown"], default="csv")
    parser.add_argument("-o", "--output", help="output file (default: stdout)")
    args = parser.parse_args(argv)

    if fetch is None:
        site = os.environ.get("CONFLUENCE_SITE")
        email = os.environ.get("CONFLUENCE_EMAIL")
        token = os.environ.get("CONFLUENCE_API_TOKEN")
        missing = [
            name
            for name, value in (
                ("CONFLUENCE_SITE", site),
                ("CONFLUENCE_EMAIL", email),
                ("CONFLUENCE_API_TOKEN", token),
            )
            if not value
        ]
        if missing:
            parser.error(
                "missing environment variable(s): {}".format(", ".join(missing))
            )
        fetch = make_fetcher(site, email, token)

    rows = build_report(fetch, args.space)
    text = rows_to_csv(rows) if args.format == "csv" else rows_to_markdown(rows)

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

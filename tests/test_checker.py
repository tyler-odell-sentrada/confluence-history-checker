import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import confluence_history_checker as checker


VERSIONS = [
    {"number": 2, "when": "2026-01-03T11:00:00.000Z", "by": {"displayName": "Ben Builder"}},
    {"number": 1, "when": "2026-01-01T09:00:00.000Z", "by": {"displayName": "Ada Admin"}},
    {"number": 3, "when": "2026-02-01T08:30:00.000Z", "by": {"displayName": "Ada Admin"}},
]


class SummariseTests(unittest.TestCase):
    def test_summarises_first_latest_and_count(self):
        item = {"id": "42", "title": "Onboarding Guide", "type": "page"}
        versions = sorted(VERSIONS, key=lambda v: v["number"])
        row = checker.summarise(item, versions)
        self.assertEqual(row["version_count"], 3)
        self.assertEqual(row["first_version_date"], "2026-01-01T09:00:00.000Z")
        self.assertEqual(row["latest_version_date"], "2026-02-01T08:30:00.000Z")
        self.assertEqual(row["latest_editor"], "Ada Admin")
        self.assertEqual(row["history_record"], "native version list only")

    def test_empty_version_list(self):
        item = {"id": "43", "title": "Empty Page", "type": "page"}
        row = checker.summarise(item, [])
        self.assertEqual(row["version_count"], 0)
        self.assertEqual(row["first_version_date"], "")


class PaginationTests(unittest.TestCase):
    def test_content_pagination_follows_next_link(self):
        pages = [
            {"results": [{"id": "1", "title": "A", "type": "page"}], "_links": {"next": "/x"}},
            {"results": [{"id": "2", "title": "B", "type": "blogpost"}], "_links": {}},
        ]

        def fetch(path):
            self.assertTrue(path.startswith("/wiki/rest/api/content?"))
            return pages.pop(0)

        items = checker.list_space_content(fetch, "DOCS")
        self.assertEqual([i["title"] for i in items], ["A", "B"])

    def test_versions_sorted_oldest_first(self):
        def fetch(path):
            return {"results": list(VERSIONS), "_links": {}}

        versions = checker.fetch_versions(fetch, "42")
        self.assertEqual([v["number"] for v in versions], [1, 2, 3])


class ReportTests(unittest.TestCase):
    def test_build_report_end_to_end(self):
        def fetch(path):
            if path.startswith("/wiki/rest/api/content?"):
                return {
                    "results": [{"id": "42", "title": "Onboarding Guide", "type": "page"}],
                    "_links": {},
                }
            if "/version" in path:
                return {"results": list(VERSIONS), "_links": {}}
            raise AssertionError(path)

        rows = checker.build_report(fetch, "DOCS")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["version_count"], 3)

    def test_csv_header(self):
        rows = checker.build_report(
            lambda path: (
                {"results": [], "_links": {}}
                if path.startswith("/wiki/rest/api/content?")
                else {"results": [], "_links": {}}
            ),
            "DOCS",
        )
        text = checker.rows_to_csv(rows)
        self.assertEqual(
            text.strip(),
            "title,type,version_count,first_version_date,latest_version_date,latest_editor,history_record",
        )

    def test_markdown_table_shape(self):
        row = checker.summarise(
            {"id": "42", "title": "Onboarding Guide", "type": "page"},
            sorted(VERSIONS, key=lambda v: v["number"]),
        )
        text = checker.rows_to_markdown([row])
        self.assertIn("| Onboarding Guide | page | 3 |", text)
        self.assertIn("native version list only", text)


if __name__ == "__main__":
    unittest.main()

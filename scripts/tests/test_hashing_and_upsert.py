"""Run with:  python3 -m scripts.tests.test_hashing_and_upsert
(or plain `pytest scripts/tests/`). Uses an in-memory SQLite; no fixtures.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib.events import prepare, upsert
from lib.hashing import canonicalize_url, content_hash, url_hash
from lib.schema import migrate


class TestCanonicalizeURL(unittest.TestCase):
    def test_strips_tracking_params(self) -> None:
        a = canonicalize_url("https://www.example.com/story?utm_source=x&id=7")
        b = canonicalize_url("https://example.com/story?id=7&fbclid=abc")
        self.assertEqual(a, b)

    def test_strips_www_and_trailing_slash(self) -> None:
        self.assertEqual(
            canonicalize_url("https://WWW.Example.COM/a/b/"),
            "https://example.com/a/b",
        )

    def test_drops_fragment(self) -> None:
        self.assertEqual(
            canonicalize_url("https://x.com/#top"),
            "https://x.com/",
        )

    def test_sorts_query_params(self) -> None:
        self.assertEqual(
            canonicalize_url("https://a.com/p?b=2&a=1"),
            canonicalize_url("https://a.com/p?a=1&b=2"),
        )


class TestURLHash(unittest.TestCase):
    def test_same_story_different_tracking_collides(self) -> None:
        h1 = url_hash("https://stlpr.org/story?utm_source=twitter")
        h2 = url_hash("https://www.stlpr.org/story")
        self.assertEqual(h1, h2)

    def test_different_stories_differ(self) -> None:
        self.assertNotEqual(url_hash("https://a.com/1"), url_hash("https://a.com/2"))


class TestContentHash(unittest.TestCase):
    def test_ignores_breaking_prefix(self) -> None:
        a = content_hash("BREAKING: Maine passes data center moratorium")
        b = content_hash("Maine passes data center moratorium")
        self.assertEqual(a, b)

    def test_case_and_whitespace_insensitive(self) -> None:
        a = content_hash("Festus  voters   oust incumbents")
        b = content_hash("FESTUS VOTERS OUST INCUMBENTS")
        self.assertEqual(a, b)


def _fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    migrate(conn)
    return conn


class TestUpsert(unittest.TestCase):
    def test_insert_then_same_url_merges_sources(self) -> None:
        conn = _fresh_conn()
        e1 = {
            "headline": "Maine passes data center moratorium",
            "url": "https://cnn.com/story",
            "source": "gdelt",
            "source_tier": "fast",
            "state": "ME",
            "category": "banned",
            "platform": "news",
            "date": "2026-04-07",
        }
        e2 = {
            "headline": "BREAKING: Maine passes data center moratorium",
            "url": "https://www.cnn.com/story?utm_source=twitter",
            "source": "reddit",
            "source_tier": "fast",
            "state": "ME",
            "category": "banned",
            "platform": "reddit",
            "date": "2026-04-07",
        }
        self.assertEqual(upsert(conn, e1), "inserted")
        self.assertEqual(upsert(conn, e2), "updated")

        rows = conn.execute("SELECT sources_seen FROM events").fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(json.loads(rows[0][0])), {"gdelt", "reddit"})

    def test_content_hash_catches_reworded_reshare(self) -> None:
        conn = _fresh_conn()
        upsert(conn, {
            "headline": "Loudoun County eliminates by-right data center approval",
            "url": "https://patch.com/a",
            "source": "gdelt",
            "state": "VA",
            "category": "protested",
            "platform": "news",
            "date": "2026-03-15",
        })
        upsert(conn, {
            "headline": "loudoun county eliminates by-right data center approval",
            "url": "https://reddit.com/r/va/comments/xyz",
            "source": "reddit",
            "state": "VA",
            "category": "protested",
            "platform": "reddit",
            "date": "2026-03-15",
        })
        count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        self.assertEqual(count, 1, "reworded reshare should dedupe on content_hash")

    def test_tier_strengthens_never_weakens(self) -> None:
        conn = _fresh_conn()
        upsert(conn, {
            "headline": "x", "url": "https://a.com/1",
            "source": "seed", "source_tier": "manual",
            "state": "US", "category": "announced", "platform": "news", "date": "2026-01-01",
        })
        upsert(conn, {
            "headline": "x", "url": "https://a.com/1",
            "source": "gdelt", "source_tier": "fast",
            "state": "US", "category": "announced", "platform": "news", "date": "2026-01-01",
        })
        tier = conn.execute("SELECT source_tier FROM events").fetchone()[0]
        self.assertEqual(tier, "manual", "manual must not be demoted by fast")

    def test_fill_null_geo(self) -> None:
        conn = _fresh_conn()
        upsert(conn, {
            "headline": "Some story", "url": "https://a.com/s",
            "source": "gdelt", "state": "US",
            "category": "protested", "platform": "news", "date": "2026-01-01",
        })
        upsert(conn, {
            "headline": "Some story", "url": "https://a.com/s",
            "source": "reddit", "state": "OH", "city": "Columbus",
            "category": "protested", "platform": "reddit", "date": "2026-01-01",
        })
        row = conn.execute("SELECT state, city FROM events").fetchone()
        self.assertEqual(row, ("US", "Columbus"),
                         "city fills from null; state not overwritten if already set")

    def test_prepare_is_pure(self) -> None:
        e = {"headline": "t", "url": "https://a.com/?utm_source=x"}
        before = dict(e)
        out = prepare(e)
        self.assertEqual(e, before, "prepare() must not mutate the input dict")
        self.assertIn("url_hash", out)
        self.assertIn("content_hash", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)

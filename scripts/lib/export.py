"""Export data/news.json (rolling window) + data/meta.json (freshness chips).

news.json is the wire format the dashboard fetches. Schema is stable so the
frontend can depend on it without reading SQLite.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_list(s: str | None) -> list:
    if not s:
        return []
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return []


def export_news(
    db_path: Path, out_path: Path, window_days: int = 90
) -> tuple[int, dict[str, int]]:
    """Write data/news.json from events table. Returns (item_count, by_source_counts)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=window_days)).strftime("%Y-%m-%d")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT * FROM events
           WHERE date >= ?
           ORDER BY date DESC, engagement_score DESC""",
        (cutoff,),
    ).fetchall()
    conn.close()

    items: list[dict] = []
    by_source: dict[str, int] = {}
    by_state: dict[str, dict] = {}
    for r in rows:
        d = dict(r)
        d["companies"]     = _json_list(d.get("companies"))
        d["sources_seen"]  = _json_list(d.get("sources_seen"))
        d["counties"]      = _json_list(d.get("counties"))
        d["topics"]        = _json_list(d.get("topics"))
        d["ferc_dockets"]  = _json_list(d.get("ferc_dockets"))
        if d.get("platform_metadata"):
            try:
                d["platform_metadata"] = json.loads(d["platform_metadata"])
            except json.JSONDecodeError:
                d["platform_metadata"] = None
        items.append(d)

        src = d.get("source") or d.get("platform") or "unknown"
        by_source[src] = by_source.get(src, 0) + 1

        st = d.get("state")
        if st and st != "US":
            agg = by_state.setdefault(
                st,
                {"state": st, "count": 0, "total_engagement": 0,
                 "categories": {}, "platforms": {}, "latest_date": ""},
            )
            agg["count"] += 1
            agg["total_engagement"] += int(d.get("engagement_score") or 0)
            cat = d.get("category") or "unknown"
            agg["categories"][cat] = agg["categories"].get(cat, 0) + 1
            plat = d.get("platform") or "unknown"
            agg["platforms"][plat] = agg["platforms"].get(plat, 0) + 1
            if (d.get("date") or "") > agg["latest_date"]:
                agg["latest_date"] = d["date"]

    out = {
        "generated_at": _utcnow_iso(),
        "window_days":  window_days,
        "count":        len(items),
        "items":        items,
        "by_state":     by_state,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    return len(items), by_source


def write_meta(
    out_path: Path,
    tier_timestamps: dict[str, str],
    counts_by_source: dict[str, int],
    run_stats: dict,
) -> None:
    """Write data/meta.json — consumed by the dashboard's freshness chips."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at":     _utcnow_iso(),
        "tier_timestamps":  tier_timestamps,   # {"fast":"...", "deep":"...", "live":"..."}
        "counts_by_source": counts_by_source,
        "run_stats":        run_stats,
    }
    out_path.write_text(json.dumps(payload, indent=2))


def read_meta(out_path: Path) -> dict:
    if not out_path.exists():
        return {}
    try:
        return json.loads(out_path.read_text())
    except json.JSONDecodeError:
        return {}

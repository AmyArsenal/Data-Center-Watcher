#!/usr/bin/env bash
# Daily backfill run (laptop-local). Does the full pipeline end-to-end:
#
#   1/5 migrate_db.py     — ensure schema + backfill url_hash/content_hash
#   2/5 last30days skill  — deep X / YouTube / HackerNews harvest (~2 min)
#   3/5 ingest_x_from_raw — parse today's raw markdown into news.db
#   4/5 refresh_fast.py   — GDELT + Reddit + outlet RSS into the same db
#   5/5 build_news_db.py  — re-export data/social_events.json
#
# Outputs: data/news.db, data/news.json, data/meta.json, data/social_events.json
# No HTML mutation — the frontend fetches these JSON files at runtime.
#
# Usage:
#   bash scripts/run_daily.sh             # full run
#   bash scripts/run_daily.sh --skip-deep # fast tier only (GDELT/Reddit/RSS)
#
# After it finishes:  git add data/ && git commit && git push

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=python3.14
command -v "$PY" >/dev/null 2>&1 || PY=python3

SKILL_ROOT="$HOME/.claude/skills/last30days-full"
TOPIC="data center oppositions in US"
DATE_TAG=$(date +%Y-%m-%d)
SUFFIX="v3-${DATE_TAG}"
MEM_DIR="${LAST30DAYS_MEMORY_DIR:-$HOME/Documents/Last30Days}"

SKIP_DEEP=0
for arg in "$@"; do
  case "$arg" in
    --skip-deep) SKIP_DEEP=1 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
  esac
done

echo "[1/5] Ensuring schema is current"
"$PY" scripts/migrate_db.py

if [ "$SKIP_DEEP" -eq 0 ]; then
  echo "[2/5] Running last30days skill on '$TOPIC' -> suffix=$SUFFIX"
  if [ ! -d "$SKILL_ROOT" ]; then
    echo "    WARN: skill not found at $SKILL_ROOT — skipping deep tier" >&2
    echo "          (install last30days-full or pass --skip-deep to silence this)"
    SKIP_DEEP=1
  else
    "$PY" "$SKILL_ROOT/scripts/last30days.py" "$TOPIC" \
      --emit=compact \
      --save-dir="$MEM_DIR" \
      --save-suffix="$SUFFIX" \
      --subreddits=energy,urbanplanning,politics,technology,environment,PublicFreakout \
      --x-related=datacenterwatch,heatmapnews,utilitydive \
      --plan '{"intent":"breaking_news","freshness_mode":"strict_recent","cluster_mode":"story","subqueries":[{"label":"primary","search_query":"data center opposition community protest","ranking_query":"What are US communities doing to oppose data centers?","sources":["reddit","x","youtube","hackernews"],"weight":1.0},{"label":"moratorium","search_query":"data center moratorium state ban","ranking_query":"Which states are passing data center moratoriums?","sources":["x","reddit","youtube"],"weight":0.8}]}' \
      > /dev/null
  fi
fi

if [ "$SKIP_DEEP" -eq 0 ]; then
  RAW_FILE="$MEM_DIR/$(echo "$TOPIC" | tr ' ' '-' | tr '[:upper:]' '[:lower:]')-raw-$SUFFIX.md"
  if [ -f "$RAW_FILE" ]; then
    echo "[3/5] Ingesting X posts from $RAW_FILE"
    LAST30DAYS_RAW_PATH="$RAW_FILE" "$PY" scripts/ingest_x_from_raw.py
  else
    echo "    WARN: raw file not found at $RAW_FILE — skipping X ingest" >&2
  fi
else
  echo "[3/5] Skipping X ingest (deep tier disabled)"
fi

echo "[4/5] Running fast tier (GDELT / Reddit / outlet RSS / YouTube)"
"$PY" scripts/refresh_fast.py

echo "[5/5] Re-exporting data/social_events.json"
"$PY" scripts/build_news_db.py > /dev/null
# build_news_db INSERT OR REPLACE can clear the fast-tier hashes on legacy
# seed rows — re-run migrate to re-backfill. Cheap (< 1 sec).
"$PY" scripts/migrate_db.py > /dev/null

echo ""
echo "✓ Done. Review:"
echo "    git status"
echo "    git diff --stat data/"
echo ""
echo "  Push:"
echo "    git add data/ && git commit -m 'data: daily backfill $(date -u +%F)' && git push"

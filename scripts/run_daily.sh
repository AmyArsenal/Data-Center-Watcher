#!/usr/bin/env bash
# Daily refresh of the data-center opposition dashboard.
# - Runs last30days on the opposition topic (xAI X search + Reddit + YouTube + GitHub + Polymarket)
# - Ingests new X posts into SQLite (dedups by tweet URL; drops rows >35d old)
# - Re-exports data/social_events.json
# - Re-inlines the JSON into data-center-tracker.html so file:// viewers see new data
#
# Usage: bash scripts/run_daily.sh
# Expected runtime: 2-3 minutes.

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

echo "[1/4] Running last30days on '$TOPIC' -> suffix=$SUFFIX"
"$PY" "$SKILL_ROOT/scripts/last30days.py" "$TOPIC" \
  --emit=compact \
  --save-dir="$MEM_DIR" \
  --save-suffix="$SUFFIX" \
  --subreddits=energy,urbanplanning,politics,technology,environment,PublicFreakout \
  --x-related=datacenterwatch,heatmapnews,utilitydive \
  --plan '{"intent":"breaking_news","freshness_mode":"strict_recent","cluster_mode":"story","subqueries":[{"label":"primary","search_query":"data center opposition community protest","ranking_query":"What are US communities doing to oppose data centers?","sources":["reddit","x","youtube","hackernews"],"weight":1.0},{"label":"moratorium","search_query":"data center moratorium state ban","ranking_query":"Which states are passing data center moratoriums?","sources":["x","reddit","youtube"],"weight":0.8}]}' \
  > /dev/null

RAW_FILE="$MEM_DIR/$(echo "$TOPIC" | tr ' ' '-' | tr '[:upper:]' '[:lower:]')-raw-$SUFFIX.md"
if [ ! -f "$RAW_FILE" ]; then
  echo "ERROR: expected raw file not found: $RAW_FILE" >&2
  exit 1
fi

echo "[2/4] Ingesting new X posts into data/news.db (dedup by tweet URL)"
# Point the ingester at today's raw file
LAST30DAYS_RAW_PATH="$RAW_FILE" "$PY" scripts/ingest_x_from_raw.py

echo "[3/4] Re-exporting data/social_events.json"
"$PY" scripts/build_news_db.py > /dev/null

echo "[4/4] Re-inlining JSON into data-center-tracker.html"
"$PY" - <<'PYEOF'
import re
HTML = "data-center-tracker.html"
JSON = "data/social_events.json"
html = open(HTML).read()
html = re.sub(r'<script type="application/json" id="social-data">.*?</script>\s*', '', html, flags=re.DOTALL)
social = open(JSON).read().replace("</script>", "<\\/script>")
inj = f'<script type="application/json" id="social-data">{social}</script>\n\n'
html = html.replace('<script type="application/json" id="iso-data">', inj + '<script type="application/json" id="iso-data">', 1)
open(HTML, "w").write(html)
print(f"    wrote {len(social):,} bytes into HTML")
PYEOF

echo ""
echo "Done. Open data-center-tracker.html to view today's update."

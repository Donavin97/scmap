#!/usr/bin/env bash
set -euo pipefail

# scmap-all — generate all four map modes for a region in one pass.
#
# Usage:
#   ./scmap-all.sh "2026-06-10" "2026-06-18"             # explicit start/end
#   ./scmap-all.sh "2026-06-10"                           # start only (end = now)
#   ./scmap-all.sh -d 7                                   # last 7 days
#   ./scmap-all.sh -d 30                                  # last 30 days
#
# Customise the region and database below, or override via environment:
#   LAT=-29 LON=25 MARGIN=8 DB="sysop:sysop@host:port/db" ./scmap-all.sh -d 7

# ── defaults (edit these) ───────────────────────────────────────────────
LAT="${LAT:--29}"
LON="${LON:-25}"
MARGIN="${MARGIN:-8}"
DB="${DB:-localhost:18002/seiscomp}"
OUTDIR="${OUTDIR:-.}"
CITY_POP="${CITY_POP:-50000}"
GRID_SIZE="${GRID_SIZE:-1.5}"
GRID_RADIUS="${GRID_RADIUS:-300}"
MC_HINT="${MC_HINT:-0.5}"
RATE_PERIOD="${RATE_PERIOD:-0}"

# ── parse time arguments ───────────────────────────────────────────────
if [ $# -eq 0 ]; then
    echo "Usage: $0 [--days N | \"YYYY-MM-DD\" [\"YYYY-MM-DD\"]]"
    echo "  --days N         last N days"
    echo "  start [end]      explicit time window (end defaults to now)"
    exit 1
fi

if [ "$1" = "-d" ] || [ "$1" = "--days" ]; then
    DAYS="${2:?missing day count}"
    END_TIME="$(date -u '+%Y-%m-%d %H:%M:%S')"
    START_TIME="$(date -u -d "$DAYS days ago" '+%Y-%m-%d %H:%M:%S')"
    LABEL="last ${DAYS}d"
else
    START_TIME="$1"
    END_TIME="${2:-$(date -u '+%Y-%m-%d %H:%M:%S')}"
    LABEL="${START_TIME%% *} – ${END_TIME%% *}"
fi

echo "=== scmap-all ======================================="
echo "  region   : lat=$LAT lon=$LON margin=${MARGIN}°"
echo "  time     : $START_TIME  →  $END_TIME"
echo "  database : $DB"
echo "  output   : $OUTDIR"
echo "======================================================"

# ── event map ───────────────────────────────────────────────────────────
echo "[1/4] event map ..."
python3 "$(dirname "$0")/scmap.py" \
    -d "$DB" \
    --start-time "$START_TIME" --end-time "$END_TIME" \
    --lat "$LAT" --lon "$LON" -m "$MARGIN" \
    --min-city-population "$CITY_POP" \
    -o "$OUTDIR/map_events.png" \
    --title "Seismicity  $LABEL"

# ── b‑value ────────────────────────────────────────────────────────────
echo "[2/4] b‑value map ..."
python3 "$(dirname "$0")/scmap.py" \
    -d "$DB" \
    --start-time "$START_TIME" --end-time "$END_TIME" \
    --lat "$LAT" --lon "$LON" -m "$MARGIN" \
    --mode bvalue --grid-size "$GRID_SIZE" --grid-radius "$GRID_RADIUS" \
    --mc-hint "$MC_HINT" \
    --min-city-population 100000 \
    -o "$OUTDIR/map_bvalue.png" \
    --title "b‑value  $LABEL"

# ── magnitude of completeness ───────────────────────────────────────────
echo "[3/4] Mc map ..."
python3 "$(dirname "$0")/scmap.py" \
    -d "$DB" \
    --start-time "$START_TIME" --end-time "$END_TIME" \
    --lat "$LAT" --lon "$LON" -m "$MARGIN" \
    --mode mc --grid-size "$GRID_SIZE" --grid-radius "$GRID_RADIUS" \
    --min-city-population 100000 \
    -o "$OUTDIR/map_mc.png" \
    --title "Magnitude of Completeness  $LABEL"

# ── rate ────────────────────────────────────────────────────────────────
echo "[4/4] rate map ..."
python3 "$(dirname "$0")/scmap.py" \
    -d "$DB" \
    --start-time "$START_TIME" --end-time "$END_TIME" \
    --lat "$LAT" --lon "$LON" -m "$MARGIN" \
    --mode rate --grid-size "$GRID_SIZE" --grid-radius "$GRID_RADIUS" \
    --mc-hint "$MC_HINT" \
    --rate-period "$RATE_PERIOD" \
    --min-city-population 100000 \
    -o "$OUTDIR/map_rate.png" \
    --title "Seismicity Rate  $LABEL"

echo ""
echo "=== done ==="
ls -lh "$OUTDIR"/map_{events,bvalue,mc,rate}.png

#!/usr/bin/env bash
set -euo pipefail

# scmap-all — generate all four map modes for a region in one pass.
# Log written to $OUTDIR/scmap-all.log (with -vvvv verbosity).
#
# Usage:
#   ./scmap-all.sh "2026-06-10" "2026-06-18"             # explicit start/end
#   ./scmap-all.sh "2026-06-10"                           # start only (end = now)
#   ./scmap-all.sh -d 7                                   # last 7 days
#   ./scmap-all.sh -d 30                                  # last 30 days
#   ./scmap-all.sh --osm -d 7                              # OSM tiles, last 7 days
#   ./scmap-all.sh --topo -d 7                             # OpenTopoMap tiles
#   ./scmap-all.sh --osm "2026-06-10" "2026-06-18"         # OSM tiles, date range
#
# Customise the region and database below, or override via environment:
#   LAT=-29 LON=25 MARGIN=8 USE_OSM=1 DB="sysop:sysop@host:port/db" ./scmap-all.sh -d 7

# ── defaults (edit these) ───────────────────────────────────────────────
LAT="${LAT:--29}"
LON="${LON:-25}"
MARGIN="${MARGIN:-8}"
DB="${DB:-localhost:18002/seiscomp}"
OUTDIR="${OUTDIR:-.}"
JOBS="${JOBS:-0}"
CITY_POP="${CITY_POP:-50000}"
GRID_SIZE="${GRID_SIZE:-1.5}"
GRID_RADIUS="${GRID_RADIUS:-300}"
MC_HINT="${MC_HINT:-0.5}"
RATE_PERIOD="${RATE_PERIOD:-0}"
USE_OSM="${USE_OSM:-}"

# ── parse flags ─────────────────────────────────────────────────────────
TILE_FLAG=""
DEBUG_FLAG=""
PASSTHRU=()
while [ $# -gt 0 ]; do
    case "$1" in
        --osm)
            TILE_FLAG="--osm"
            shift
            ;;
        --topo)
            TILE_FLAG="--topo"
            shift
            ;;
        --jobs)
            JOBS="${2:?missing value for --jobs}"
            shift 2
            ;;
        --debug)
            DEBUG_FLAG="--debug"
            shift
            ;;
        --)
            shift
            PASSTHRU+=("$@")
            break
            ;;
        *)
            PASSTHRU+=("$1")
            shift
            ;;
    esac
done
# Also support USE_OSM=1 env var (legacy)
if [ "${USE_OSM:-}" = "1" ] && [ -z "$TILE_FLAG" ]; then
    TILE_FLAG="--osm"
fi
set -- "${PASSTHRU[@]}"

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

# ── all four maps in a single pass ────────────────────────────────────
echo "Generating all 4 maps in a single pass ..."
python3 "$(dirname "$0")/scmap.py" \
    -d "$DB" \
    $TILE_FLAG $DEBUG_FLAG \
    -vvvv \
    --log-file="$OUTDIR/scmap-all.log" \
    --start-time "$START_TIME" --end-time "$END_TIME" \
    --lat "$LAT" --lon "$LON" -m "$MARGIN" \
    --mode all \
    --grid-size "$GRID_SIZE" --grid-radius "$GRID_RADIUS" \
    --mc-hint "$MC_HINT" \
    --rate-period "$RATE_PERIOD" \
    --min-city-population "$CITY_POP" \
    -o "$OUTDIR/map.png" \
    --title "$LABEL" \
    --jobs "$JOBS"

echo ""
echo "=== done ==="
ls -lh "$OUTDIR"/map_{events,bvalue,mc,rate}.png "$OUTDIR"/scmap-all.log

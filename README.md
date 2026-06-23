# scmap — SeisComP Seismic Event Map Generator

High-resolution PNG map generator for seismicity visualisation, built on the
[SeisComP](https://www.seiscomp.de/) framework.  Reads SCML (SeisComP Markup
Language) event files or queries a live SeisComP database, then renders publication-quality maps
with Cartopy and matplotlib.

**Design follows established seismological conventions** (GMT, USGS, EMSC,
GFZ) with perceptually uniform colour scales, colourblind-safe markers,
and a clean Tufte-inspired low-data‑ink basemap.

## Features

- **Three input modes** — SCML XML files (`-i`), database by event ID
  (`-E`), or database by time range (`--start-time` / `--end-time`)
- **Five map modes** — event markers (depth‑coloured, magnitude‑scaled),
  Gutenberg‑Richter b‑value heatmap, magnitude‑of‑completeness (MAXC),
  annual seismicity rate, and **Wadati diagram** for Vp/Vs estimation
- **Focal mechanisms** — beach‑ball rendering for events with moment tensor
  or nodal‑plane data (requires [ObsPy](https://obspy.org/))
- **Station locations** — derived from arrival azimuth/distance
- **Wadati diagram** — `--mode wadati` plots S–P vs P travel times with
  least‑squares Vp/Vs fit; optional `--velocity-model` overlays theoretical
  curves from SeisComP LOCSAT tables and adds model‑predicted S points for
  P‑only stations
- **City labels** — loaded from the SeisComP `cities.xml`, with
  density‑aware collision avoidance and population filtering
- **Professional layout** — scale bar, north arrow, graticule, inset
  overview map, depth colour‑bar, magnitude reference circles,
  event‑type legend
- **OpenStreetMap tiles** — optional `--osm` flag swaps the vector land/ocean
  basemap for OSM raster tiles, providing roads, terrain, and built‑up
  area context beneath event markers
- **Fully configurable** — all colours, sizes, DPI, and dimensions are
  adjustable via CLI
- **Step‑by‑step debug logging** — `--debug` prints extent, margins,
  label counts, and analysis grid stats

## Requirements

| Dependency | Purpose |
|---|---|
| Python ≥ 3.8 | runtime |
| [SeisComP](https://www.seiscomp.de/) ≥ 5.0 | `seiscomp.client`, `seiscomp.datamodel`, `seiscomp.core`, `seiscomp.io`, `seiscomp.logging` |
| numpy | numerical arrays |
| matplotlib ≥ 3.3 | plotting |
| [Cartopy](https://scitools.org.uk/cartopy) ≥ 0.18 | map projections, coastlines, borders |
| ObsPy (optional) | focal‑mechanism beach balls |
| MySQL / PostgreSQL / SQLite driver (optional) | database queries |

### Installing SeisComP Python bindings

The SeisComP Python packages are shipped with the SeisComP installation under
`$SEISCOMP_ROOT/lib/python`.  Set `PYTHONPATH` (or `SEISCOMP_ROOT`) so that
`import seiscomp.client` resolves:

```bash
export SEISCOMP_ROOT=$HOME/seiscomp
export PYTHONPATH=$SEISCOMP_ROOT/lib/python:$PYTHONPATH
```

### Installing Python dependencies

```bash
pip install numpy matplotlib cartopy obspy
```

## Usage

```
scmap [options]
```

### Quick examples

```bash
# Render all events from an SCML file
scmap -i events.xml -o map.png

# Fixed geographic region with custom margin
scmap -i events.xml -o map.png --region 10x8+35+20 -m 5

# Query a single event from the database
scmap -E smi:org.gfz-potsdam/event1 -d sysop:sysop@localhost:18002/seiscomp

# All events from the last 24 hours (limit 50)
scmap --start-time "2026-06-15" -d sysop:sysop@localhost:18002/seiscomp \
  --limit 50 -o map.png

# b-value heatmap, 0.5° grid, 80 km sample radius
scmap -i events.xml --mode bvalue --grid-size 0.5 --grid-radius 80

# Magnitude-completeness map
scmap -i events.xml --mode mc --grid-size 0.5

# Rate map with log file
scmap --start-time "2026-06-01" -d sysop:sysop@localhost:18002/seiscomp \
  --mode rate --grid-size 0.3 --grid-radius 60 --log-file scmap.log

# Thin out city labels in a dense region
scmap -i events.xml --min-city-population 20000 --city-spacing 1.5

# Debug output showing map build steps
scmap -i events.xml --debug

# Use OpenStreetMap raster tiles as the base map
scmap -i events.xml --osm -o map.png

# Wadati diagram for a single event from the database
scmap -E SEC2026mhzy -d localhost --mode wadati -o wadati.png

# Wadati diagram with theoretical overlay from a LOCSAT velocity model
scmap -E SEC2026mhzy -d localhost --mode wadati --velocity-model iasp91_scanloc \
  -o wadati.png
```

### Batch script (`scmap-all.sh`)

Generates all four map modes (events, b‑value, Mc, rate) in a single
invocation.  Edit the defaults at the top of the script to set your own
region and database, or override them via environment variables.

```bash
# Last 7 days (uses $LAT / $LON / $DB defaults)
./scmap-all.sh -d 7

# Last 30 days
./scmap-all.sh -d 30

# Explicit date range
./scmap-all.sh "2026-06-01" "2026-06-18"

# Start date only  →  end defaults to now
./scmap-all.sh "2026-06-15"
```

**Customising the region and database:**

```bash
# Override via environment variables
LAT=50 LON=8 MARGIN=6 DB="sysop:sysop@10.202.50.1:18002/seiscomp" ./scmap-all.sh -d 30

# Or edit the defaults block at the top of scmap-all.sh:
#   LAT="${LAT:--29}"            # centre latitude
#   LON="${LON:-25}"             # centre longitude
#   MARGIN="${MARGIN:-8}"        # margin in degrees
#   DB="${DB:-localhost:18002/seiscomp}"
#   GRID_SIZE="${GRID_SIZE:-1.5}"
#   GRID_RADIUS="${GRID_RADIUS:-300}"
#   MC_HINT="${MC_HINT:-0.5}"
#   RATE_PERIOD="${RATE_PERIOD:-0}"
#   CITY_POP="${CITY_POP:-50000}"
```

Output files: `map_events.png`, `map_bvalue.png`, `map_mc.png`,
`map_rate.png`.

### Example gallery — South Africa, 10–18 Jun 2026

Generated with:
```
./scmap-all.sh "2026-06-10" "2026-06-18"
```

#### Event map
Depth‑coloured event markers with magnitude‑proportional sizing, station
locations derived from arrivals, and city labels for population ≥ 50 000.

![Event map](map_events.png)

#### b‑value heatmap
Gutenberg‑Richter b‑value computed via Aki‑Utsu MLE on a 1.5° × 1.5° grid
with 300 km sampling radius and Mc = 0.5.  Warm (red) = high b‑value,
cool (dark) = low b‑value.  Cells with fewer than 10 events are blank.

![b-value map](map_bvalue.png)

#### Magnitude of completeness (Mc)
Maximum‑curvature Mc estimate on the same grid.  Dark = high Mc (catalogue
complete only at larger magnitudes); bright = low Mc (small events
detected).  Cells with fewer than 15 events are blank.

![Mc map](map_mc.png)

#### Seismicity rate
Weekly event rate (events / km² / week) for M ≥ 0.5, normalised to 7 days.
Bright = high activity, dark = low.  Cells with fewer than 5 events are blank.

![Rate map](map_rate.png)

### Input options

| Flag | Description |
|---|---|
| `-i`, `--input` | SCML XML file (use `"-"` for stdin) |
| `-E`, `--event` | Event ID(s) from database (comma‑separated) |
| `--start-time` | Time‑window start (`"YYYY-MM-DD [HH:MM[:SS]]"`) |
| `--end-time` | Time‑window end (defaults to now) |
| `--limit` | Max events from a time‑range query (0 = unlimited) |

### Map modes (`--mode`)

| Mode | Description |
|---|---|---|
| `events` *(default)* | Individual event markers with depth colouring and magnitude‑proportional size |
| `bvalue` | Gutenberg‑Richter **b‑value** via Aki‑Utsu maximum‑likelihood estimator: `b = log₁₀(e) / (M̄ − Mc)`, where Mc is set by `--mc-hint` |
| `mc` | **Magnitude of completeness** via maximum curvature (MAXC) |
| `rate` | **Annual seismicity rate** (events / km² / year) above Mc set by `--mc-hint` |
| `wadati` | **Wadati diagram** — plots S‑P vs P travel times for stations with both phases.  A linear least‑squares fit gives Vp/Vs = slope + 1.  When `--velocity-model` is set, theoretical travel times from the model are overlaid and P‑only stations contribute model‑predicted S‑P points (orange squares) |

All analysis modes use a grid with configurable `--grid-size` (degrees) and
`--grid-radius` (km).  Each grid node samples events within the radius and
requires a minimum count before computing a value.

### Analysis options

| Flag | Default | Description |
|---|---|---|
| `--grid-size` | 0.5 | Grid cell spacing in degrees |
| `--grid-radius` | 50 | Sample radius in kilometres |
| `--mc-hint` | 1.5 | Lower magnitude cutoff for b‑value and rate |
| `--rate-period` | 0 | Rate normalisation in days (0 = auto annual).  Set to 7 for weekly, 1 for daily |
| `--velocity-model` | — | SeisComP LOCSAT travel‑time table profile (e.g. `iasp91`, `iasp91_scanloc`, `tab`).  Overlays theoretical travel‑time curves on the Wadati diagram and derives model‑predicted S‑P values for stations with only a P pick.  Only used with `--mode wadati` |

### Map layout

| Flag | Default | Description |
|---|---|---|
| `-o`, `--output` | `map.png` | Output PNG path |
| `-r`, `--region` | — | Map region (`lat×lon+lat₀+lon₀` or `+lat₀+lon₀+lat₁+lon₁`) |
| `-m`, `--margin` | 3.0 | Margin in degrees around event centre |
| `--lat` | — | Centre latitude |
| `--lon` | — | Centre longitude |
| `--dimension` | `1600×1000` | Output size in pixels (`WxH`) |
| `--dpi` | 150 | Output resolution |
| `--title` | — | Override map title |

### Rendering controls

| Flag | Default | Description |
|---|---|---|
| `--depth-max` | 200 | Maximum depth for colour scale (km) |
| `--min-mag` | 0 | Minimum magnitude for marker scale |
| `--max-mag` | 8 | Maximum magnitude for marker scale |
| `--min-marker-size` | 20 | Minimum marker area |
| `--max-marker-size` | 450 | Maximum marker area |

### City labels

| Flag | Default | Description |
|---|---|---|
| `--min-city-population` | 100 000 | Minimum population to display a label |
| `--city-spacing` | 1.0 | Spacing multiplier — higher = fewer labels, lower = more |
| `--no-cities` | — | Disable all city labels |

City label placement uses a density‑aware collision‑avoidance algorithm:

1. **Text‑size estimate** — converts font size, character count, canvas
   dimensions, and DPI into an approximate degree‑span for each label.
2. **Density multiplier** — when candidate density exceeds 3 cities/deg²,
   margins are scaled up (up to 4×) to thin out labels in crowded regions.
3. **User factor** — `--city-spacing` acts as a global multiplier on all
   margins.  Values below 1.0 allow more labels (tighter), values above
   produce sparser labels.

### Display toggles

| Flag | Effect |
|---|---|
| `--no-legend` | Hide legend / parameter box |
| `--no-stations` | Hide station triangles |
| `--no-beachballs` | Hide focal‑mechanism beach balls |
| `--no-borders` | Hide country borders |
| `--no-inset` | Hide overview inset map |
| `--no-labels` | Hide magnitude text labels on event markers |
| `--no-cities` | Hide city labels |
| `--show-rivers` | Draw major rivers |
| `--show-states` | Draw province/state boundaries |

### Standard SeisComP options

Inherited from `seiscomp.client.Application`:

| Flag | Description |
|---|---|
| `-d`, `--database` | Database URI: `[mysql://]user:pass@host[:port]/db` |
| `-H`, `--host` | Messaging host/queue (default `localhost/production`) |
| `--debug` | Debug logging (`--verbosity=4 --console=1`) |
| `--log-file` | Write log output to file instead of stderr |
| `--plugins` | Load SeisComP plugins |
| `--offline` | Disable messaging connections |
| `-h`, `--help` | Show full help |
| `-V`, `--version` | Show framework version |

## Database connection

The `-d` flag accepts SeisComP‑style database URIs:

```
sysop:sysop@localhost:18002/seiscomp
mysql://sysop:sysop@localhost/seiscomp
```

Without a scheme prefix, the driver is inferred from `core.plugins` in
`global.cfg` (e.g. `dbmysql`, `dbpostgresql`, `dbsqlite3`).

## Logging

- **Default** (no `--log-file`): messages go to stderr (terminal).
- **With `--log-file scmap.log`**: messages go to the file; console is
  silent.
- **`--debug`**: enables verbose step‑by‑step diagnostic output including
  map extent, margin, grid dimensions, label counts, collision margins,
  analysis cell fill‑rates, and render timing.

## Design principles

scmap follows established seismological map conventions:

### Depth colour scale

Uses `inferno_r` — a **perceptually uniform**, **colourblind‑safe**
colormap that progresses warm‑shallow to cool‑deep.  This avoids the
traditional red‑green‑blue triad which fails under deuteranopia (~5 % of
males) and produces phantom discontinuities.  All Crameri/Brewer scientific
colormaps pass CVD testing; `jet` and `rainbow` are explicitly rejected by
Nature, EGU journals, and Crameri et al. (2020).

### Magnitude‑to‑size scaling

Markers scale by area ∝ **10^M** (moment‑proportional) rather than energy
(10^(1.5M)).  This keeps the size range manageable — M 8 events remain
readable without overwhelming the map — while preserving the relative
visual weight between magnitudes.  Reference circles at M 2, 4, 6, 8
appear in the legend, drawn to the exact scale used on the map.

### Basemap

Low‑saturation land (`#F2EFE9`, pale tan) and ocean (`#DCE4EC`, pale
steel‑blue) maximise contrast with event markers — a Tufte "data‑ink
ratio" approach.  Coastlines (0.3 pt), borders (0.2 pt), and grid lines
(0.15 pt) are deliberately thin to let the data dominate.

### Typography

Clear hierarchy: 14 pt bold title → 8 pt subtitle → 7 pt legend
titles → 6 pt legend body → 5 pt magnitude labels.  All labels use
sans‑serif for readability at small sizes.  Ink weight increases with
importance.

## Event type symbols

scmap recognises all SeisComP event types and groups them for the legend:

| Group | Symbol | Example types |
|---|---|---|
| Earthquake | ● | `earthquake` |
| Induced / Triggered | ◆ | `induced earthquake`, `fluid injection` |
| Explosion / Blast | ★ (red) | `quarry blast`, `nuclear explosion` |
| Volcanic | ▲ (purple) | `volcanic eruption`, `lahar` |
| Landslide / Avalanche | ▼ | `landslide`, `rock avalanche` |
| Collapse | ■ | `mine collapse`, `building collapse` |
| Rock Burst | ■ (orange) | `rock burst` |
| Meteor / Impact | ✕ (orange) | `meteor impact`, `meteorite` |
| Sonic | ⎯ | `sonic boom` |
| Anthropogenic | ◆ | `anthropogenic event` |
| Other / Unknown | · | `not reported`, `other event` |

## Project structure

```
scmap/
├── scmap.py           # main application
├── scmap-all.sh       # batch script — all four map modes in one run
├── scmap.txt          # usage reference (auto‑generated by --help)
├── map.png            # sample output
├── README.md          # this file
└── .gitignore
```

## Algorithm details

### b‑value

The Aki‑Utsu (1965) maximum‑likelihood estimator for magnitudes M ≥ Mc:

$$b = \frac{\log_{10}(e)}{\bar{M} - M_c}$$

where $\bar{M}$ is the mean magnitude and $M_c$ is a fixed completeness
threshold (`mc_hint`, default 0.5 in the batch script, configurable via
`--mc-hint`).  Grid nodes with fewer than 10 events are left blank (NaN).

### Magnitude of completeness (Mc)

The maximum curvature method (MAXC; Wiemer & Wyss 2000) bins events by
0.1 magnitude units and finds the bin with the highest frequency.  Mc is
estimated as the bin centre + 0.2.  Nodes with fewer than 15 events are
left blank.

### Seismicity rate

Annual event rate per km² for M ≥ Mc, where Mc is set by `--mc-hint`:

$$\text{rate} = \frac{N}{\pi r^2 \cdot \Delta t}$$

where $N$ is the event count within radius $r$, and $\Delta t$ is the
catalogue time span in years.  Nodes with fewer than 5 events are blank.

### Wadati diagram

For each origin, arrivals are grouped by phase code (via `Phase.code()` — P‑type
starting with `P`, S‑type starting with `S`).  A P arrival is paired with the
S arrival from the same station by minimising the distance difference
(tolerance ≤ 0.5°) and checking azimuth consistency (≤ 10°).  The P travel time
is derived from the pick time minus origin time (not from `arrival.time()`,
which is often unset in the database).

For each pair the point $(T_P, T_S - T_P)$ is plotted.  A linear
least‑squares fit

$$T_S - T_P = \alpha \cdot T_P + \beta$$

gives the Vp/Vs ratio as $\alpha + 1$.  RMSE and $R^2$ are displayed in the
info box.

When `--velocity-model` is given:
- **Theoretical curve** — the LOCSAT travel‑time table computes P and S
  travel times at each paired station's distance.  These are plotted as a
  green scatter with a separate Vp/Vs line.
- **P‑only stations** — stations with only a P pick receive a
  model‑predicted S travel time, plotted as orange squares.  This fills the
  diagram with additional data without requiring S picks.

## Contributing

1. Ensure SeisComP Python bindings are on `PYTHONPATH`.
2. Make changes to `scmap.py`.
3. Run `python3 scmap.py --help` to verify CLI integrity.
4. Test with both XML file input and database input where possible.

## Author

**Donavin Liebgott** — [donavinliebgott@gmail.com](mailto:donavinliebgott@gmail.com)

## License

This project is provided as‑is.  SeisComP is distributed under the
[GNU AGPL v3](https://www.gnu.org/licenses/agpl-3.0.html) by the
[GEOFON Program](https://geofon.gfz-potsdam.de/) at
[GFZ Potsdam](https://www.gfz-potsdam.de/).

## References

- Aki, K. (1965). *Maximum likelihood estimate of b in the formula
  log N = a − bM and its confidence limits.* Bull. Earthq. Res. Inst.,
  43, 237–239.
- Crameri, F., Shephard, G.E., & Heron, P.J. (2020). *The misuse of
  colour in science communication.* Nature Comms., 11, 5444.
- Tufte, E.R. (2001). *The Visual Display of Quantitative Information*
  (2nd ed.). Graphics Press.
- Wessel, P., Luis, J.F., Uieda, L., et al. (2019). *The Generic
  Mapping Tools version 6.* Geochem. Geophys. Geosyst., 20, 5556–5564.
- Wiemer, S. & Wyss, M. (2000). *Minimum magnitude of completeness in
  earthquake catalogs: Examples from Alaska, the Western United States,
  and Japan.* Bull. Seismol. Soc. Am., 90(4), 859–869.
- [SeisComP documentation](https://www.seiscomp.de/)
- [SeisComP on GitHub](https://github.com/SeisComP)
- [Crameri Scientific Colormaps](https://www.fabiocrameri.ch/colourmaps/)

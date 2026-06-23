# scmap Pro — Planned features

This document tracks features under consideration for the Pro edition.
Priorities and timelines are driven by customer demand.

## Legend

| Icon | Meaning |
|---|---|
| 🟢 | Shipped |
| 🟡 | In development |
| 🔵 | Planned |
| ⚪ | Under consideration |

---

## High-value features

### 🟡 Vector export

Generate publication-ready vector figures in addition to PNG.

| Format | Community | Pro |
|---|---|---|
| PNG (raster, 150 dpi) | ✅ | ✅ |
| PNG (raster, configurable up to 600 dpi) | — | ✅ |
| **PDF** (vector text, raster basemap) | — | ✅ |
| **SVG** (fully editable in Illustrator / Inkscape) | — | ✅ |

*Why it sells:* Most journals (Nature, GRL, SRL, BSSA) prefer vector figures.
Currently users rasterise → Inkscape → re-export, which takes 10–15 min per
figure. Pro does it in one command.

### 🔵 Map templates

Save and restore the full configuration as a JSON profile.

```bash
# Save a publication template once
scmap --save-template publication.json \
  --dimension 2400x1600 --dpi 300 \
  --font-scale 1.2 --depth-max 100 \
  --no-stations --no-inset --no-cities

# Reuse for every weekly update
./scmap-all.sh -d 7 --template publication.json
```

Templates cover: dimension, DPI, margin, grid parameters, colour settings,
display toggles, font scaling.

*Why it sells:* Monitoring labs run the same map daily or weekly. Templates
eliminate flag repetition and guarantee consistent output across the team.

### 🔵 Catalogue statistics panel

Optional inset panel on the map showing:

- Magnitude–frequency distribution (log10 N vs M histogram)
- Cumulative moment release curve
- Weekly/daily event count time history
- Depth histogram

Toggle with `--stats` flag, position with `--stats-position`.

*Why it sells:* Agencies include these plots in weekly bulletins. Currently
they export from scmap then build stats in a separate Python/Matlab script.
Pro combines them into a single figure.

---

## Niche but defensible features

### 🔵 Depth cross-sections

```bash
scmap -i events.xml --cross-section 25,-30,30,-25 \
  --cross-section-width 50 --cross-section-depth 50 -o cross_section.png
```

Projects events within a swath width onto a vertical profile along a
great-circle path.  Includes topographic surface, station projections, and
Mc-constrained magnitude completeness shading.

*Why it sells:* Sequence monitoring teams need cross-sections for hazard
assessment.  Current workflow: scmap for the map → GMT/Matlab for the
section.  Pro collapses this to one command.

### ⚪ Custom branding / white-label

```bash
scmap --mode events \
  --logo institution_logo.png --logo-position bottom-right \
  --brand-color "#003366" --institution "SARAO"
```

Places an institution logo on the map and applies a brand colour to accent
elements (title, legend headers).  Matching colour scales available for the
analysis grid modes.

### ⚪ WMS / GeoJSON station overlay

```bash
scmap --station-wms "https://geoserver.institution.ac.za/wms?layers=seismic_stations"
scmap --station-geojson network_stations.geojson
```

Overlay custom vector layers (station networks, faults, isoseismal lines)
from WMS servers or GeoJSON files.  Supplements the built-in station
locations derived from arrivals.

*Why it sells:* Every monitoring network has a station map they maintain in
GIS.  Pro lets them use it directly instead of relying on the
arrival-derived station set.

### ⚪ Multi-frame animated maps

```bash
scmap --start-time "2026-01-01" --end-time "2026-06-01" \
  --animate --frame-days 7 -o animation.gif
```

Generates a sequence of maps at regular intervals and composites them into an
animated GIF or MP4.  Useful for conference presentations and public
outreach.

---

## Community features (always free)

These ship in both editions — kept here for reference.

- ✅ All map modes: events, b-value, Mc, rate, Wadati
- ✅ OpenStreetMap raster tiles (`--osm`)
- ✅ OpenTopoMap terrain tiles (`--topo`)
- ✅ Focal mechanism beach balls (requires ObsPy)
- ✅ Station locations from arrival data
- ✅ City labels with collision avoidance
- ✅ Depth colour bar, magnitude reference circles
- ✅ Wadati diagram with Vp/Vs fitting
- ✅ LOCSAT velocity model overlay (Wadati)
- ✅ Batch script (`scmap-all.sh`)
- ✅ Configurable dimensions, DPI, margins
- ✅ Step-by-step debug logging

---

## How features are prioritised

1. **Customer requests** — if two Pro users ask for the same feature, it
   moves to the top of the queue.
2. **Publication workflow** — features that save a step between scmap output
   and journal submission are prioritised over cosmetic additions.
3. **Implementation cost** — features are ordered by expected effort, with
   quick wins shipping first to validate demand.

To suggest or vote for a feature, contact
[donavinliebgott@gmail.com](mailto:donavinliebgott@gmail.com).

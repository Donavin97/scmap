#!/usr/bin/env seiscomp-python
# -*- coding: utf-8 -*-
"""
scmap – SeisComP seismic event map generator.

Generates high-resolution PNG maps from SeisComP event parameters. Supports:

  - Reading QuakeML XML files exported via scxmldump (offline mode)
  - Direct database queries by event ID (online mode, requires -d)
  - Multiple event types with distinct symbols (explosions: stars,
    earthquakes: circles, landslides: triangles, etc.)
  - Magnitude-proportional symbol sizes
  - Depth-based coloring
  - Beach balls for focal mechanisms (requires obspy)
  - Station locations derived from arrival data
  - Comprehensive legend with event types, magnitude scale, depth colorbar
  - Scale bar, grid lines, country borders
  - Inset overview map

Usage:
    scmap -i events.xml -o map.png
    scmap -i events.xml -o map.png --region 5x5+45+10
    scmap -i events.xml -o map.png -m 3
    scmap -E smi:org.gfz-potsdam/event1 -d mysql://sysop:sysop@localhost/seiscomp -o map.png
"""

import sys
import os
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# ── SeisComP Python bindings ──────────────────────────────────────────────
import seiscomp.client
import seiscomp.io
import seiscomp.datamodel as dm
import seiscomp.core
import seiscomp.logging

# ── Optional: obspy for beach balls ───────────────────────────────────────
try:
    from obspy.imaging.beachball import beach as _beach_patch
    HAS_OBSPY_BEACH = True
except ImportError:
    HAS_OBSPY_BEACH = False


# ═══════════════════════════════════════════════════════════════════════════
# Event type → symbol mapping  (seismological conventions)
# ═══════════════════════════════════════════════════════════════════════════

EVENT_TYPE_CONFIG = {
    dm.EARTHQUAKE:                    ('o',     'Earthquake',              None),
    dm.INDUCED_EARTHQUAKE:            ('D',     'Induced Earthquake',      None),
    dm.INDUCED_OR_TRIGGERED_EVENT:    ('D',     'Induced/Triggered',       None),
    dm.QUARRY_BLAST:                  ('*',     'Quarry Blast',            '#e74c3c'),
    dm.MINING_EXPLOSION:              ('*',     'Mining Explosion',        '#e74c3c'),
    dm.EXPLOSION:                     ('*',     'Explosion',               '#e74c3c'),
    dm.CHEMICAL_EXPLOSION:            ('*',     'Chemical Explosion',      '#e74c3c'),
    dm.NUCLEAR_EXPLOSION:             ('*',     'Nuclear Explosion',       '#c0392b'),
    dm.CONTROLLED_EXPLOSION:          ('*',     'Controlled Explosion',    '#e74c3c'),
    dm.INDUSTRIAL_EXPLOSION:          ('*',     'Industrial Explosion',    '#e74c3c'),
    dm.ACCIDENTAL_EXPLOSION:          ('*',     'Accidental Explosion',    '#e74c3c'),
    dm.EXPERIMENTAL_EXPLOSION:        ('*',     'Experimental Explosion',  '#e74c3c'),
    dm.LANDSLIDE:                     ('v',     'Landslide',               None),
    dm.ROCKSLIDE:                     ('v',     'Rockslide',               None),
    dm.DEBRIS_AVALANCHE:              ('v',     'Debris Avalanche',       None),
    dm.SNOW_AVALANCHE:                ('v',     'Snow Avalanche',          None),
    dm.AVALANCHE:                     ('v',     'Avalanche',               None),
    dm.SUBMARINE_LANDSLIDE:           ('v',     'Submarine Landslide',     None),
    dm.VOLCANIC_ERUPTION:             ('^',     'Volcanic Eruption',       '#8e44ad'),
    dm.VOLCANO_TECTONIC:              ('^',     'Volcano-tectonic',        '#8e44ad'),
    dm.VOLCANIC_LONG_PERIOD:          ('^',     'Volcanic LP',             '#8e44ad'),
    dm.VOLCANIC_VERY_LONG_PERIOD:     ('^',     'Volcanic VLP',            '#8e44ad'),
    dm.VOLCANIC_HYBRID:               ('^',     'Volcanic Hybrid',         '#8e44ad'),
    dm.VOLCANIC_ROCKFALL:             ('^',     'Volcanic Rockfall',       '#8e44ad'),
    dm.VOLCANIC_TREMOR:               ('^',     'Volcanic Tremor',         '#8e44ad'),
    dm.PYROCLASTIC_FLOW:              ('^',     'Pyroclastic Flow',        '#8e44ad'),
    dm.LAHAR:                         ('^',     'Lahar',                  '#8e44ad'),
    dm.MINE_COLLAPSE:                 ('s',     'Mine Collapse',           None),
    dm.BUILDING_COLLAPSE:             ('s',     'Building Collapse',       None),
    dm.COLLAPSE:                      ('s',     'Collapse',                None),
    dm.CAVITY_COLLAPSE:               ('s',     'Cavity Collapse',         None),
    dm.METEOR_IMPACT:                 ('X',     'Meteor Impact',           '#e67e22'),
    dm.METEORITE:                     ('X',     'Meteorite',               '#e67e22'),
    dm.ATMOSPHERIC_METEOR_EXPLOSION:  ('X',     'Atm. Meteor Explosion',   '#e67e22'),
    dm.SONIC_BOOM:                    ('h',     'Sonic Boom',              None),
    dm.SONIC_BLAST:                   ('h',     'Sonic Blast',             None),
    dm.ROCK_BURST:                    ('s',     'Rock Burst',              None),
    dm.ICE_QUAKE:                     ('D',     'Ice Quake',               None),
    dm.FROST_QUAKE:                   ('D',     'Frost Quake',             None),
    dm.TREMOR_PULSE:                  ('D',     'Tremor Pulse',            None),
    dm.ANTHROPOGENIC_EVENT:           ('p',     'Anthropogenic',           None),
    dm.ROCKET_LAUNCH:                 ('*',     'Rocket Launch',           '#e74c3c'),
    dm.ROCKET_IMPACT:                 ('*',     'Rocket Impact',           '#e74c3c'),
    dm.PLANE_CRASH:                   ('X',     'Plane Crash',             None),
    dm.TRAIN_CRASH:                   ('X',     'Train Crash',             None),
    dm.BOAT_CRASH:                    ('X',     'Boat Crash',              None),
    dm.CRASH:                         ('X',     'Crash',                   None),
    dm.FLUID_INJECTION:               ('D',     'Fluid Injection',         None),
    dm.FLUID_EXTRACTION:              ('D',     'Fluid Extraction',        None),
    dm.RESERVOIR_LOADING:             ('D',     'Reservoir Loading',       None),
    dm.ARTILLERY_STRIKE:              ('*',     'Artillery Strike',        '#e74c3c'),
    dm.BOMB_DETONATION:               ('*',     'Bomb Detonation',         '#c0392b'),
    dm.NOT_REPORTED:                  ('.',     'Not Reported',            None),
    dm.OTHER_EVENT:                   ('.',     'Other Event',             None),
    dm.NOT_EXISTING:                  ('.',     'Not Existing',            None),
    dm.NOT_LOCATABLE:                 ('.',     'Not Locatable',           None),
    dm.DUPLICATE:                     ('.',     'Duplicate',               None),
    dm.OUTSIDE_OF_NETWORK_INTEREST:   ('.',     'Outside Interest',        None),
}

EVENT_TYPE_GROUPS = {
    'Earthquake':              ('o', None),
    'Induced / Triggered':     ('D', None),
    'Explosion / Blast':       ('*', '#e74c3c'),
    'Rock Burst':              ('s', '#d35400'),
    'Landslide / Avalanche':   ('v', None),
    'Volcanic':                ('^', '#8e44ad'),
    'Collapse':                ('s', None),
    'Meteor / Impact':         ('X', '#e67e22'),
    'Sonic':                   ('h', None),
    'Anthropogenic':           ('p', None),
    'Other / Unknown':         ('.', None),
}

DEPTH_CMAP = plt.cm.viridis_r


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════

def depth_color(depth_km, vmin=0, vmax=200):
    norm = max(vmin, min(vmax, depth_km))
    return DEPTH_CMAP((norm - vmin) / max(1, vmax - vmin))


def mag_to_size(magnitude, min_mag=0, max_mag=9, min_size=20, max_size=500):
    if magnitude is None:
        return min_size
    mag_clipped = max(min_mag, min(max_mag, magnitude))
    energy_scale = 10 ** (1.5 * mag_clipped)
    energy_min = 10 ** (1.5 * min_mag)
    energy_max = 10 ** (1.5 * max_mag)
    frac = (energy_scale - energy_min) / max(1, energy_max - energy_min)
    return min_size + frac * (max_size - min_size)


def _safe_attr(obj, method_name, *args):
    try:
        method = getattr(obj, method_name, None)
        if method is None:
            return None
        result = method(*args)
        if hasattr(result, 'value'):
            return result.value()
        return result
    except Exception:
        return None


def _safe_str(obj, method_name, *args):
    val = _safe_attr(obj, method_name, *args)
    if val is None:
        return ''
    return str(val)


# ═══════════════════════════════════════════════════════════════════════════
# SeismicEvent container
# ═══════════════════════════════════════════════════════════════════════════

class SeismicEvent:
    __slots__ = (
        'public_id', 'event_type', 'event_type_name',
        'type_certainty', 'latitude', 'longitude', 'depth_km',
        'origin_time', 'magnitude_value', 'magnitude_type',
        'evaluation_mode', 'evaluation_status',
        'n_phases', 'n_stations', 'rms', 'azimuthal_gap',
        'has_focal_mechanism', 'fm_strike', 'fm_dip', 'fm_rake',
        'arrivals', 'region_name',
    )

    def __init__(self):
        self.public_id = ''
        self.event_type = None
        self.event_type_name = 'Unknown'
        self.type_certainty = None
        self.latitude = None
        self.longitude = None
        self.depth_km = None
        self.origin_time = None
        self.magnitude_value = None
        self.magnitude_type = ''
        self.evaluation_mode = None
        self.evaluation_status = None
        self.n_phases = 0
        self.n_stations = 0
        self.rms = None
        self.azimuthal_gap = None
        self.has_focal_mechanism = False
        self.fm_strike = None
        self.fm_dip = None
        self.fm_rake = None
        self.arrivals = []
        self.region_name = ''


# ═══════════════════════════════════════════════════════════════════════════
# Data extraction
# ═══════════════════════════════════════════════════════════════════════════

def extract_events(ep):
    events = []
    n_events = ep.eventCount()
    seiscomp.logging.debug(
        "Parsing EventParameters: %d event(s), %d origin(s), %d pick(s)"
        % (n_events, ep.originCount(), ep.pickCount()))

    agency = ''
    author = ''
    sc_version = _seiscomp_version_string()

    for i in range(n_events):
        ev = ep.event(i)
        se = SeismicEvent()
        se.public_id = ev.publicID()
        se.event_type = _safe_attr(ev, 'type')
        se.event_type_name = _event_type_label(se.event_type)
        se.type_certainty = _safe_attr(ev, 'typeCertainty')

        # Preferred origin
        org = _find_preferred_origin(ep, ev.publicID())
        if org is None and ep.originCount() > 0:
            org = ep.origin(0)

        if org is not None:
            se.latitude = _safe_attr(org, 'latitude')
            se.longitude = _safe_attr(org, 'longitude')
            se.depth_km = _safe_attr(org, 'depth')
            se.origin_time = _safe_attr(org, 'time')
            se.evaluation_mode = _safe_attr(org, 'evaluationMode')
            se.evaluation_status = _safe_attr(org, 'evaluationStatus')

            # Quality
            try:
                q = org.quality()
                se.rms = _safe_attr(q, 'standardError')
                se.azimuthal_gap = _safe_attr(q, 'azimuthalGap')
            except Exception:
                pass

            # Arrivals
            for k in range(org.arrivalCount()):
                arr = org.arrival(k)
                phase = _safe_str(arr, 'phase') or '?'
                dist = _safe_attr(arr, 'distance')
                az = _safe_attr(arr, 'azimuth')
                se.arrivals.append((phase, dist, az))
            se.n_phases = len(se.arrivals)

        # Magnitude
        mag = _find_preferred_magnitude(ev, org)
        if mag is not None:
            se.magnitude_value = _safe_attr(mag, 'magnitude')
            se.magnitude_type = _safe_str(mag, 'type')

        # Focal mechanism
        fm = _find_preferred_focal_mechanism(ev, ep)
        if fm is not None:
            se.has_focal_mechanism = True
            _extract_fm_data(fm, se)

        # Region name
        for k in range(ev.eventDescriptionCount()):
            ed = ev.eventDescription(k)
            ed_type = _safe_attr(ed, 'type')
            if ed_type == dm.FLINN_ENGDAHL_REGION:
                se.region_name = _safe_str(ed, 'text') or ''
            elif ed_type == dm.REGION_NAME:
                if not se.region_name:
                    se.region_name = _safe_str(ed, 'text') or ''

        # Agency / author from first event
        if not agency:
            try:
                ci = ev.creationInfo()
                if ci:
                    a = _safe_str(ci, 'agencyID')
                    au = _safe_str(ci, 'author')
                    if a:
                        agency = a
                    if au:
                        author = au
            except Exception:
                pass
            if not agency and org is not None:
                try:
                    ci = org.creationInfo()
                    if ci:
                        a = _safe_str(ci, 'agencyID')
                        if a:
                            agency = a
                except Exception:
                    pass

        events.append(se)

    # Time range
    times = [e.origin_time for e in events if e.origin_time is not None]
    t_start = min(times).toString("%Y-%m-%d %H:%M:%S") if times else ''
    t_end = max(times).toString("%Y-%m-%d %H:%M:%S") if times else ''
    if t_start == t_end:
        time_range = t_start
    else:
        time_range = f'{t_start}  \u2013  {t_end}'

    metadata = {
        'agency': agency or '\u2014',
        'author': author or '',
        'version': sc_version,
        'n_events': len(events),
        'time_range': time_range,
    }

    return events, metadata


def _event_type_label(event_type_int):
    if event_type_int is None:
        return 'Unknown'
    info = EVENT_TYPE_CONFIG.get(event_type_int)
    if info:
        return info[1]
    return f'Unknown({event_type_int})'


def _find_preferred_origin(ep, event_public_id):
    n_origins = ep.originCount()
    for i in range(ep.eventCount()):
        ev = ep.event(i)
        if ev.publicID() == event_public_id:
            pref_id = _safe_str(ev, 'preferredOriginID')
            if pref_id:
                for j in range(n_origins):
                    org = ep.origin(j)
                    if org.publicID() == pref_id:
                        return org
            for j in range(ev.originReferenceCount()):
                try:
                    ref = ev.originReference(j)
                    ref_id = ref.originID()
                    for k in range(n_origins):
                        org = ep.origin(k)
                        if org.publicID() == ref_id:
                            return org
                except Exception:
                    pass
    return None


def _find_preferred_magnitude(ev, org):
    pref_mag_id = _safe_str(ev, 'preferredMagnitudeID')
    if org is not None:
        for j in range(org.magnitudeCount()):
            m = org.magnitude(j)
            if pref_mag_id and m.publicID() == pref_mag_id:
                return m
        if org.magnitudeCount() > 0:
            return org.magnitude(0)
    return None


def _find_preferred_focal_mechanism(ev, ep):
    pref_fm_id = _safe_str(ev, 'preferredFocalMechanismID')
    if not pref_fm_id:
        return None
    for k in range(ep.focalMechanismCount()):
        fm = ep.focalMechanism(k)
        if fm.publicID() == pref_fm_id:
            return fm
    return None


def _extract_fm_data(fm, se):
    np_planes = _safe_attr(fm, 'nodalPlanes')
    if np_planes is not None:
        try:
            plane = np_planes.nodalPlane1()
            pref = _safe_attr(np_planes, 'preferredPlane')
            if pref == 2:
                plane = np_planes.nodalPlane2()
        except Exception:
            plane = np_planes.nodalPlane1()
        se.fm_strike = _safe_attr(plane, 'strike') or 0
        se.fm_dip = _safe_attr(plane, 'dip') or 90
        se.fm_rake = _safe_attr(plane, 'rake') or 0
        return

    for k in range(fm.momentTensorCount()):
        mt = fm.momentTensor(k)
        t = _safe_attr(mt, 'tensor')
        if t is None:
            continue
        mtt = _safe_attr(t, 'Mtt') or 0
        mpp = _safe_attr(t, 'Mpp') or 0
        mrr = _safe_attr(t, 'Mrr') or 0
        mrt = _safe_attr(t, 'Mrt') or 0
        mrp = _safe_attr(t, 'Mrp') or 0
        mtp = _safe_attr(t, 'Mtp') or 0
        try:
            strike, dip, rake = _mt2sdr(mrr, mtt, mpp, mrt, mrp, mtp)
            se.fm_strike = strike
            se.fm_dip = dip
            se.fm_rake = rake
        except Exception:
            pass
        break


# ═══════════════════════════════════════════════════════════════════════════
# Moment tensor → strike/dip/rake  (NED convention)
# ═══════════════════════════════════════════════════════════════════════════

def _mt2sdr(mrr, mtt, mpp, mrt, mrp, mtp):
    m = np.array([
        [mtt, mtp, mrt],
        [mtp, mpp, mrp],
        [mrt, mrp, mrr]
    ], dtype=float)
    eigenvalues, eigenvectors = np.linalg.eigh(m)
    idx = np.argsort(eigenvalues)
    t_vec = eigenvectors[:, idx[2]]
    p_vec = eigenvectors[:, idx[0]]

    t_vec = t_vec / np.linalg.norm(t_vec)
    p_vec = p_vec / np.linalg.norm(p_vec)

    n = t_vec + p_vec
    n = n / np.linalg.norm(n)
    u = t_vec - p_vec
    u = u / np.linalg.norm(u)

    nz = max(-1.0, min(1.0, n[2]))
    dip = math.degrees(math.acos(nz))

    if abs(nz) > 0.9999:
        strike = 0.0
    else:
        strike = math.degrees(math.atan2(-n[0], n[1])) % 360

    phi = math.radians(strike)
    delta = math.radians(dip)
    cos_p = math.cos(phi)
    sin_p = math.sin(phi)
    cos_d = math.cos(delta)
    sin_d = math.sin(delta)

    u1 = cos_p * u[0] + sin_p * u[1]
    u2 = -sin_p * u[0] + cos_p * u[1]
    u3 = u[2]
    us = cos_d * u1 - sin_d * u3
    ud = sin_d * u1 + cos_d * u3

    if abs(us) < 1e-10 and abs(ud) < 1e-10:
        rake = 0.0
    else:
        rake = math.degrees(math.atan2(-ud, us)) % 360

    return strike, dip, rake


# ═══════════════════════════════════════════════════════════════════════════
# Region parsing
# ═══════════════════════════════════════════════════════════════════════════

def _parse_region(region_str):
    import re
    s = region_str.strip()

    m = re.match(r'^\+([\d.\-]+)\+([\d.\-]+)\+([\d.\-]+)\+([\d.\-]+)$', s)
    if m:
        lat0, lon0, lat1, lon1 = map(float, m.groups())
        return (min(lon0, lon1), max(lon0, lon1), min(lat0, lat1), max(lat0, lat1))

    m = re.match(r'^([\d.]+)x([\d.]+)\+([\d.\-]+)\+([\d.\-]+)$', s)
    if m:
        lat_dim, lon_dim, lat0, lon0 = map(float, m.groups())
        return (lon0, lon0 + lon_dim, lat0, lat0 + lat_dim)

    m = re.match(r'^([\d.\-]+)/([\d.\-]+)/([\d.\-]+)/([\d.\-]+)$', s)
    if m:
        lon0, lon1, lat0, lat1 = map(float, m.groups())
        return (min(lon0, lon1), max(lon0, lon1), min(lat0, lat1), max(lat0, lat1))

    raise ValueError(f"Invalid region: {region_str}")


# ═══════════════════════════════════════════════════════════════════════════
# Azimuth + distance → lat/lon  (spherical earth approx.)
# ═══════════════════════════════════════════════════════════════════════════

def _az_dist_to_latlon(lat, lon, azimuth_deg, distance_deg):
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    az_r = math.radians(azimuth_deg)
    dist_r = math.radians(distance_deg)

    sin_lat = math.sin(lat_r)
    cos_lat = math.cos(lat_r)
    sin_dist = math.sin(dist_r)
    cos_dist = math.cos(dist_r)
    sin_az = math.sin(az_r)
    cos_az = math.cos(az_r)

    new_lat = math.asin(sin_lat * cos_dist + cos_lat * sin_dist * cos_az)
    new_lon = lon_r + math.atan2(sin_az * sin_dist * cos_lat,
                                 cos_dist - sin_lat * math.sin(new_lat))
    return math.degrees(new_lat), math.degrees(new_lon)


# ═══════════════════════════════════════════════════════════════════════════
# City data loader (from SeisComP cities.xml)
# ═══════════════════════════════════════════════════════════════════════════

SEISCOMP_ROOT = os.environ.get(
    'SEISCOMP_ROOT',
    os.path.expanduser('/home/seismocomp/seiscomp')
)
CITIES_XML_PATH = os.path.join(SEISCOMP_ROOT, 'share', 'cities.xml')


def load_cities(lon_min, lon_max, lat_min, lat_max, min_population=100000):
    if not os.path.isfile(CITIES_XML_PATH):
        seiscomp.logging.warning("Cities file not found: %s" % CITIES_XML_PATH)
        return

    try:
        context = ET.iterparse(CITIES_XML_PATH, events=('end',))
        for _, elem in context:
            if elem.tag != 'City':
                continue

            try:
                name_el = elem.find('name')
                lat_el = elem.find('latitude')
                lon_el = elem.find('longitude')
                pop_el = elem.find('population')

                if name_el is None or lat_el is None or lon_el is None:
                    elem.clear()
                    continue
                if lat_el.text is None or lon_el.text is None:
                    elem.clear()
                    continue

                lat = float(lat_el.text)
                lon = float(lon_el.text)

                if not (lon_min <= lon <= lon_max and
                        lat_min <= lat <= lat_max):
                    elem.clear()
                    continue

                pop = int(pop_el.text) if pop_el is not None and pop_el.text else 0
                if pop < min_population:
                    elem.clear()
                    continue

                name = name_el.text.strip() if name_el.text else ''
                if not name:
                    elem.clear()
                    continue

                is_capital = elem.get('category') == 'C'
                yield (name, lat, lon, pop, is_capital)
            except (ValueError, TypeError, AttributeError):
                pass
            finally:
                elem.clear()

    except ET.ParseError as e:
        seiscomp.logging.warning("Failed to parse cities.xml: %s" % e)


# ═══════════════════════════════════════════════════════════════════════════
# Seismological analysis — grid-based b-value, Mc, and rate maps
# ═══════════════════════════════════════════════════════════════════════════

class SeismoAnalysis:
    """Spatial seismicity analysis on a regular lat/lon grid.

    For each grid node, samples events within *radius_km* and computes
    the requested statistic.  Returns (lons_2d, lats_2d, values_2d)
    ready for pcolormesh / contourf.
    """

    def __init__(self, events, lon_min, lon_max, lat_min, lat_max,
                 grid_size=0.5, radius_km=50):
        self.events = [e for e in events
                       if e.latitude is not None and e.longitude is not None
                       and e.magnitude_value is not None
                       and e.depth_km is not None]
        self.lon_min = lon_min
        self.lon_max = lon_max
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.grid_size = grid_size
        self.radius_km = radius_km

    def _haversine_km(self, lat1, lon1, lat2, lon2):
        """Great-circle distance in km between two points."""
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) *
             math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return 6371.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _sample(self, clat, clon):
        """Return magnitudes of events within radius_km of (clat, clon)."""
        mags = []
        min_mag = []
        for e in self.events:
            if self._haversine_km(clat, clon, e.latitude, e.longitude) <= self.radius_km:
                mags.append(e.magnitude_value)
                if e.magnitude_value is not None:
                    min_mag.append(e.magnitude_value)
        return mags

    def _grid_coords(self):
        """Return 1-D arrays of grid centre lons and lats."""
        nlons = max(1, int((self.lon_max - self.lon_min) / self.grid_size))
        nlats = max(1, int((self.lat_max - self.lat_min) / self.grid_size))

        lons = np.linspace(self.lon_min, self.lon_max, nlons)
        lats = np.linspace(self.lat_min, self.lat_max, nlats)
        return lons, lats

    def _grid_edges(self):
        nlons = max(1, int((self.lon_max - self.lon_min) / self.grid_size))
        nlats = max(1, int((self.lat_max - self.lat_min) / self.grid_size))
        lon_edges = np.linspace(self.lon_min, self.lon_max, nlons + 1)
        lat_edges = np.linspace(self.lat_min, self.lat_max, nlats + 1)
        return lon_edges, lat_edges

    # ── b-value (Aki-Utsu MLE) ─────────────────────────────────────────

    def bvalue_map(self, mc_hint=1.5):
        """Maximum-likelihood b-value on a grid.

        b = log10(e) / (M̄ − Mc)   for M ≥ Mc
        Uses the given *mc_hint* as a fixed completeness threshold.
        """
        lons, lats = self._grid_coords()
        nlons, nlats = len(lons), len(lats)
        values = np.full((nlats, nlons), np.nan)
        min_events = 10

        for j, lat in enumerate(lats):
            for i, lon in enumerate(lons):
                mags = np.array(self._sample(lat, lon))
                mags = mags[mags >= mc_hint]
                if len(mags) >= min_events:
                    values[j, i] = math.log10(math.e) / (mags.mean() - mc_hint)

        return lons, lats, values

    # ── Magnitude completeness (MAXC) ───────────────────────────────────

    def mc_map(self):
        """Maximum-curvature Mc on a grid.

        Finds the magnitude bin with the highest event count,
        returns that magnitude + 0.2 as the Mc estimate.
        """
        lons, lats = self._grid_coords()
        nlons, nlats = len(lons), len(lats)
        values = np.full((nlats, nlons), np.nan)
        min_events = 15
        bin_width = 0.1

        for j, lat in enumerate(lats):
            for i, lon in enumerate(lons):
                mags = np.array(self._sample(lat, lon))
                if len(mags) < min_events:
                    continue
                m_min = np.floor(mags.min() / bin_width) * bin_width
                m_max = np.ceil(mags.max() / bin_width) * bin_width
                if m_max <= m_min:
                    continue
                bins = np.arange(m_min, m_max + bin_width, bin_width)
                hist, edges = np.histogram(mags, bins=bins)
                if len(hist) == 0:
                    continue
                idx = np.argmax(hist)
                values[j, i] = (edges[idx] + edges[idx + 1]) / 2 + 0.2

        return lons, lats, values

    # ── Seismicity rate ─────────────────────────────────────────────────

    def rate_map(self):
        """Annual seismicity rate per km² above Mc=1.5 on a grid."""
        lons, lats = self._grid_coords()
        nlons, nlats = len(lons), len(lats)
        values = np.full((nlats, nlons), np.nan)
        mc = 1.5

        # Estimate time span from event origin times
        etimes = [e.origin_time for e in self.events
                  if e.origin_time is not None]
        if len(etimes) < 2:
            years = 1.0
        else:
            tspan = seiscomp.core.TimeSpan(max(etimes) - min(etimes))
            years = max(1.0, tspan.seconds() / 31557600.0)

        area_km2 = math.pi * self.radius_km ** 2

        for j, lat in enumerate(lats):
            for i, lon in enumerate(lons):
                mags = np.array(self._sample(lat, lon))
                mags = mags[mags >= mc]
                if len(mags) >= 5:
                    values[j, i] = len(mags) / (area_km2 * years)

        return lons, lats, values


# ═══════════════════════════════════════════════════════════════════════════
# MapBuilder
# ═══════════════════════════════════════════════════════════════════════════

class MapBuilder:
    def __init__(self, events, config, metadata=None):
        self.events = events
        self.config = config
        self.metadata = metadata or {}
        self._plotted_type_groups = set()
        self._analysis_params = []

    def build(self, output_path):
        config = self.config
        lon_min, lon_max, lat_min, lat_max = self._compute_extent()

        dpi = config.get('dpi', 150)
        dims = config['dimension']
        figsize = (dims[0] / dpi, dims[1] / dpi)

        fig = plt.figure(figsize=figsize, dpi=dpi, facecolor='white')

        proj = ccrs.PlateCarree()
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        ax.set_extent([lon_min, lon_max, lat_min, lat_max], crs=proj)

        self._draw_basemap(ax)

        mode = config.get('mode', 'events')
        if mode == 'events':
            self._draw_grid(ax)
            self._draw_events(ax, proj)
            if config.get('show_stations', True):
                self._draw_stations(ax, proj)
            if config.get('show_beachballs', True):
                self._draw_beachballs(ax, proj)
        else:
            self._draw_analysis_layer(ax, proj, lon_min, lon_max,
                                      lat_min, lat_max, mode)
            self._draw_grid(ax)

        if config.get('show_cities', True):
            self._draw_cities(ax, proj, lon_min, lon_max, lat_min, lat_max)
        self._draw_scale_bar(ax, proj, lon_min, lat_min)
        self._draw_north_arrow(ax, proj)

        if config.get('show_legend', True):
            self._draw_legend(fig, ax)

        self._draw_title(ax)
        self._draw_timestamp(fig)

        if config.get('show_inset', True):
            self._draw_inset(fig, lon_min, lon_max, lat_min, lat_max)

        fig.savefig(output_path, dpi=dpi, bbox_inches='tight',
                    facecolor='white', edgecolor='none', pad_inches=0.2)
        plt.close(fig)
        seiscomp.logging.info("Map saved to %s" % output_path)
        print(f"Map saved to {output_path}")

    def _compute_extent(self):
        config = self.config
        if config.get('region'):
            return _parse_region(config['region'])

        margin = config.get('margin', 3.0)
        center_lat = config.get('lat')
        center_lon = config.get('lon')

        if center_lat is None and self.events:
            valid = [e for e in self.events if e.latitude is not None]
            if valid:
                center_lat = valid[0].latitude
                center_lon = valid[0].longitude

        if center_lat is None:
            center_lat, center_lon = 0, 0
            margin = 90

        dlat = dlon = margin
        dims = config['dimension']
        aspect = dims[0] / max(1, dims[1])
        dlon = dlat * aspect

        return (center_lon - dlon, center_lon + dlon,
                center_lat - dlat, center_lat + dlat)

    def _draw_basemap(self, ax):
        cfg = self.config
        ax.add_feature(cfeature.OCEAN.with_scale('50m'),
                       facecolor=cfg.get('ocean_color', '#e8f0f8'), zorder=1)
        ax.add_feature(cfeature.LAND.with_scale('50m'),
                       facecolor=cfg.get('land_color', '#f5f3e8'), zorder=2)
        ax.add_feature(cfeature.COASTLINE.with_scale('50m'),
                       edgecolor=cfg.get('coast_color', '#666666'),
                       linewidth=0.6, zorder=3)
        if cfg.get('show_borders', True):
            ax.add_feature(cfeature.BORDERS.with_scale('50m'),
                           edgecolor=cfg.get('border_color', '#aaaaaa'),
                           linewidth=0.35, linestyle='-', zorder=3)
        if cfg.get('show_states', False):
            ax.add_feature(cfeature.STATES.with_scale('50m'),
                           edgecolor=cfg.get('state_color', '#cccccc'),
                           linewidth=0.2, linestyle=':', zorder=3)
        ax.add_feature(cfeature.LAKES.with_scale('50m'),
                       facecolor=cfg.get('ocean_color', '#e8f0f8'),
                       edgecolor='#888888', linewidth=0.25, zorder=3)
        if cfg.get('show_rivers', False):
            ax.add_feature(cfeature.RIVERS.with_scale('50m'),
                           edgecolor='#88aacc', linewidth=0.25, zorder=3)

    def _draw_grid(self, ax):
        cfg = self.config
        gl = ax.gridlines(draw_labels=True, dms=False,
                          x_inline=False, y_inline=False,
                          linewidth=0.25, color='#cccccc', alpha=0.7, zorder=4)
        gl.top_labels = False
        gl.right_labels = False
        gl.xlabel_style = {'size': 6.5, 'color': '#555555'}
        gl.ylabel_style = {'size': 6.5, 'color': '#555555'}
        gl.xlocator = MaxNLocator(nbins=cfg.get('grid_x', 8))
        gl.ylocator = MaxNLocator(nbins=cfg.get('grid_y', 6))

    def _draw_events(self, ax, proj):
        cfg = self.config
        self._plotted_type_groups = set()

        for se in self.events:
            if se.latitude is None or se.longitude is None:
                continue

            info = EVENT_TYPE_CONFIG.get(se.event_type, ('.', 'Unknown', None))
            marker, type_name, override_color = info

            depth = se.depth_km if se.depth_km is not None else 10
            mag = se.magnitude_value if se.magnitude_value is not None else 0

            face_color = override_color or depth_color(
                depth, vmin=0, vmax=cfg.get('depth_max', 200))

            size = mag_to_size(mag,
                               min_mag=cfg.get('min_mag', 0),
                               max_mag=cfg.get('max_mag', 8),
                               min_size=cfg.get('min_marker_size', 20),
                               max_size=cfg.get('max_marker_size', 450))

            edge_lw = 0.5 if marker not in ('*',) else 0.8
            ax.plot(se.longitude, se.latitude,
                    marker=marker, markersize=math.sqrt(size) / 2.0,
                    markerfacecolor=face_color if marker != '*' else 'none',
                    markeredgecolor=cfg.get('marker_edge', '#333333'),
                    markeredgewidth=edge_lw,
                    alpha=cfg.get('marker_alpha', 0.9),
                    linestyle='none', transform=proj, zorder=7,
                    clip_on=True)

            if mag > 0 and cfg.get('show_labels', True):
                label = f'M{mag:.1f}'
                ax.annotate(label, (se.longitude, se.latitude),
                            textcoords='offset points',
                            xytext=(4, 4), fontsize=5.5, color='#333333',
                            alpha=0.85, zorder=8, clip_on=True,
                            bbox=dict(boxstyle='round,pad=0.1',
                                      facecolor='white', alpha=0.6, lw=0))

            group_name = _group_name_for_type(se.event_type)
            if group_name:
                self._plotted_type_groups.add(group_name)

    def _draw_analysis_layer(self, ax, proj, lon_min, lon_max,
                             lat_min, lat_max, mode):
        """Draw a gridded seismological analysis as a heatmap."""
        config = self.config
        grid_size = config.get('grid_size', 0.5)
        radius_km = config.get('grid_radius', 50)
        mc_hint = config.get('mc_hint', 1.5)

        analysis = SeismoAnalysis(
            self.events, lon_min, lon_max, lat_min, lat_max,
            grid_size=grid_size, radius_km=radius_km)

        seiscomp.logging.debug("Running %s analysis (grid=%.2f°, r=%d km) ..."
                               % (mode, grid_size, radius_km))

        if mode == 'bvalue':
            lons, lats, vals = analysis.bvalue_map(mc_hint=mc_hint)
            cmap = plt.cm.inferno
            label = 'b-value'
            vmin, vmax = 0.5, 1.5
            fmt = '%0.2f'
        elif mode == 'mc':
            lons, lats, vals = analysis.mc_map()
            cmap = plt.cm.plasma_r
            label = 'Magnitude of completeness  Mc'
            vmin, vmax = 0.5, 3.0
            fmt = '%0.1f'
        elif mode == 'rate':
            lons, lats, vals = analysis.rate_map()
            cmap = plt.cm.viridis
            label = 'Annual rate  ev / km²'
            vmin, vmax = None, None  # auto-scale
            fmt = '%0.2e'
        else:
            return

        lon_edges, lat_edges = analysis._grid_edges()
        lon_mesh, lat_mesh = np.meshgrid(lon_edges, lat_edges)

        # Mask NaN and add a small epsilon to avoid all-NaN warnings
        masked = np.ma.masked_invalid(vals)
        if masked.count() == 0:
            seiscomp.logging.warning(
                "Analysis produced only NaN values — "
                "too few events or grid too sparse.")
            return

        if vmin is None:
            vmin = float(np.nanmin(vals))
        if vmax is None:
            vmax = float(np.nanmax(vals))

        pcm = ax.pcolormesh(lon_mesh, lat_mesh, vals,
                            cmap=cmap, vmin=vmin, vmax=vmax,
                            transform=proj, zorder=5, alpha=0.85,
                            shading='flat', snap=True)

        cax = ax.inset_axes([0.92, 0.15, 0.015, 0.55])
        cb = plt.colorbar(pcm, cax=cax, orientation='vertical')
        cb.set_label(label, fontsize=8)
        cb.ax.tick_params(labelsize=6.5)
        cb.outline.set_linewidth(0.4)

        # Overlay event locations as small dots for reference
        lons_ev = [e.longitude for e in self.events
                   if e.longitude is not None and e.latitude is not None]
        lats_ev = [e.latitude for e in self.events
                   if e.longitude is not None and e.latitude is not None]
        if lons_ev:
            ax.plot(lons_ev, lats_ev, 'o', markersize=1.2,
                    color='#000000', alpha=0.25,
                    linestyle='none', transform=proj, zorder=6)

        # New legend block showing analysis params
        self._analysis_params = [
            'Mode: %s' % mode,
            'Grid: %.2f°   Radius: %d km' % (grid_size, radius_km),
        ]
        if mode == 'bvalue':
            self._analysis_params.append('Mc hint: M\u2009\u2265\u2009%.1f'
                                         % mc_hint)

    def _draw_stations(self, ax, proj):
        all_stations = {}

        for se in self.events:
            if se.latitude is None:
                continue
            for phase, dist, az in se.arrivals:
                if dist is not None and az is not None:
                    slat, slon = _az_dist_to_latlon(
                        se.latitude, se.longitude, az, dist)
                    key = f'{slat:.2f},{slon:.2f}'
                    if key not in all_stations:
                        all_stations[key] = (slat, slon)

        if not all_stations:
            return

        lons = [s[1] for s in all_stations.values()]
        lats = [s[0] for s in all_stations.values()]
        ax.plot(lons, lats, 'v', markersize=4, color='#444444',
                markerfacecolor='#ffffff', markeredgewidth=0.5,
                linestyle='none', transform=proj, zorder=6,
                label='_stations', alpha=0.8)

    def _draw_cities(self, ax, proj, lon_min, lon_max, lat_min, lat_max):
        cfg = self.config
        min_pop = cfg.get('min_city_population', 100000)

        cities = list(load_cities(lon_min, lon_max, lat_min, lat_max, min_pop))
        if not cities:
            return

        cities.sort(key=lambda c: (not c[4], -c[3]))

        placed = []
        for name, lat, lon, pop, is_capital in cities:
            too_close = False
            for px, py in placed:
                if abs(lat - py) < 0.08 and abs(lon - px) < 0.12:
                    too_close = True
                    break
            if too_close:
                continue

            placed.append((lon, lat))

            if is_capital:
                fontsize = 8.0
                color = '#222222'
                fontweight = 'bold'
                ax.plot(lon, lat, 's', markersize=3.5, color='#cc3333',
                        markerfacecolor='#cc3333', transform=proj,
                        zorder=8, clip_on=True)
            else:
                fontsize = 6.0
                color = '#444444'
                fontweight = 'normal'

            ax.annotate(name, (lon, lat),
                        textcoords='offset points',
                        xytext=(3, -2), fontsize=fontsize,
                        color=color, fontweight=fontweight,
                        ha='left', va='top',
                        alpha=0.85, zorder=9, clip_on=True)

    def _draw_beachballs(self, ax, proj):
        if not HAS_OBSPY_BEACH:
            return

        for se in self.events:
            if not se.has_focal_mechanism:
                continue
            if se.fm_strike is None or se.latitude is None:
                continue

            mag = se.magnitude_value or 3
            bb_deg = 0.06 + 0.03 * mag

            try:
                b = _beach_patch(
                    [se.fm_strike, se.fm_dip, se.fm_rake],
                    xy=(se.longitude, se.latitude),
                    width=bb_deg * 2, linewidth=0.4,
                    facecolor='#555555')
                ax.add_collection(b)
            except Exception:
                pass

    def _draw_north_arrow(self, ax, proj):
        x_frac, y_frac = 0.92, 0.90
        arrow_len = 0.04

        ax.annotate('', xy=(x_frac, y_frac + arrow_len),
                    xytext=(x_frac, y_frac),
                    xycoords='axes fraction',
                    textcoords='axes fraction',
                    arrowprops=dict(arrowstyle='->', lw=1.5,
                                    color='#333333', shrinkB=0),
                    zorder=30)
        ax.text(x_frac, y_frac + arrow_len + 0.01, 'N',
                transform=ax.transAxes, fontsize=9, fontweight='bold',
                color='#333333', ha='center', va='bottom', zorder=30)

    def _draw_scale_bar(self, ax, proj, lon_min, lat_min):
        extent = ax.get_extent(proj)
        lon_span = extent[1] - extent[0]
        lat_span = extent[3] - extent[2]
        mid_lat = (extent[2] + extent[3]) / 2
        km_per_deg = 111.32 * math.cos(math.radians(mid_lat))
        total_km = lon_span * km_per_deg

        nice = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
        bar_km = min(nice, key=lambda x: abs(x - total_km / 4))
        bar_deg = bar_km / km_per_deg

        bar_x = extent[0] + 0.04 * lon_span
        bar_y = extent[2] + 0.04 * lat_span
        bar_h = 0.006 * lat_span

        n_segments = 4
        seg_deg = bar_deg / n_segments

        from matplotlib.patches import Rectangle
        for i in range(n_segments):
            x0 = bar_x + i * seg_deg
            fc = 'black' if i % 2 == 0 else 'white'
            ec = 'black'
            rect = Rectangle((x0, bar_y), seg_deg, bar_h,
                             facecolor=fc, edgecolor=ec, linewidth=0.4,
                             transform=proj, zorder=20, clip_on=False)
            ax.add_patch(rect)

        if bar_km >= 1000:
            label = f'{bar_km / 1000:.0f} km' if bar_km % 1000 == 0 else f'{bar_km / 1000:.1f} km'
        else:
            label = f'{bar_km:.0f} km'
        ax.text(bar_x + bar_deg / 2, bar_y - 0.012 * lat_span, label,
                transform=proj, ha='center', va='top',
                fontsize=7, color='black', zorder=20, fontweight='bold')

    def _draw_legend(self, fig, ax):
        cfg = self.config
        mode = cfg.get('mode', 'events')

        if mode != 'events':
            # Analysis mode: show parameter block as a text box
            if self._analysis_params:
                text = '\n'.join(self._analysis_params)
                ax.text(0.01, 0.36, text, transform=ax.transAxes,
                        fontsize=6.5, color='#222222',
                        fontfamily='monospace',
                        va='top', ha='left',
                        bbox=dict(boxstyle='round,pad=0.3',
                                  facecolor='white', alpha=0.85, lw=0.5),
                        zorder=30)
            return

        mag_handles = []
        for mag in [2, 4, 6, 8]:
            size = mag_to_size(mag,
                               min_mag=cfg.get('min_mag', 0),
                               max_mag=cfg.get('max_mag', 8),
                               min_size=cfg.get('min_marker_size', 20),
                               max_size=cfg.get('max_marker_size', 450))
            ms = math.sqrt(size) / 2.5
            mag_handles.append(
                Line2D([0], [0], marker='o', color='w',
                       markerfacecolor='#888888',
                       markeredgecolor='#333333',
                       markeredgewidth=0.4,
                       markersize=ms, label=f'M{mag}'))

        leg2 = ax.legend(handles=mag_handles,
                         title='Magnitude',
                         loc='lower left',
                         fontsize=6, title_fontsize=7,
                         framealpha=0.85,
                         borderpad=0.4,
                         labelspacing=0.15,
                         ncol=4,
                         columnspacing=0.4)
        leg2.get_frame().set_linewidth(0.5)

        cax = fig.add_axes([0.18, 0.07, 0.64, 0.012])
        sm = plt.cm.ScalarMappable(
            cmap=DEPTH_CMAP,
            norm=plt.Normalize(0, cfg.get('depth_max', 200)))
        sm.set_array([])
        cb = fig.colorbar(sm, cax=cax, orientation='horizontal')
        cb.set_label('Depth (km)', fontsize=7.5)
        cb.ax.tick_params(labelsize=6.5)
        cb.outline.set_linewidth(0.4)

    def _draw_title(self, ax):
        cfg = self.config
        meta = self.metadata

        if cfg.get('title'):
            title = cfg['title']
        elif self.events and self.events[0].region_name:
            title = self.events[0].region_name
        else:
            title = 'Seismic Event Map'

        ax.set_title(title, fontsize=14, fontweight='bold',
                     pad=10, loc='left')

        subtitle_lines = []

        if self.events:
            n = meta.get('n_events', len(self.events))
            mags = [e.magnitude_value for e in self.events
                    if e.magnitude_value is not None]
            if mags:
                subtitle_lines.append(
                    f'{n} event{"s" if n > 1 else ""}  |  '
                    f'M {min(mags):.1f} \u2013 {max(mags):.1f}')
            else:
                subtitle_lines.append(f'{n} event{"s" if n > 1 else ""}')

        time_range = meta.get('time_range', '')
        if time_range:
            subtitle_lines.append(time_range)

        agency = meta.get('agency', '')
        version = meta.get('version', '')
        parts = []
        if agency and agency != '\u2014':
            parts.append(f'Agency: {agency}')
        if version:
            parts.append(version)
        if parts:
            subtitle_lines.append('  \u2022  '.join(parts))

        if subtitle_lines:
            y = 1.025
            for line in subtitle_lines:
                ax.text(0, y, line, transform=ax.transAxes,
                        fontsize=9.5, color='#222222',
                        fontweight='normal',
                        va='bottom', ha='left')
                y -= 0.028

    def _draw_timestamp(self, fig):
        ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        fig.text(0.99, 0.01, f'Generated: {ts}  |  scmap',
                 fontsize=5.5, color='#999999', ha='right', va='bottom',
                 style='italic')

    def _draw_inset(self, fig, lon_min, lon_max, lat_min, lat_max):
        inset_ax = fig.add_axes([0.76, 0.76, 0.18, 0.18],
                                projection=ccrs.PlateCarree())
        inset_ax.set_global()
        inset_ax.add_feature(cfeature.LAND, facecolor='#e8e8e8', zorder=1)
        inset_ax.add_feature(cfeature.OCEAN, facecolor='#ffffff', zorder=1)
        inset_ax.add_feature(cfeature.COASTLINE, edgecolor='#aaaaaa',
                             linewidth=0.3, zorder=2)

        from matplotlib.patches import Rectangle
        rect = Rectangle((lon_min, lat_min), lon_max - lon_min,
                         lat_max - lat_min,
                         linewidth=1.2, edgecolor='#cc3333',
                         facecolor='#cc3333', alpha=0.15,
                         transform=ccrs.PlateCarree(), zorder=10)
        inset_ax.add_patch(rect)
        inset_ax.set_title('Overview', fontsize=6, pad=2)


# ═══════════════════════════════════════════════════════════════════════════
# Legend grouping helpers
# ═══════════════════════════════════════════════════════════════════════════

_TYPE_TO_GROUP = {
    dm.EARTHQUAKE:                       'Earthquake',
    dm.INDUCED_EARTHQUAKE:               'Induced / Triggered',
    dm.INDUCED_OR_TRIGGERED_EVENT:       'Induced / Triggered',
    dm.FLUID_INJECTION:                  'Induced / Triggered',
    dm.FLUID_EXTRACTION:                 'Induced / Triggered',
    dm.RESERVOIR_LOADING:                'Induced / Triggered',
    dm.QUARRY_BLAST:                     'Explosion / Blast',
    dm.MINING_EXPLOSION:                 'Explosion / Blast',
    dm.EXPLOSION:                        'Explosion / Blast',
    dm.CHEMICAL_EXPLOSION:               'Explosion / Blast',
    dm.NUCLEAR_EXPLOSION:                'Explosion / Blast',
    dm.CONTROLLED_EXPLOSION:             'Explosion / Blast',
    dm.INDUSTRIAL_EXPLOSION:             'Explosion / Blast',
    dm.ACCIDENTAL_EXPLOSION:             'Explosion / Blast',
    dm.EXPERIMENTAL_EXPLOSION:           'Explosion / Blast',
    dm.ROCKET_LAUNCH:                    'Explosion / Blast',
    dm.ROCKET_IMPACT:                    'Explosion / Blast',
    dm.ARTILLERY_STRIKE:                 'Explosion / Blast',
    dm.BOMB_DETONATION:                  'Explosion / Blast',
    dm.LANDSLIDE:                        'Landslide / Avalanche',
    dm.ROCKSLIDE:                        'Landslide / Avalanche',
    dm.DEBRIS_AVALANCHE:                 'Landslide / Avalanche',
    dm.SNOW_AVALANCHE:                   'Landslide / Avalanche',
    dm.AVALANCHE:                        'Landslide / Avalanche',
    dm.SUBMARINE_LANDSLIDE:              'Landslide / Avalanche',
    dm.VOLCANIC_ERUPTION:                'Volcanic',
    dm.VOLCANO_TECTONIC:                 'Volcanic',
    dm.VOLCANIC_LONG_PERIOD:             'Volcanic',
    dm.VOLCANIC_VERY_LONG_PERIOD:        'Volcanic',
    dm.VOLCANIC_HYBRID:                  'Volcanic',
    dm.VOLCANIC_ROCKFALL:                'Volcanic',
    dm.VOLCANIC_TREMOR:                  'Volcanic',
    dm.PYROCLASTIC_FLOW:                 'Volcanic',
    dm.LAHAR:                            'Volcanic',
    dm.MINE_COLLAPSE:                    'Collapse',
    dm.BUILDING_COLLAPSE:                'Collapse',
    dm.COLLAPSE:                         'Collapse',
    dm.CAVITY_COLLAPSE:                  'Collapse',
    dm.METEOR_IMPACT:                    'Meteor / Impact',
    dm.METEORITE:                        'Meteor / Impact',
    dm.ATMOSPHERIC_METEOR_EXPLOSION:     'Meteor / Impact',
    dm.SONIC_BOOM:                       'Sonic',
    dm.SONIC_BLAST:                      'Sonic',
    dm.ANTHROPOGENIC_EVENT:              'Anthropogenic',
    dm.ROCK_BURST:                       'Rock Burst',
    dm.ICE_QUAKE:                        'Induced / Triggered',
    dm.FROST_QUAKE:                      'Induced / Triggered',
    dm.TREMOR_PULSE:                     'Induced / Triggered',
}


def _group_name_for_type(event_type):
    if event_type is None:
        return 'Other / Unknown'
    return _TYPE_TO_GROUP.get(event_type, 'Other / Unknown')


def _seiscomp_version_string():
    try:
        v = seiscomp.core.Version()
        maj = v.majorTag()
        if maj == 0:
            return 'SeisComP 8.0'
        return f'SeisComP {maj}.{v.minorTag()}'
    except Exception:
        return 'SeisComP'


# ═══════════════════════════════════════════════════════════════════════════
# SeisComP Client Application
# ═══════════════════════════════════════════════════════════════════════════

class ScmapApp(seiscomp.client.Application):
    """
    SeisComP client application for generating seismic event maps.

    Supports two modes of operation:
       -- offline:  Reads QuakeML from file/stdin (-i)
       -- online:   Queries events from SeisComP database
                    (-d with -E for IDs or --start-time/--end-time for range)

    Standard SeisComP options like -H (messaging host), -d (database), --debug
    are inherited from seiscomp.client.Application and always available.
    """

    def __init__(self, argc, argv):
        seiscomp.client.Application.__init__(self, argc, argv)
        self.setMessagingEnabled(False)
        self.setDatabaseEnabled(True, True)
        self.setDaemonEnabled(False)
        self.setLoadInventoryEnabled(True)
        self.setLoadRegionsEnabled(True)
        self.setLoadCitiesEnabled(True)

        self._input_file = None
        self._event_ids = None
        self._start_time = None
        self._end_time = None
        self._limit = 0

    def createCommandLineDescription(self):
        try:
            self.commandline().addGroup("Input")
            self.commandline().addStringOption(
                "Input", "input,i",
                "QuakeML XML file with event parameters (use \"-\" for stdin)."
            )
            self.commandline().addStringOption(
                "Input", "event,E",
                "Event ID to query from database (comma-separated for multiple)."
            )
            self.commandline().addStringOption(
                "Input", "start-time",
                "Start of time window for database event query "
                "(format: \"YYYY-MM-DD [HH:MM[:SS]]\"). "
                "Requires -d with a valid database URI."
            )
            self.commandline().addStringOption(
                "Input", "end-time",
                "End of time window for database event query "
                "(format: \"YYYY-MM-DD [HH:MM[:SS]]\"). "
                "If omitted, defaults to current time."
            )
            self.commandline().addStringOption(
                "Input", "limit",
                "Maximum number of events to return from time-range query. "
                "0 = unlimited (default: 0)."
            )

            self.commandline().addGroup("Map")
            self.commandline().addStringOption(
                "Map", "output,o",
                "Output PNG file path (default: map.png)."
            )
            self.commandline().addStringOption(
                "Map", "region,r",
                "Map region defined as latxlon+lat0+lon0 "
                "(e.g. 5x5+45+10) or +lat0+lon0+lat1+lon1."
            )
            self.commandline().addStringOption(
                "Map", "margin,m",
                "Margin in degrees around event center (default: 3)."
            )
            self.commandline().addStringOption(
                "Map", "lat",
                "Center latitude."
            )
            self.commandline().addStringOption(
                "Map", "lon",
                "Center longitude."
            )
            self.commandline().addStringOption(
                "Map", "dimension",
                "Output dimensions WxH in pixels (default: 1600x1000)."
            )
            self.commandline().addStringOption(
                "Map", "dpi",
                "Output DPI (default: 150)."
            )
            self.commandline().addStringOption(
                "Map", "depth-max",
                "Max depth in km for color scale (default: 200)."
            )
            self.commandline().addStringOption(
                "Map", "min-mag",
                "Minimum magnitude for marker scale (default: 0)."
            )
            self.commandline().addStringOption(
                "Map", "max-mag",
                "Maximum magnitude for marker scale (default: 8)."
            )
            self.commandline().addStringOption(
                "Map", "min-marker-size",
                "Minimum marker area for scale (default: 20)."
            )
            self.commandline().addStringOption(
                "Map", "max-marker-size",
                "Maximum marker area for scale (default: 450)."
            )
            self.commandline().addStringOption(
                "Map", "title",
                "Override map title text."
            )
            self.commandline().addStringOption(
                "Map", "min-city-population",
                "Minimum population for city labels (default: 100000)."
            )

            self.commandline().addGroup("Display")
            self.commandline().addStringOption(
                "Display", "mode",
                "Map mode: events (default), bvalue, mc, or rate."
            )
            self.commandline().addStringOption(
                "Display", "grid-size",
                "Grid cell size in degrees for analysis modes (default: 0.5)."
            )
            self.commandline().addStringOption(
                "Display", "grid-radius",
                "Sample radius in km for analysis modes (default: 50)."
            )
            self.commandline().addOption(
                "Display", "no-legend",
                "Disable event type legend."
            )
            self.commandline().addOption(
                "Display", "no-stations",
                "Disable station triangle markers."
            )
            self.commandline().addOption(
                "Display", "no-beachballs",
                "Disable focal mechanism beach balls."
            )
            self.commandline().addOption(
                "Display", "no-borders",
                "Disable country borders."
            )
            self.commandline().addOption(
                "Display", "no-inset",
                "Disable overview inset map."
            )
            self.commandline().addOption(
                "Display", "no-labels",
                "Disable magnitude text labels on markers."
            )
            self.commandline().addOption(
                "Display", "no-cities",
                "Disable city/place name labels."
            )
            self.commandline().addOption(
                "Display", "show-rivers",
                "Draw major rivers."
            )
            self.commandline().addOption(
                "Display", "show-states",
                "Draw province/state administrative boundaries."
            )
        except RuntimeError:
            seiscomp.logging.warning(
                "Unexpected error in createCommandLineDescription: %s"
                % sys.exc_info())

        return True

    def validateParameters(self):
        if not seiscomp.client.Application.validateParameters(self):
            return False

        try:
            self._input_file = self.commandline().optionString("input")
        except RuntimeError:
            self._input_file = None

        try:
            self._event_ids = self.commandline().optionString("event")
        except RuntimeError:
            self._event_ids = None

        try:
            self._start_time = self.commandline().optionString("start-time")
        except RuntimeError:
            self._start_time = None

        try:
            self._end_time = self.commandline().optionString("end-time")
        except RuntimeError:
            self._end_time = None

        try:
            limit_s = self.commandline().optionString("limit")
            self._limit = int(limit_s) if limit_s else 0
        except (RuntimeError, ValueError):
            self._limit = 0

        # File input overrides everything; disable database in that case
        if self._input_file:
            self.setDatabaseEnabled(False, False)
            self._event_ids = None
            self._start_time = None

        # If no database-oriented options, disable database
        if not self._event_ids and not self._start_time:
            self.setDatabaseEnabled(False, False)

        # Require at least one input source
        if not self._input_file and not self._event_ids and not self._start_time:
            seiscomp.logging.error(
                "No input specified. Use -i <file>, -E <eventID>, "
                "or --start-time to query by time range.")
            return False

        # Enable stderr logging only when no --log-file was set;
        # otherwise the base class writes to the file instead.
        try:
            has_log_file = bool(self.commandline().optionString("log-file"))
        except RuntimeError:
            has_log_file = False
        if not has_log_file:
            self.setLoggingToStdErr(True)

        return True

    def printUsage(self):
        print("""Usage:
  scmap [options]

Generate high-resolution PNG seismic event maps from SeisComP data.

Modes:
  File mode:      scmap -i events.xml -o map.png
  By event ID:    scmap -E <id> -d user:pass@host:port/db
  By time range:  scmap --start-time "2024-01-01 00:00" -d user:pass@host:port/db
  Interactive:    scmap -i - < events.xml > map.png

Analysis modes (--mode):
  events          Individual event markers (default)
  bvalue          Gutenberg-Richter b-value heatmap
  mc              Magnitude of completeness heatmap (MAXC)
  rate            Annual seismicity rate per km²""")
        print()

        seiscomp.client.Application.printUsage(self)

        print("""
Examples:
  Render all events from a QuakeML file:
    scmap -i events.xml -o map.png

  Render a specific region with a 5-degree margin:
    scmap -i events.xml -o map.png -m 5

  Render a fixed geographic region:
    scmap -i events.xml -o map.png --region 10x8+35+20

  Query a single event from database and render it:
    scmap -E smi:org.gfz-potsdam/event1 -d sysop:sysop@localhost:18002/seiscomp

  Query events from the last 24 hours (limit to 50 events):
    scmap --start-time "2024-06-01 00:00" \\
      -d sysop:sysop@localhost:18002/seiscomp --limit 50 -o map.png

  Query events for a specific day:
    scmap --start-time "2024-06-01" --end-time "2024-06-02" \\
      -d sysop:sysop@localhost:18002/seiscomp -o map.png

  High-resolution output with custom dimensions:
    scmap -i events.xml -o map.png --dimension 2400x1600 --dpi 300

  Minimal output (no legend, no inset, no borders):
    scmap -i events.xml -o map.png --no-legend --no-inset --no-borders

  b-value heatmap with 0.25° grid, 80 km sample radius:
    scmap -i events.xml -o map.png --mode bvalue --grid-size 0.25 --grid-radius 80

  Magnitude completeness (Mc) map:
    scmap -i events.xml -o map.png --mode mc --grid-size 0.5

  Seismicity rate map for the last 7 days:
    scmap --start-time "2026-06-10" -d sysop:sysop@localhost:18002/seiscomp \\
      --mode rate --grid-size 0.3 --grid-radius 60 -o rate_map.png
""")
        return True

    def run(self):
        events = []
        metadata = {}

        output = self._opt_str("output", "map.png")
        config = self._build_config()

        if self._input_file:
            ep = self._load_xml(self._input_file)
            if ep is None:
                return False
            events, metadata = extract_events(ep)
        elif self._event_ids or self._start_time:
            ep = self._query_database()
            if ep is None:
                return False
            events, metadata = extract_events(ep)

        if not events:
            seiscomp.logging.warning(
                "No events found in input. Map will be empty.")

        builder = MapBuilder(events, config, metadata=metadata)
        builder.build(output)
        return True

    # ── helpers ─────────────────────────────────────────────────────────

    def _opt_str(self, name, default=""):
        try:
            val = self.commandline().optionString(name)
            if val:
                return val
        except RuntimeError:
            pass
        return default

    def _opt_float(self, name, default=0.0):
        try:
            val = self.commandline().optionString(name)
            if val:
                return float(val)
        except (RuntimeError, ValueError):
            pass
        return default

    def _has_flag(self, name):
        try:
            return self.commandline().hasOption(name)
        except RuntimeError:
            return False

    def _build_config(self):
        dims_str = self._opt_str("dimension", "1600x1000")
        dim_parts = dims_str.split('x')
        w = int(dim_parts[0]) if len(dim_parts) >= 1 and dim_parts[0] else 1600
        h = int(dim_parts[1]) if len(dim_parts) >= 2 and dim_parts[1] else 1000

        config = {
            'dimension': (w, h),
            'dpi': self._opt_float("dpi", 150) or 150,
            'depth_max': self._opt_float("depth-max", 200) or 200,
            'min_mag': self._opt_float("min-mag", 0),
            'max_mag': self._opt_float("max-mag", 8) or 8,
            'min_marker_size': self._opt_float("min-marker-size", 20) or 20,
            'max_marker_size': self._opt_float("max-marker-size", 450) or 450,
            'margin': self._opt_float("margin", 3.0) or 3.0,
            'show_legend': not self._has_flag("no-legend"),
            'show_stations': not self._has_flag("no-stations"),
            'show_beachballs': not self._has_flag("no-beachballs") and HAS_OBSPY_BEACH,
            'show_borders': not self._has_flag("no-borders"),
            'show_inset': not self._has_flag("no-inset"),
            'show_labels': not self._has_flag("no-labels"),
            'show_rivers': self._has_flag("show-rivers"),
            'show_states': self._has_flag("show-states"),
            'show_cities': not self._has_flag("no-cities"),
            'min_city_population': int(self._opt_float("min-city-population", 100000) or 100000),
            'title': self._opt_str("title"),
            'mode': self._opt_str("mode", "events"),
            'grid_size': self._opt_float("grid-size", 0.5) or 0.5,
            'grid_radius': self._opt_float("grid-radius", 50) or 50,
            'mc_hint': 1.5,
        }

        region = self._opt_str("region")
        if region:
            config['region'] = region

        lat = self._opt_float("lat")
        if lat:
            config['lat'] = lat

        lon = self._opt_float("lon")
        if lon:
            config['lon'] = lon

        return config

    def _load_xml(self, path):
        ar = seiscomp.io.XMLArchive()
        if path == '-':
            import tempfile
            xml_data = sys.stdin.buffer.read()
            fd, tmppath = tempfile.mkstemp(suffix='.xml', prefix='scmap_')
            with os.fdopen(fd, 'wb') as f:
                f.write(xml_data)
            if not ar.open(tmppath):
                seiscomp.logging.error("Cannot read XML from stdin")
                os.unlink(tmppath)
                return None
            obj = ar.readObject()
            os.unlink(tmppath)
        else:
            if not ar.open(path):
                seiscomp.logging.error("Cannot open input file: %s" % path)
                return None
            obj = ar.readObject()

        if obj is None:
            seiscomp.logging.error("Cannot read any object from input")
            return None

        ep = dm.EventParameters.Cast(obj)
        if ep is None:
            seiscomp.logging.error("Input is not an EventParameters document")
            return None

        return ep

    def _query_database(self):
        """
        Query the SeisComP database for events.

        Supports two modes:
          - By event ID (-E): loads each event and its related objects.
          - By time range (--start-time / --end-time): iterates all events
            in the window via getEvents(), optionally capped by --limit.

        For each event, loads the preferred origin, picks, amplitudes,
        and focal mechanism. Returns a populated EventParameters object
        compatible with extract_events().
        """
        try:
            dbq = dm.DatabaseQuery(self.database())
        except Exception as e:
            seiscomp.logging.error("Cannot create database query: %s" % e)
            seiscomp.logging.error(
                "Ensure a database URI is set via -d or in the module config.\n"
                "  Format: [mysql://]user:pass@host[:port]/db\n"
                "  Example: -d sysop:sysop@localhost:18002/seiscomp")
            return None

        ep = dm.EventParameters()

        # ── Mode 1: query by event ID ──────────────────────────────────
        if self._event_ids:
            ids = [eid.strip() for eid in self._event_ids.split(",") if eid.strip()]
            seiscomp.logging.info("Querying database for %d event(s) by ID ..."
                                  % len(ids))

            for evid in ids:
                self._load_event_full(dbq, ep, evid)

        # ── Mode 2: query by time range ────────────────────────────────
        else:
            t_start, t_end = self._parse_time_range()
            if t_start is None:
                return None

            seiscomp.logging.info(
                "Querying database for events in [ %s .. %s ]%s ..."
                % (t_start.toString("%Y-%m-%d %H:%M:%S"),
                   t_end.toString("%Y-%m-%d %H:%M:%S"),
                   " (limit=%d)" % self._limit if self._limit else ""))

            it = dbq.getEvents(t_start, t_end)
            pending = []
            count = 0

            # First pass: collect events from the iterator (no nested queries)
            while it.valid():
                if self._limit and count >= self._limit:
                    seiscomp.logging.info(
                        "Reached limit of %d events; stopping query."
                        % self._limit)
                    break

                obj = it.get()
                if obj is not None:
                    evt = dm.Event.Cast(obj)
                    if evt is not None:
                        ep.add(evt)
                        pending.append(evt)
                        count += 1
                it.next()

            seiscomp.logging.debug(
                "Collected %d event(s) from time-range query." % count)

            # Second pass: load related objects (origins, picks, amplitudes,
            # focal mechanisms) — safe because iterator is now exhausted
            for evt in pending:
                seiscomp.logging.debug("Loading related for event: %s"
                                       % evt.publicID())
                self._load_event_related(dbq, ep, evt)

        seiscomp.logging.info(
            "Query complete: %d events, %d origins, %d picks"
            % (ep.eventCount(), ep.originCount(), ep.pickCount()))
        return ep

    def _load_event_full(self, dbq, ep, evid):
        """Load an event by publicID and all its related objects into *ep*."""
        seiscomp.logging.debug("Loading event: %s" % evid)
        obj = dbq.loadObject(dm.Event.TypeInfo(), evid)
        if obj is None:
            seiscomp.logging.warning(
                "Event not found in database: %s" % evid)
            return
        evt = dm.Event.Cast(obj)
        ep.add(evt)
        self._load_event_related(dbq, ep, evt)

    def _load_event_related(self, dbq, ep, evt):
        """Load origin, picks, amplitudes, and focal mechanism for an event."""
        evid = evt.publicID()

        # Preferred origin
        pref_oid = _safe_str(evt, 'preferredOriginID')
        if pref_oid:
            obj = dbq.loadObject(dm.Origin.TypeInfo(), pref_oid)
            org = dm.Origin.Cast(obj)
            if org:
                ep.add(org)
                for pick_obj in dbq.getPicks(pref_oid):
                    pick = dm.Pick.Cast(pick_obj)
                    if pick and ep.findPick(pick.publicID()) is None:
                        ep.add(pick)
                for amp_obj in dbq.getAmplitudesForOrigin(pref_oid):
                    amp = dm.Amplitude.Cast(amp_obj)
                    if amp and ep.findAmplitude(amp.publicID()) is None:
                        ep.add(amp)
            else:
                seiscomp.logging.warning(
                    "Preferred origin %s not found for event %s"
                    % (pref_oid, evid))

        # Preferred focal mechanism
        pref_fmid = _safe_str(evt, 'preferredFocalMechanismID')
        if pref_fmid:
            obj = dbq.loadObject(dm.FocalMechanism.TypeInfo(), pref_fmid)
            fm = dm.FocalMechanism.Cast(obj)
            if fm:
                ep.add(fm)

    def _parse_time_range(self):
        """Parse --start-time / --end-time into seiscomp.core.Time objects.

        Accepts formats:  "YYYY-MM-DD HH:MM:SS", "YYYY-MM-DD HH:MM",
        and "YYYY-MM-DD".  Returns (start, end).  'end' defaults to
        current UTC time if not provided.  Returns (None, None) on failure.
        """
        TIME_FORMATS = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]

        if not self._start_time:
            seiscomp.logging.error(
                "--start-time is required for time-range queries.")
            return None, None

        t_start = self._parse_time(self._start_time, TIME_FORMATS, "start-time")
        if t_start is None:
            return None, None

        if self._end_time:
            t_end = self._parse_time(self._end_time, TIME_FORMATS, "end-time")
            if t_end is None:
                return None, None
        else:
            t_end = seiscomp.core.Time.GMT()

        if t_end <= t_start:
            seiscomp.logging.error(
                "end-time must be after start-time: %s <= %s"
                % (t_end.toString("%Y-%m-%d %H:%M:%S"),
                   t_start.toString("%Y-%m-%d %H:%M:%S")))
            return None, None

        return t_start, t_end

    @staticmethod
    def _parse_time(value, formats, label):
        """Try to parse *value* as a Time using each format in *formats*.

        Returns a Time on success, or None and logs an error on failure.
        """
        for fmt in formats:
            try:
                t = seiscomp.core.Time.FromString(value, fmt)
                if t and t.valid():
                    return t
            except RuntimeError:
                continue

        seiscomp.logging.error(
            "Invalid --%s: \"%s\" (expected \"YYYY-MM-DD HH:MM:SS\", "
            "\"YYYY-MM-DD HH:MM\", or \"YYYY-MM-DD\")" % (label, value))
        return None


# ═══════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════

def main():
    app = ScmapApp(len(sys.argv), sys.argv)
    return app()


if __name__ == '__main__':
    sys.exit(main())

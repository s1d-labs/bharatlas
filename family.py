"""What this family scrapes: bharatlas (https://bharatlas.com), India's open atlas by Urban Morph.

bharatlas republishes open geo data from LGD, Survey of India, Bhuvan, FSI, CWC, PMGSY, DataMeet, OpenCity and others, one file
per layer, and says so: "search engines, AI assistants and dataset crawlers are all welcome" (robots.txt). The API is open (no key,
120 requests a minute per IP) and asks for a User-Agent that names the app.

1. <family>-layers    every curated layer of the catalogue (/api/v1/layers, about 161): the Parquet file (GeoJSON where a layer has
                      no Parquet), the layer's catalogue card (source, licence, attribution, notes) and its column schema.
                      Files on bharatlas's public R2 bucket, about 7.7 GB. Queue key `<layer id>@<etag 12>`: a new Setup run adds
                      only layers whose file changed.
2. <family>-releases  the dated, immutable releases (/releases/index.json): Census 2011 <-> LGD crosswalk, the dated catalogue
                      record. Every file of the manifest, checked against its SHA-256. Queue key = release code.

Not collected: community submissions (/api/v1/submissions; people's own uploads, credited to private persons), the PMTiles,
KML, Shapefile and GeoJSON copies of layers that have Parquet (the same data).
"""
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

FAMILY = json.loads((Path(__file__).parent / "scrape.json").read_text())["family"]
UA = {"User-Agent": "s1d-labs-scraper/1.0 (https://github.com/s1d-labs)"}
SITE = "https://bharatlas.com"
API = SITE + "/api/v1"
FILES_HOST = "pub-0429b8e3b5a946e69ea007df844a6f1c.r2.dev"


def _get(url, timeout=120, method="GET", tries=4):
    """GET (body) or HEAD (headers), with retries: the API and R2 sometimes stall for a minute."""
    for n in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read() if method == "GET" else dict(r.headers)
        except (OSError, urllib.error.URLError):
            if n == tries - 1:
                raise
            time.sleep(10 * (n + 1))


def pick_file(layer):
    """Pure: (format, url, bytes) of the one file to keep: Parquet, else GeoJSON, else None."""
    d = layer.get("downloads") or {}
    for fmt in ("parquet", "geojson"):
        if (d.get(fmt) or {}).get("url"):
            return fmt, d[fmt]["url"], d[fmt].get("bytes")
    return None


def is_curated(layer):
    """Pure: community layers (people's own submissions) are left out."""
    return layer.get("provenance") != "community"


def etag_of(headers):
    return (headers.get("ETag") or headers.get("etag") or "").replace("W/", "").strip('"')


def all_layers():
    out, off = [], 0
    while True:
        page = json.loads(_get(f"{API}/layers?limit=200&offset={off}"))
        out += page["data"]
        off += len(page["data"])
        if not page["data"] or off >= page.get("total", 0):
            return out


def layer_items():
    items = []
    for layer in all_layers():
        f = pick_file(layer)
        if not f or not is_curated(layer):
            continue
        fmt, url, size = f
        try:
            tag = etag_of(_get(url, timeout=60, method="HEAD"))[:12]
        except OSError:
            tag = ""
        tag = tag or f"b{size}"
        items.append({"key": f"{layer['id']}@{tag}"[:200],
                      "payload": {"id": layer["id"], "format": fmt, "url": url, "bytes": size, "layer": layer, "expected": 1}})
    return items


def release_items():
    index = json.loads(_get(SITE + "/releases/index.json"))
    return [{"key": r["code"], "payload": {"code": r["code"], "manifest": r["manifest"], "expected": 1}}
            for r in index.get("releases", [])]


PROJECTS = [
    {
        "name": f"{FAMILY}-releases", "title": "bharatlas dated releases (Census 2011 <-> LGD crosswalk, catalogue record)",
        "task": "releases", "target": "bharatlas.com", "env": {}, "probe": f"{FAMILY}:releases",
        "unit_label": "release", "record_label": "release", "items": release_items, "max_workers": 1, "threads": 1, "delay_ms": 1000,
    },
    {
        "name": f"{FAMILY}-layers", "title": "bharatlas open geo layers of India (Parquet files and catalogue cards)",
        "task": "layers", "target": FILES_HOST, "env": {}, "probe": f"{FAMILY}:api",
        "unit_label": "layer", "record_label": "layer", "items": layer_items, "max_workers": 2, "threads": 1, "delay_ms": 1000,
    },
]

# projects kept out of the pool (name -> reason); setup_family.py takes them out
HELD = {}

PROBES = [
    {"name": f"{FAMILY}:api", "url": f"{API}/categories", "expect": "layer_count"},
    {"name": f"{FAMILY}:releases", "url": f"{SITE}/releases/index.json", "expect": "releases"},
]

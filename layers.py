"""Task `layers`: one bharatlas layer per queue item.

Payload: {"id", "format", "url", "bytes", "layer": <catalogue card from /api/v1/layers>}. The task downloads the file from
bharatlas's public R2 bucket, checks its size, reads the layer's column schema from the API, keeps the file in the family's
bucket at `<project>/<layer id>/<etag 12>/<file name>` and stores one record per layer (id = layer id; a new version replaces it).

Try one layer without the hub (downloads the file to ./local-out/):
  python layers.py --local lgd_states
"""
import json
import sys
from urllib.parse import urlparse

import requests

from common import LocalHub, Skip, get, run

API = "https://bharatlas.com/api/v1"
CONTENT_TYPES = {"parquet": "application/vnd.apache.parquet", "geojson": "application/geo+json"}


def file_name(url):
    return urlparse(url).path.rsplit("/", 1)[-1]


def card(layer):
    """Pure: the catalogue fields kept in the record."""
    att = layer.get("attribution") or {}
    return {
        "layer": layer["id"], "category": layer.get("category"), "level": layer.get("level"),
        "level_meta": layer.get("level_meta"), "source": layer.get("source"), "provenance": layer.get("provenance"),
        "licence": layer.get("licence"), "source_name": (att.get("primary") or {}).get("name"),
        "source_url": (att.get("primary") or {}).get("url"), "publisher_name": (att.get("publisher") or {}).get("name"),
        "publisher_url": (att.get("publisher") or {}).get("url"), "attribution": att,
        "notes": (layer.get("notes") or "")[:4000], "rows": layer.get("rows"),
        "downloads": {k: {"url": v.get("url"), "bytes": v.get("bytes")} for k, v in (layer.get("downloads") or {}).items()},
    }


def schema_columns(schema):
    """Pure: [{name, type, nested}] from /layers/:id/schema (answers differ a little in shape)."""
    data = schema.get("data", schema) if isinstance(schema, dict) else schema
    cols = data.get("columns", data) if isinstance(data, dict) else data
    out = []
    for c in cols or []:
        if isinstance(c, dict) and c.get("name"):
            out.append({"name": c["name"], "type": c.get("type"), "nested": c.get("nested")})
    return out or None


def check_body(body, expected_bytes, fmt):
    """Pure: None if the file looks whole, else why not."""
    if expected_bytes and len(body) != expected_bytes:
        return f"size {len(body)} != catalogue {expected_bytes}"
    if fmt == "parquet" and not (body[:4] == b"PAR1" and body[-4:] == b"PAR1"):
        return "not a Parquet file (magic bytes)"
    if fmt == "geojson" and not body.lstrip()[:1] == b"{":
        return "not a GeoJSON file"
    return None


def process(hub, session, item):
    p = item["payload"]
    key = item["key"]
    version = key.rsplit("@", 1)[-1]
    r = get(hub, session, p["url"], timeout=(30, 300))
    if r is None:
        raise RuntimeError("file download failed")
    if r.status_code in (404, 410):
        raise Skip(f"file {r.status_code}: {p['url']}")
    body = r.content
    bad = check_body(body, p.get("bytes"), p["format"])
    if bad:
        raise RuntimeError(bad)
    schema = None
    s = get(hub, session, f"{API}/layers/{p['id']}/schema", target=False, timeout=60)
    if s is not None and s.status_code == 200:
        try:
            schema = schema_columns(s.json())
        except ValueError:
            schema = None
    name = file_name(p["url"])
    stored = hub.upload_many([(f"{p['id']}/{version}/{name}", body, CONTENT_TYPES[p["format"]])])[0]
    hub.record(p["id"], {**card(p["layer"]), "format": p["format"], "file_url": p["url"], "file": name,
                         "version": version, "bytes": len(body), "sha256": stored["sha256"], "key": stored["key"],
                         "columns": schema, "item": key})
    return 1


def local(layer_id):
    from family import pick_file, etag_of, _get
    page = json.loads(_get(f"{API}/layers/{layer_id}"))
    layer = page.get("data", page)
    fmt, url, size = pick_file(layer)
    tag = etag_of(_get(url, method="HEAD"))[:12]
    hub = LocalHub()
    process(hub, requests.Session(), {"key": f"{layer_id}@{tag}",
                                      "payload": {"id": layer_id, "format": fmt, "url": url, "bytes": size, "layer": layer}})
    print(f"counters {hub.counts}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--local":
        local(sys.argv[2])
    else:
        run(process)

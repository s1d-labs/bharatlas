"""Task `releases`: one dated bharatlas release per queue item (for example bharatlas-cw-2026.11, the Census 2011 <-> LGD crosswalk).

Payload: {"code", "manifest": <manifest.json URL>}. The task reads the manifest, downloads every file it lists and checks each
against the manifest's SHA-256, also keeps manifest.json, CHANGES.md and SHA256SUMS, stores them at `<project>/<code>/<file>`
and keeps one record per release (id = code). Releases never change, so a code is fetched once.

Try one release without the hub:
  python releases.py --local bharatlas-cw-2026.11
"""
import sys

import requests

from common import LocalHub, get, run, sha256

SITE = "https://bharatlas.com"
EXTRA = ("manifest.json", "CHANGES.md", "SHA256SUMS")
TYPES = {"csv": "text/csv", "parquet": "application/vnd.apache.parquet", "json": "application/json",
         "md": "text/markdown", "": "text/plain"}


def ctype(name):
    ext = name.rsplit(".", 1)[-1] if "." in name else ""
    return TYPES.get(ext, "application/octet-stream")


def safe_name(name):
    """Pure: a manifest file name usable as one bucket path segment, or None."""
    return name if name and "/" not in name and ".." not in name and all(c.isalnum() or c in "._-" for c in name) else None


def process(hub, session, item):
    p = item["payload"]
    code = p["code"]
    base = p["manifest"].rsplit("/", 1)[0]
    r = get(hub, session, p["manifest"], timeout=60)
    if r is None or r.status_code != 200:
        raise RuntimeError("manifest download failed")
    manifest = r.json()
    files, kept = [], []
    for f in manifest.get("files", []):
        name = safe_name(f.get("name"))
        if not name:
            raise RuntimeError(f"odd file name in manifest: {f.get('name')!r}")
        r = get(hub, session, f.get("url") or f"{base}/{name}", timeout=(30, 120))
        if r is None or r.status_code != 200:
            raise RuntimeError(f"download failed: {name}")
        if f.get("sha256") and sha256(r.content) != f["sha256"]:
            raise RuntimeError(f"sha256 mismatch: {name}")
        files.append((f"{code}/{name}", r.content, ctype(name)))
        kept.append({"name": name, "bytes": len(r.content), "rows": f.get("rows"), "licence": f.get("licence"),
                     "source_layer": f.get("source_layer"), "sha256": f.get("sha256")})
    for name in EXTRA:
        r = get(hub, session, f"{base}/{name}", timeout=60)
        if r is not None and r.status_code == 200:
            files.append((f"{code}/{name}", r.content, ctype(name)))
    stored = hub.upload_many(files)
    hub.record(code, {"code": code, "dataset": manifest.get("dataset"), "title": manifest.get("title"),
                      "description": manifest.get("description"), "released": manifest.get("released"),
                      "pin": manifest.get("pin"), "sha256": manifest.get("sha256"), "files": kept,
                      "keys": [s["key"] for s in stored]})
    return 1


def local(code):
    hub = LocalHub()
    process(hub, requests.Session(), {"key": code, "payload": {"code": code,
                                                               "manifest": f"{SITE}/releases/{code}/manifest.json"}})
    print(f"counters {hub.counts}", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--local":
        local(sys.argv[2])
    else:
        run(process)

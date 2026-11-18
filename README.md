# bharatlas

Open geo layers of India from [bharatlas](https://bharatlas.com) (Urban Morph), for the s1d-labs scrape pool. The pool runs this
code on members' GitHub Actions minutes, coordinated by [scrape.s1d.me](https://scrape.s1d.me); the full contract is in `CLAUDE.md`.

bharatlas republishes open data from government bodies and open-data groups (LGD, Survey of India, Bhuvan, Forest Survey of
India, CWC, PMGSY, DataMeet, OpenCity and others). Its robots.txt welcomes crawlers, the API needs no key (120 requests a minute
per IP), and each layer names its licence and source.

## Projects

### `bharatlas-layers`: every curated layer

- **Queue**: one item per layer file, key `<layer id>@<etag 12>` (`family.py`, `layer_items()`). Setup lists `/api/v1/layers`
  and reads each file's ETag (HEAD). A new Setup run adds only the layers whose file changed. About 160 layers, 8 GB.
- **Task** `layers` (`layers.py`): downloads the layer's Parquet file (GeoJSON for the 5 layers with no Parquet) from bharatlas's
  public R2 bucket, checks the size and the Parquet magic bytes, reads the column schema (`/api/v1/layers/<id>/schema`).
- **Files**: `bharatlas-layers/<layer id>/<etag 12>/<file>` in the family's bucket.
- **Records**: one per layer, id = layer id: `category`, `level`, `source`, `licence`, `source_name`, `source_url`,
  `publisher_name`, `attribution`, `notes`, `rows`, `downloads` (all formats), `format`, `file_url`, `version`, `bytes`,
  `sha256`, `key`, `columns`.

### `bharatlas-releases`: dated releases

- **Queue**: one item per release code from `/releases/index.json` (for example `bharatlas-cw-2026.11`, the Census 2011 <-> LGD
  crosswalk, and `bharatlas-catalog-2026.11`). Releases never change.
- **Task** `releases` (`releases.py`): every file of the manifest, checked against its SHA-256, plus `manifest.json`,
  `CHANGES.md` and `SHA256SUMS`, at `bharatlas-releases/<code>/<file>`. One record per release.

## Not collected

- Community submissions (`/api/v1/submissions`): people's own uploads, credited to private persons.
- The PMTiles, KML, Shapefile and GeoJSON copies of layers that have Parquet (the same data).

## Licences and credit

- Each record has the layer's licence and its original source. Credit the original source first (for example "Local Government
  Directory, via bharatlas").
- Some layers are Bhuvan (NRSC/ISRO) data that bharatlas marks CC0. Bhuvan's own data policy is stricter. Check before you
  republish those layers.

## Working here

```
python layers.py --local ngt_zones                 # one layer to ./local-out/
python releases.py --local bharatlas-cw-2026.11    # one release to ./local-out/
python -m pytest tests -q                          # pure-function tests, no network
scrape-check --project bharatlas-releases --task releases --items 1
```

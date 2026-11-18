"""Pure-function tests on synthetic data (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from family import etag_of, is_curated, pick_file  # noqa: E402
from layers import card, check_body, file_name, schema_columns  # noqa: E402
from releases import ctype, safe_name  # noqa: E402

LAYER = {"id": "lgd_states", "category": "boundaries", "source": "LGD", "provenance": "curated", "licence": "CC0-1.0",
         "attribution": {"primary": {"name": "Local Government Directory", "url": "https://lgdirectory.gov.in/"}, "publisher": None},
         "rows": 36, "downloads": {"parquet": {"url": "https://x.r2.dev/admin/states/LGD_States.parquet", "bytes": 10},
                                   "geojson": {"url": "https://x.r2.dev/a.geojson", "bytes": 20}}}


def test_pick_file_prefers_parquet_then_geojson():
    assert pick_file(LAYER) == ("parquet", "https://x.r2.dev/admin/states/LGD_States.parquet", 10)
    assert pick_file({"downloads": {"geojson": {"url": "u", "bytes": 1}, "kml": {"url": "k"}}}) == ("geojson", "u", 1)
    assert pick_file({"downloads": {"pmtiles": {"url": "p"}}}) is None


def test_community_layers_left_out():
    assert is_curated(LAYER) and not is_curated({"provenance": "community"})


def test_etag():
    assert etag_of({"ETag": '"150187e2339f"'}) == "150187e2339f"
    assert etag_of({"etag": 'W/"abc"'}) == "abc"
    assert etag_of({}) == ""


def test_card_and_file_name():
    c = card(LAYER)
    assert c["source_name"] == "Local Government Directory" and c["publisher_name"] is None
    assert c["downloads"]["geojson"]["bytes"] == 20
    assert file_name(LAYER["downloads"]["parquet"]["url"]) == "LGD_States.parquet"


def test_check_body():
    good = b"PAR1" + b"x" * 2 + b"PAR1"
    assert check_body(good, 10, "parquet") is None
    assert "size" in check_body(good, 11, "parquet")
    assert "magic" in check_body(b"x" * 10, 10, "parquet")
    assert check_body(b' {"type":1}', None, "geojson") is None


def test_schema_columns_shapes():
    assert schema_columns({"data": {"columns": [{"name": "a", "type": "string"}]}}) == [{"name": "a", "type": "string", "nested": None}]
    assert schema_columns({"data": [{"name": "b"}]}) == [{"name": "b", "type": None, "nested": None}]
    assert schema_columns({}) is None


def test_release_names():
    assert safe_name("cw_blocks.csv") == "cw_blocks.csv"
    assert safe_name("../x") is None and safe_name("a/b") is None and safe_name("") is None
    assert ctype("x.parquet") == "application/vnd.apache.parquet" and ctype("SHA256SUMS") == "text/plain"

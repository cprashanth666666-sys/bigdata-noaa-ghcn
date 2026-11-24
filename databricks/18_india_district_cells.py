# Databricks notebook source
# India pilot, story IN-1.3: district boundaries, grid-cell-to-district mapping, and the name crosswalk
# between boundary districts and DES yield districts.
#
# Sources: geoBoundaries gbOpen IND ADM1 (states) and ADM2 (districts), GeoJSON on GitHub,
#          licence ODbL 1.0, boundary source lgdirectory.gov.in. https://www.geoboundaries.org
# Inputs : imd_rain_daily (16) for the list of land cells; in_district_yields (17) for district names
# Outputs (workspace.default):
#   in_districts        one row per boundary district: state, district, keys, area_km2, centroid, cells
#   in_district_cells   one row per 0.25 deg IMD land cell whose centre lies in a district
#   in_district_xwalk   one row per DES yield district: matched boundary district (or none) and match method
# Assumptions:
#   - A cell belongs to the district that contains its centre (point in polygon, matplotlib.path).
#     IMD land cells outside every state polygon (border cells beyond the geoBoundaries outline) are dropped.
#     Districts smaller than one cell (about 770 km2 at 20N) may get no cell; they take the nearest cell
#     to their centroid, flagged as nearest_cell = true.
#   - A boundary district's state = the ADM1 polygon containing its centroid.
#   - Names match inside a state: exact key first, then difflib similarity >= 0.85. Unmatched DES districts
#     are listed, not guessed; most are districts created or renamed after the boundary release.

# COMMAND ----------

import difflib, json, math, os, requests, unicodedata
import numpy as np, pandas as pd
from matplotlib.path import Path
from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
BASE = f"/Volumes/{CATALOG}/default/india_climate/boundaries"
os.makedirs(BASE, exist_ok=True)
API = "https://www.geoboundaries.org/api/current/gbOpen/IND/{}/"


def fetch(level):
    meta = requests.get(API.format(level), timeout=60).json()
    dest = f"{BASE}/IND_{level}.geojson"
    if not os.path.exists(dest):
        r = requests.get(meta["gjDownloadURL"], timeout=600)
        r.raise_for_status()
        open(dest, "wb").write(r.content)
    return json.load(open(dest, encoding="utf-8")), meta


adm1, m1 = fetch("ADM1")
adm2, m2 = fetch("ADM2")
print("ADM1", len(adm1["features"]), m1["boundaryLicense"], "| ADM2", len(adm2["features"]), m2["boundaryLicense"])

# COMMAND ----------

def rings(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    return [Path(np.asarray(p[0])[:, :2]) for p in polys]          # outer rings; holes are rare at district level


def contains(paths, pts):
    inside = np.zeros(len(pts), dtype=bool)
    for p in paths:
        inside |= p.contains_points(pts)
    return inside


def ring_area_km2(path, lat0):
    x, y = path.vertices[:, 0], path.vertices[:, 1]
    a = 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))   # square degrees
    return a * 111.32 * 111.32 * math.cos(math.radians(lat0))


# ASCII key: geoBoundaries names carry diacritics ("Mahārāshtra"); DES names are plain ASCII ("Maharashtra").
key = lambda s: "".join(ch for ch in unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower() if "a" <= ch <= "z")
states = [(f["properties"]["shapeName"], rings(f["geometry"])) for f in adm1["features"]]

rows = []
for f in adm2["features"]:
    paths = rings(f["geometry"])
    v = np.vstack([p.vertices for p in paths])
    lon_c, lat_c = float(v[:, 0].mean()), float(v[:, 1].mean())
    state = next((n for n, sp in states if contains(sp, np.array([[lon_c, lat_c]]))[0]), None)
    if state is None:   # centroid in a gap or on the coast: use the nearest state vertex
        state = min(states, key=lambda s: min(np.min((p.vertices[:, 0] - lon_c) ** 2 + (p.vertices[:, 1] - lat_c) ** 2) for p in s[1]))[0]
    rows.append({"shape_id": f["properties"]["shapeID"], "district": f["properties"]["shapeName"], "state": state,
                 "lon": lon_c, "lat": lat_c, "area_km2": sum(ring_area_km2(p, lat_c) for p in paths), "paths": paths})

# COMMAND ----------

cells = spark.table(f"{S}.imd_rain_daily").select("lat", "lon").distinct().toPandas()
pts = cells[["lon", "lat"]].to_numpy()
owner = np.full(len(pts), None, dtype=object)
for r in rows:
    hit = contains(r["paths"], pts) & (owner == None)  # noqa: E711  first district wins on shared borders
    owner[hit] = r["shape_id"]
cells["shape_id"] = owner
cells["nearest_cell"] = False

assigned = cells.dropna(subset=["shape_id"])
missing = [r for r in rows if r["shape_id"] not in set(assigned["shape_id"])]
extra = []
for r in missing:   # district smaller than a cell: borrow the nearest land cell
    i = int(np.argmin((pts[:, 0] - r["lon"]) ** 2 + (pts[:, 1] - r["lat"]) ** 2))
    extra.append({"lat": pts[i, 1], "lon": pts[i, 0], "shape_id": r["shape_id"], "nearest_cell": True})
dc = pd.concat([assigned, pd.DataFrame(extra)], ignore_index=True)

n_cells = dc.groupby("shape_id").size()
dist = pd.DataFrame([{k: v for k, v in r.items() if k != "paths"} for r in rows])
dist["state_key"] = dist["state"].map(key)
dist["district_key"] = dist["district"].map(key)
dist["n_cells"] = dist["shape_id"].map(n_cells).fillna(0).astype(int)

spark.createDataFrame(dist).write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_districts")
spark.createDataFrame(dc).write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_district_cells")
print(f"districts {len(dist)}, cells assigned {len(assigned)} of {len(pts)}, small districts given nearest cell {len(extra)}")

# COMMAND ----------

# Name crosswalk: DES yield districts -> boundary districts, inside the same state.
des = spark.table(f"{S}.in_district_yields").select("state", "district", "state_key", "district_key").distinct().toPandas()
bstate = {k: [] for k in dist["state_key"].unique()}
for _, r in dist.iterrows():
    bstate[r["state_key"]].append(r)
state_match = {sk: (sk if sk in bstate else (difflib.get_close_matches(sk, list(bstate), n=1, cutoff=0.8) or [None])[0])
               for sk in des["state_key"].unique()}

out = []
for _, d in des.iterrows():
    cands = bstate.get(state_match[d["state_key"]], [])
    keys = [c["district_key"] for c in cands]
    method, hit = "none", None
    if d["district_key"] in keys:
        method, hit = "exact", cands[keys.index(d["district_key"])]
    else:
        close = difflib.get_close_matches(d["district_key"], keys, n=1, cutoff=0.85)
        if close:
            method, hit = "fuzzy", cands[keys.index(close[0])]
    out.append({"state": d["state"], "district": d["district"], "state_key": d["state_key"], "district_key": d["district_key"],
                "shape_id": None if hit is None else hit["shape_id"],
                "boundary_district": None if hit is None else hit["district"], "match": method})
xw = pd.DataFrame(out)
spark.createDataFrame(xw).write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_district_xwalk")

# COMMAND ----------

# Checks
assert dist["shape_id"].is_unique
assert not assigned.duplicated(["lat", "lon"]).any(), "a cell was assigned to two districts"
# IMD's land grid includes border cells that the geoBoundaries outline of India leaves out (western
# border, far north). So the test is: of the cells inside some state polygon, nearly all must get a district.
in_state = np.zeros(len(pts), dtype=bool)
for _, sp in states:
    in_state |= contains(sp, pts)
in_district = cells["shape_id"].notna().to_numpy()
share_cells = (in_district & in_state).sum() / in_state.sum()
print(f"IMD land cells: {len(pts)}; inside a state outline: {in_state.sum()}; outside India's outline (excluded): {(~in_state).sum()}")
print(f"cells inside a state that got a district: {share_cells:.2%}")
assert share_cells > 0.99, "district polygons leave gaps inside states"

# Second method for area: total district area vs India's reported land area (3.287 million km2 incl. claimed areas).
print(f"sum of district areas: {dist['area_km2'].sum()/1e6:.2f} million km2")

m = xw["match"].value_counts().to_dict()
print("crosswalk:", m, f"matched {(xw['match'] != 'none').mean():.1%} of {len(xw)} DES districts")
# Weighted by yield rows, since that is what the analysis uses
yrows = spark.table(f"{S}.in_district_yields").groupBy("state_key", "district_key").count().toPandas()
j = yrows.merge(xw, on=["state_key", "district_key"])
print(f"share of yield rows with a matched district: {j.loc[j['match'] != 'none', 'count'].sum() / j['count'].sum():.1%}")
display(spark.createDataFrame(xw[xw["match"] == "none"].sort_values(["state", "district"])))

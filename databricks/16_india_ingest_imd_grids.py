# Databricks notebook source
# India pilot, story IN-1.1: ingest IMD gridded daily rainfall (0.25 deg) and max/min temperature (1.0 deg)
# into a Unity Catalog Volume and Bronze Delta tables.
#
# Source : India Meteorological Department, Pune, gridded data archive (no key; one binary .grd file per year)
#   rain : POST https://www.imdpune.gov.in/cmpg/Griddata/rainfall.php  field rain=<year>     -> ind<year>_rfp25.grd
#   tmax : POST https://www.imdpune.gov.in/cmpg/Griddata/maxtemp.php   field maxtemp=<year>  -> Maxtemp_MaxT_<year>.GRD
#   tmin : POST https://www.imdpune.gov.in/cmpg/Griddata/mintemp.php   field mintemp=<year>  -> Mintemp_MinT_<year>.GRD
#   Years offered by the archive form: 1990 to 2025 (checked 24 Nov 2026).
# File layout (same as the imdlib package, MIT licence, v0.4.0):
#   little-endian float32, stored as (days, lat, lon) in C order
#   rain grid: first cell centre 66.5E 6.5N, step 0.25, 135 lon x 129 lat; missing = -999
#   temp grid: first cell centre 67.5E 7.5N, step 1.0,  31 lon x 31 lat;  missing = 99.9
# Outputs (workspace.default):
#   imd_rain_daily  (lat, lon, date, year, rain_mm)            land cells only, partitioned by year
#   imd_temp_daily  (lat, lon, date, year, tmax_c, tmin_c)     land cells only, partitioned by year
# Assumptions:
#   - A cell-day whose value equals the missing code is dropped, not set to zero (same rule as GHCN QC drops).
#   - Re-running overwrites only the years passed in YEARS (replaceWhere), so years can be loaded in batches.

# COMMAND ----------

dbutils.widgets.text("YEARS", "2023", "Years, e.g. 2023 or 1990-2025")
spec = dbutils.widgets.get("YEARS").strip()
YEARS = list(range(int(spec.split("-")[0]), int(spec.split("-")[1]) + 1)) if "-" in spec else [int(spec)]

import calendar, os, time, numpy as np, pandas as pd, requests
from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
spark.sql(f"CREATE VOLUME IF NOT EXISTS {S}.india_climate")
BASE = f"/Volumes/{CATALOG}/default/india_climate"
HEADERS = {"User-Agent": "student-bigdata-project"}

VARS = {  # name: (url, form field, file name pattern, lon0, lat0, step, nlon, nlat, missing)
    "rain": ("https://www.imdpune.gov.in/cmpg/Griddata/rainfall.php", "rain", "ind{y}_rfp25.grd", 66.5, 6.5, 0.25, 135, 129, -999.0),
    "tmax": ("https://www.imdpune.gov.in/cmpg/Griddata/maxtemp.php", "maxtemp", "Maxtemp_MaxT_{y}.GRD", 67.5, 7.5, 1.0, 31, 31, 99.9),
    "tmin": ("https://www.imdpune.gov.in/cmpg/Griddata/mintemp.php", "mintemp", "Mintemp_MinT_{y}.GRD", 67.5, 7.5, 1.0, 31, 31, 99.9),
}
for v in VARS:
    os.makedirs(f"{BASE}/{v}", exist_ok=True)
print(CATALOG, BASE, YEARS)

# COMMAND ----------

def download(var, year):
    url, field, pattern, *_ , nlon, nlat, _miss = VARS[var]
    days = 366 if calendar.isleap(year) else 365
    expected = days * nlon * nlat * 4
    dest = f"{BASE}/{var}/{pattern.format(y=year)}"
    if os.path.exists(dest) and os.path.getsize(dest) == expected:
        return dest, "cached"
    for attempt in range(3):
        try:
            r = requests.post(url, data={field: str(year)}, headers=HEADERS, timeout=600)
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(10)
    # The server returns an empty file for a year it does not hold; a wrong size means a broken download.
    assert len(r.content) == expected, f"{var} {year}: got {len(r.content)} bytes, expected {expected}"
    with open(dest, "wb") as f:
        f.write(r.content)
    return dest, "downloaded"


def to_long(var, year, path):
    _u, _f, _p, lon0, lat0, step, nlon, nlat, missing = VARS[var]
    days = 366 if calendar.isleap(year) else 365
    a = np.fromfile(path, dtype="<f4").reshape(days, nlat, nlon)
    d, i, j = np.nonzero(~np.isclose(a, missing))
    return pd.DataFrame({
        "lat": np.round(lat0 + i * step, 2), "lon": np.round(lon0 + j * step, 2),
        "date": pd.to_datetime(f"{year}-01-01") + pd.to_timedelta(d, unit="D"),
        "year": year, var: a[d, i, j].astype("float64"),
    })

# COMMAND ----------

log = []
for y in YEARS:
    paths = {}
    for v in VARS:
        paths[v], status = download(v, y)
        log.append((y, v, status, os.path.getsize(paths[v])))
    rain = to_long("rain", y, paths["rain"]).rename(columns={"rain": "rain_mm"})
    temp = to_long("tmax", y, paths["tmax"]).merge(to_long("tmin", y, paths["tmin"]), on=["lat", "lon", "date", "year"], how="outer")
    temp = temp.rename(columns={"tmax": "tmax_c", "tmin": "tmin_c"})
    for name, pdf in [("imd_rain_daily", rain), ("imd_temp_daily", temp)]:
        (spark.createDataFrame(pdf).withColumn("date", F.to_date("date"))
            .write.format("delta").mode("overwrite").partitionBy("year")
            .option("replaceWhere", f"year = {y}")
            .saveAsTable(f"{S}.{name}"))
    print(y, "rain rows", len(rain), "temp rows", len(temp))

display(spark.createDataFrame(log, "year INT, var STRING, status STRING, bytes LONG"))

# COMMAND ----------

# Checks: physical ranges, no duplicate cell-days, land-cell count stable across years,
# and a second method: the all-India June-September rainfall mean recomputed from the raw file with numpy.
rain = spark.table(f"{S}.imd_rain_daily").where(F.col("year").isin(YEARS))
temp = spark.table(f"{S}.imd_temp_daily").where(F.col("year").isin(YEARS))

dups = rain.groupBy("lat", "lon", "date").count().where("count > 1").count()
assert dups == 0, f"{dups} duplicate rain cell-days"
bad_rain = rain.where("rain_mm < 0 OR rain_mm > 1500").count()
bad_temp = temp.where("tmax_c < -40 OR tmax_c > 55 OR tmin_c < -50 OR tmin_c > 45").count()
assert bad_rain == 0 and bad_temp == 0, (bad_rain, bad_temp)

cells = rain.groupBy("year").agg(F.countDistinct("lat", "lon").alias("land_cells"), F.count("*").alias("rows")).orderBy("year")
display(cells)

y = YEARS[-1]
_u, _f, pattern, lon0, lat0, step, nlon, nlat, missing = VARS["rain"]
days = 366 if calendar.isleap(y) else 365
a = np.fromfile(f"{BASE}/rain/{pattern.format(y=y)}", dtype="<f4").reshape(days, nlat, nlon)
doy0 = pd.Timestamp(f"{y}-06-01").dayofyear - 1
jjas = a[doy0:doy0 + 122]
full = (~np.isclose(jjas, missing)).all(axis=0)          # cells observed on all 122 days
np_mean = float(jjas.sum(axis=0, dtype="float64")[full].mean())
sp_mean = (rain.where(f"year = {y} AND month(date) BETWEEN 6 AND 9").groupBy("lat", "lon").agg(F.sum("rain_mm").alias("s"), F.count("*").alias("n"))
           .where("n = 122").agg(F.avg("s")).first()[0])
print(f"{y} June-September mean rainfall over land cells: numpy {np_mean:.1f} mm, Spark {sp_mean:.1f} mm")
assert abs(np_mean - sp_mean) < 1.0, "numpy and Spark disagree"

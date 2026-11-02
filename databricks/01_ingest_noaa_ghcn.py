# Databricks notebook source
# Ingest NOAA GHCN-Daily (2019-2025) from the public AWS Open Data bucket
# into a Unity Catalog Volume, then load it into Delta tables.
# Source: https://registry.opendata.aws/noaa-ghcn/  (no key needed)

# COMMAND ----------

import json, os, shutil, requests
from concurrent.futures import ThreadPoolExecutor
from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "default"
YEARS = list(range(2019, 2026))
SRC = "https://noaa-ghcn-pds.s3.amazonaws.com"
HEADERS = {"User-Agent": "student-bigdata-project"}

spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.bigdata")
BASE = f"/Volumes/{CATALOG}/{SCHEMA}/bigdata/ghcn"
os.makedirs(f"{BASE}/by_year", exist_ok=True)
print(CATALOG, BASE)

# COMMAND ----------

def download(url, dest):
    # Skip files already fully downloaded, so the notebook can be re-run safely.
    remote_size = int(requests.head(url, timeout=60, headers=HEADERS).headers["Content-Length"])
    if os.path.exists(dest) and os.path.getsize(dest) == remote_size:
        return dest, remote_size, "cached"
    with requests.get(url, stream=True, timeout=600, headers=HEADERS) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            shutil.copyfileobj(r.raw, f, length=16 * 1024 * 1024)
    assert os.path.getsize(dest) == remote_size, f"size mismatch for {url}"
    return dest, remote_size, "downloaded"

pairs = [(f"{SRC}/csv/by_year/{y}.csv", f"{BASE}/by_year/{y}.csv") for y in YEARS]
pairs.append((f"{SRC}/ghcnd-stations.txt", f"{BASE}/ghcnd-stations.txt"))

with ThreadPoolExecutor(4) as ex:
    downloads = list(ex.map(lambda p: download(*p), pairs))

raw_gb = sum(size for _, size, _ in downloads) / 1e9
for path, size, status in downloads:
    print(f"{os.path.basename(path):24s} {size/1e9:6.2f} GB  {status}")
print(f"Raw total: {raw_gb:.2f} GB")

# COMMAND ----------

# Daily observations -> Delta. DATA_VALUE units depend on ELEMENT
# (e.g. TMAX/TMIN in tenths of degC, PRCP in tenths of mm).
schema = ("ID STRING, DATE STRING, ELEMENT STRING, DATA_VALUE INT, "
          "M_FLAG STRING, Q_FLAG STRING, S_FLAG STRING, OBS_TIME STRING")

daily = (spark.read.csv(f"{BASE}/by_year/*.csv", header=True, schema=schema)
    .withColumn("date", F.to_date("DATE", "yyyyMMdd"))
    .withColumn("year", F.year("date"))
    .withColumn("country_code", F.substring("ID", 1, 2))
    .select(F.col("ID").alias("station_id"), "date", "year", "country_code",
            F.col("ELEMENT").alias("element"), F.col("DATA_VALUE").alias("value"),
            F.col("M_FLAG").alias("m_flag"), F.col("Q_FLAG").alias("q_flag"),
            F.col("S_FLAG").alias("s_flag"), F.col("OBS_TIME").alias("obs_time")))

(daily.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .partitionBy("year")
    .saveAsTable(f"{CATALOG}.{SCHEMA}.ghcn_daily"))

# COMMAND ----------

# Station metadata is fixed-width (see GHCN-Daily readme section IV).
stations = (spark.read.text(f"{BASE}/ghcnd-stations.txt")
    .select(
        F.trim(F.substring("value", 1, 11)).alias("station_id"),
        F.trim(F.substring("value", 13, 8)).cast("double").alias("latitude"),
        F.trim(F.substring("value", 22, 9)).cast("double").alias("longitude"),
        F.trim(F.substring("value", 32, 6)).cast("double").alias("elevation_m"),
        F.trim(F.substring("value", 39, 2)).alias("state"),
        F.trim(F.substring("value", 42, 30)).alias("name"),
        F.substring("value", 1, 2).alias("country_code")))

(stations.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOG}.{SCHEMA}.ghcn_stations"))

# COMMAND ----------

t = spark.table(f"{CATALOG}.{SCHEMA}.ghcn_daily")
per_year = {r["year"]: r["count"] for r in t.groupBy("year").count().collect()}
detail = spark.sql(f"DESCRIBE DETAIL {CATALOG}.{SCHEMA}.ghcn_daily").first()

summary = {
    "raw_csv_gb": round(raw_gb, 2),
    "daily_rows": sum(per_year.values()),
    "rows_per_year": dict(sorted(per_year.items())),
    "delta_gb": round(detail["sizeInBytes"] / 1e9, 2),
    "delta_files": detail["numFiles"],
    "distinct_stations": t.select("station_id").distinct().count(),
    "distinct_elements": t.select("element").distinct().count(),
    "station_rows": spark.table(f"{CATALOG}.{SCHEMA}.ghcn_stations").count(),
    "tables": [f"{CATALOG}.{SCHEMA}.ghcn_daily", f"{CATALOG}.{SCHEMA}.ghcn_stations"],
}
print(json.dumps(summary, indent=2))
dbutils.notebook.exit(json.dumps(summary))

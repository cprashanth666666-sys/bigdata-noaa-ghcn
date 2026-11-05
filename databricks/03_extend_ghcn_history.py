# Databricks notebook source
# Story 1.3: extend GHCN-Daily back to 2000 so each county has ~26 seasons.
#
# Inputs : s3://noaa-ghcn-pds/csv/by_year/{2000..2018}.csv (public)
# Output : appends years 2000-2018 to workspace.default.ghcn_daily (same schema, partitioned by year)
# Assumptions (document any change here):
#   - Only US stations (ID prefix "US") and elements PRCP, TMAX, TMIN are kept for the new years.
#     This keeps storage small on the Free Edition and is all the trigger features need.
#     Years 2019-2025 already in the table are unfiltered; downstream notebooks must filter the same way.
#   - Each year is loaded on its own with replaceWhere, so the notebook is safe to re-run.
#   - Each raw CSV is deleted after loading to save Volume space.

# COMMAND ----------

import os, shutil, json, requests
from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "default"
TABLE = f"{CATALOG}.{SCHEMA}.ghcn_daily"
NEW_YEARS = list(range(2000, 2019))
KEEP_ELEMENTS = ["PRCP", "TMAX", "TMIN"]
SRC = "https://noaa-ghcn-pds.s3.amazonaws.com/csv/by_year"
HEADERS = {"User-Agent": "student-bigdata-project"}
BASE = f"/Volumes/{CATALOG}/{SCHEMA}/bigdata/ghcn/by_year"
os.makedirs(BASE, exist_ok=True)

SCHEMA_DDL = ("ID STRING, DATE STRING, ELEMENT STRING, DATA_VALUE INT, "
              "M_FLAG STRING, Q_FLAG STRING, S_FLAG STRING, OBS_TIME STRING")

# COMMAND ----------

def already_loaded(year):
    return spark.table(TABLE).where(F.col("year") == year).limit(1).count() > 0

def load_year(year):
    dest = f"{BASE}/{year}.csv"
    with requests.get(f"{SRC}/{year}.csv", stream=True, timeout=600, headers=HEADERS) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            shutil.copyfileobj(r.raw, f, length=16 * 1024 * 1024)
    df = (spark.read.csv(dest, header=True, schema=SCHEMA_DDL)
        .where(F.substring("ID", 1, 2) == "US")
        .where(F.col("ELEMENT").isin(KEEP_ELEMENTS))
        .withColumn("date", F.to_date("DATE", "yyyyMMdd"))
        .select(F.col("ID").alias("station_id"), "date", F.year("date").alias("year"),
                F.substring("ID", 1, 2).alias("country_code"),
                F.col("ELEMENT").alias("element"), F.col("DATA_VALUE").alias("value"),
                F.col("M_FLAG").alias("m_flag"), F.col("Q_FLAG").alias("q_flag"),
                F.col("S_FLAG").alias("s_flag"), F.col("OBS_TIME").alias("obs_time")))
    (df.write.format("delta").mode("overwrite")
        .option("replaceWhere", f"year = {year}")
        .partitionBy("year").saveAsTable(TABLE))
    os.remove(dest)

# COMMAND ----------

for y in NEW_YEARS:
    if already_loaded(y):
        print(y, "already loaded, skipping")
        continue
    load_year(y)
    print(y, "loaded")

# COMMAND ----------

# Per-year counts (acceptance criterion: report per-year counts) and a second-method check via SQL.
per_year = spark.sql(f"""
    SELECT year, COUNT(*) AS rows, COUNT(DISTINCT station_id) AS stations
    FROM {TABLE} WHERE country_code = 'US' AND element IN ('PRCP','TMAX','TMIN')
    GROUP BY year ORDER BY year""")
per_year.show(40)

total_df = spark.table(TABLE).where("country_code = 'US' AND element IN ('PRCP','TMAX','TMIN')").count()
total_sql = sum(r["rows"] for r in per_year.collect())
assert total_df == total_sql, (total_df, total_sql)
missing = set(NEW_YEARS) - {r["year"] for r in per_year.collect()}
assert not missing, f"years missing: {missing}"
dbutils.notebook.exit(json.dumps({"us_rows_2000_2025": total_df}))

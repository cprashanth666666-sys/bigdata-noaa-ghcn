# Databricks notebook source
# Ingest USDA NASS Quick Stats crop data (county yields) and US Census county
# centroids into a separate Unity Catalog Volume, then load them into Delta tables.
# Sources (no key needed):
#   https://www.nass.usda.gov/datasets/              (qs.crops_YYYYMMDD.txt.gz, refreshed daily)
#   https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html

# COMMAND ----------

import json, os, re, shutil, zipfile, requests
from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
SCHEMA = "default"
HEADERS = {"User-Agent": "student-bigdata-project"}

spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.agri_yield")
BASE = f"/Volumes/{CATALOG}/{SCHEMA}/agri_yield"
os.makedirs(f"{BASE}/nass", exist_ok=True)
os.makedirs(f"{BASE}/census", exist_ok=True)

# The crops file name carries the publish date, so find the current one.
listing = requests.get("https://www.nass.usda.gov/datasets/", headers=HEADERS, timeout=60).text
CROPS_FILE = sorted(set(re.findall(r"qs\.crops_\d{8}\.txt\.gz", listing)))[-1]
NASS_URL = f"https://www.nass.usda.gov/datasets/{CROPS_FILE}"
GAZ_URL = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip"
print(CATALOG, BASE, CROPS_FILE)

# COMMAND ----------

def download(url, dest):
    # Skip files already fully downloaded, so the notebook can be re-run safely.
    remote_size = int(requests.head(url, timeout=60, headers=HEADERS, allow_redirects=True).headers["Content-Length"])
    if os.path.exists(dest) and os.path.getsize(dest) == remote_size:
        return remote_size, "cached"
    with requests.get(url, stream=True, timeout=1200, headers=HEADERS) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            shutil.copyfileobj(r.raw, f, length=16 * 1024 * 1024)
    assert os.path.getsize(dest) == remote_size, f"size mismatch for {url}"
    return remote_size, "downloaded"

nass_path = f"{BASE}/nass/{CROPS_FILE}"
gaz_zip = f"{BASE}/census/2024_Gaz_counties_national.zip"
nass_size, nass_status = download(NASS_URL, nass_path)
gaz_size, gaz_status = download(GAZ_URL, gaz_zip)
with zipfile.ZipFile(gaz_zip) as z:
    z.extractall(f"{BASE}/census")
print(f"NASS crops: {nass_size/1e9:.2f} GB compressed ({nass_status}); gazetteer: {gaz_size/1e3:.0f} KB ({gaz_status})")

# COMMAND ----------

# Bronze: the full crops file as published (all strings). VALUE keeps NASS
# markers such as "(D)" = withheld to avoid disclosing individual farms.
nass_raw = spark.read.csv(nass_path, sep="\t", header=True)
nass_raw = nass_raw.toDF(*[re.sub(r"[^a-z0-9]+", "_", c.lower()).strip("_") for c in nass_raw.columns])

(nass_raw.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOG}.{SCHEMA}.nass_crops_raw"))

# COMMAND ----------

# Silver: annual county-level yields, survey data only, numeric values.
nass = spark.table(f"{CATALOG}.{SCHEMA}.nass_crops_raw")
county_yields = (nass
    .filter((F.col("agg_level_desc") == "COUNTY") & (F.col("statisticcat_desc") == "YIELD")
            & (F.col("source_desc") == "SURVEY") & (F.col("freq_desc") == "ANNUAL")
            & (F.col("reference_period_desc") == "YEAR") & (F.col("county_ansi") != ""))
    # Serverless runs in ANSI mode, so try_cast turns "(D)" and similar markers into NULL.
    .withColumn("yield_value", F.expr("try_cast(regexp_replace(trim(value), ',', '') AS DOUBLE)"))
    .filter(F.col("yield_value").isNotNull())
    .select(
        F.concat(F.col("state_fips_code"), F.col("county_ansi")).alias("county_fips"),
        "state_alpha", "county_name",
        F.col("commodity_desc").alias("commodity"),
        F.col("short_desc").alias("series"),
        F.col("unit_desc").alias("unit"),
        F.expr("try_cast(year AS INT)").alias("year"),
        "yield_value"))

(county_yields.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOG}.{SCHEMA}.nass_county_yields"))

# COMMAND ----------

# County centroids, used to link each county to nearby weather stations.
gaz_txt = [f for f in os.listdir(f"{BASE}/census") if f.endswith(".txt")][0]
gaz = spark.read.csv(f"{BASE}/census/{gaz_txt}", sep="\t", header=True)
gaz = gaz.toDF(*[c.strip().lower() for c in gaz.columns])
counties = gaz.select(
    F.col("geoid").alias("county_fips"),
    F.col("usps").alias("state_alpha"),
    F.col("name").alias("county_name"),
    F.expr("try_cast(trim(intptlat) AS DOUBLE)").alias("latitude"),
    F.expr("try_cast(trim(intptlong) AS DOUBLE)").alias("longitude"),
    F.expr("try_cast(trim(aland_sqmi) AS DOUBLE)").alias("land_sqmi"))

(counties.write.format("delta").mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(f"{CATALOG}.{SCHEMA}.us_counties"))

# COMMAND ----------

cy = spark.table(f"{CATALOG}.{SCHEMA}.nass_county_yields")
recent = cy.filter(F.col("year").between(2019, 2025))
top_series = (recent.groupBy("series").agg(F.countDistinct("county_fips").alias("counties"),
                                          F.count("*").alias("rows"))
              .orderBy(F.desc("rows")).limit(10).collect())
matched = (recent.select("county_fips").distinct()
           .join(spark.table(f"{CATALOG}.{SCHEMA}.us_counties"), "county_fips").count())

summary = {
    "crops_file": CROPS_FILE,
    "nass_compressed_gb": round(nass_size / 1e9, 2),
    "nass_raw_rows": spark.table(f"{CATALOG}.{SCHEMA}.nass_crops_raw").count(),
    "county_yield_rows_all_years": cy.count(),
    "county_yield_rows_2019_2025": recent.count(),
    "counties_with_yields_2019_2025": recent.select("county_fips").distinct().count(),
    "those_counties_matched_to_centroids": matched,
    "rows_per_year_2019_2025": {r["year"]: r["count"] for r in recent.groupBy("year").count().orderBy("year").collect()},
    "top_series_2019_2025": [{"series": r["series"], "counties": r["counties"], "rows": r["rows"]} for r in top_series],
    "us_counties": spark.table(f"{CATALOG}.{SCHEMA}.us_counties").count(),
    "tables": [f"{CATALOG}.{SCHEMA}.nass_crops_raw", f"{CATALOG}.{SCHEMA}.nass_county_yields",
               f"{CATALOG}.{SCHEMA}.us_counties"],
}
print(json.dumps(summary, indent=2))
dbutils.notebook.exit(json.dumps(summary))

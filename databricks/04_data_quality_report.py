# Databricks notebook source
# Story 1.4: data-quality report.
#
# Inputs : ghcn_daily, ghcn_stations, nass_county_yields, nass_crops_raw, us_counties
# Output : workspace.default.dq_report (metric, scope, value) - one row per metric
# Assumptions:
#   - Weather metrics cover US stations and PRCP/TMAX/TMIN only (what the project uses).
#   - A row "fails QC" when q_flag is not null.
#   - Yield suppression share = non-numeric yield values such as "(D)" among county-level annual survey rows.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
rows = []  # (metric, scope, value)

w = (spark.table(f"{S}.ghcn_daily")
     .where("country_code = 'US' AND element IN ('PRCP','TMAX','TMIN')"))

# COMMAND ----------

# 1. Null rate and QC-flag share, by element.
by_el = w.groupBy("element").agg(
    F.count("*").alias("n"),
    F.avg(F.col("value").isNull().cast("int")).alias("null_rate"),
    F.avg(F.col("q_flag").isNotNull().cast("int")).alias("qc_fail_share"))
for r in by_el.collect():
    rows += [("null_rate", r["element"], r["null_rate"]),
             ("qc_fail_share", r["element"], r["qc_fail_share"]),
             ("rows", r["element"], float(r["n"]))]

# 2. QC-flag share by year (does quality drift over time?).
for r in w.groupBy("year").agg(F.avg(F.col("q_flag").isNotNull().cast("int")).alias("s")).collect():
    rows.append(("qc_fail_share_by_year", str(r["year"]), r["s"]))

# COMMAND ----------

# 3. Station coverage by state: stations with any PRCP and TMAX, per state, per year.
st = spark.table(f"{S}.ghcn_stations").select("station_id", "state")
cov = (w.where("q_flag IS NULL AND value IS NOT NULL")
       .groupBy("station_id", "year").agg(
           F.max((F.col("element") == "PRCP").cast("int")).alias("has_prcp"),
           F.max((F.col("element") == "TMAX").cast("int")).alias("has_tmax"))
       .join(st, "station_id")
       .groupBy("state", "year").agg(
           F.sum("has_prcp").alias("prcp_stations"),
           F.sum("has_tmax").alias("tmax_stations")))
for r in cov.collect():
    rows += [("stations_with_prcp", f"{r['state']}|{r['year']}", float(r["prcp_stations"])),
             ("stations_with_tmax", f"{r['state']}|{r['year']}", float(r["tmax_stations"]))]

# COMMAND ----------

# 4. Yield suppression share. Raw file: county rows, annual survey, yield series.
raw = spark.table(f"{S}.nass_crops_raw")
cols = {c.lower(): c for c in raw.columns}
base = (raw.where(F.col(cols["agg_level_desc"]) == "COUNTY")
           .where(F.col(cols["source_desc"]) == "SURVEY")
           .where(F.col(cols["freq_desc"]) == "ANNUAL")
           .where(F.col(cols["statisticcat_desc"]) == "YIELD"))
tot = base.count()
numeric = base.where(F.expr(f"try_cast(regexp_replace(trim({cols['value']}), ',', '') AS DOUBLE) IS NOT NULL")).count()
rows += [("yield_rows_total", "county_annual_survey", float(tot)),
         ("yield_rows_numeric", "county_annual_survey", float(numeric)),
         ("yield_suppressed_share", "county_annual_survey", 1 - numeric / tot)]

# 5. Centroid match share (acceptance from story 1.2, re-checked).
y = spark.table(f"{S}.nass_county_yields").select("county_fips").distinct()
c = spark.table(f"{S}.us_counties").select("county_fips")
rows.append(("yield_county_centroid_match", "all",
             y.join(c, "county_fips").count() / y.count()))

# COMMAND ----------

dq = spark.createDataFrame(rows, "metric STRING, scope STRING, value DOUBLE")
dq.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.dq_report")
display(dq.where("metric IN ('null_rate','qc_fail_share','yield_suppressed_share','yield_county_centroid_match')"))
print("dq_report rows:", dq.count())

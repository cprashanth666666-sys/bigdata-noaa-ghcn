# Databricks notebook source
# India pilot, story IN-1.2: district Kharif area, production and yield into Delta.
#
# Input : /Volumes/<catalog>/default/india_climate/des/des_kharif_apy.csv
#         written by scripts/fetch_des_yields.py (run locally) from the DES APY report,
#         https://data.desagri.gov.in/website/crops-apy-report-web
#         columns: state, district, crop, season, year, area_ha, production_t, yield_t_per_ha
# Outputs (workspace.default):
#   in_des_apy_raw       the CSV as fetched (Bronze)
#   in_district_yields   cleaned Silver table: one row per state, district, crop, year with a usable yield
# Assumptions:
#   - year = first year of the agricultural year (2018 = 2018-19), which is the Kharif harvest year.
#   - Yield is used as published (tonnes per hectare). In the fetched file, yield = production / area for
#     every crop including cotton (median ratio 1.000, checked 24 Nov 2026), so units are consistent.
#     Each crop is compared only with its own district trend, so the unit does not affect loss flags.
#   - A row is usable if area > 0 and yield > 0. Yields more than 5 times the district-crop median are
#     flagged as outliers and excluded (typing or unit errors), and the count is reported.
#   - district_key = lower-case name with punctuation and spaces removed, used to join to boundaries (18).

# COMMAND ----------

from pyspark.sql import functions as F, Window

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
SRC = f"/Volumes/{CATALOG}/default/india_climate/des/des_kharif_apy.csv"

raw = spark.read.csv(SRC, header=True, inferSchema=False)
raw.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_des_apy_raw")
n_raw = raw.count()
print("raw rows", n_raw)

# COMMAND ----------

key = lambda c: F.regexp_replace(F.lower(F.trim(c)), r"[^a-z]", "")
df = (spark.table(f"{S}.in_des_apy_raw")
      .select(F.trim("state").alias("state"), F.trim("district").alias("district"), F.trim("crop").alias("crop"),
              F.col("year").cast("int").alias("year"),
              F.expr("try_cast(area_ha AS DOUBLE)").alias("area_ha"),
              F.expr("try_cast(production_t AS DOUBLE)").alias("production"),
              F.expr("try_cast(yield_t_per_ha AS DOUBLE)").alias("yield_value"))
      .withColumn("state_key", key("state")).withColumn("district_key", key("district")))

usable = df.where("area_ha > 0 AND yield_value > 0")
w = Window.partitionBy("state_key", "district_key", "crop")
flagged = usable.withColumn("med", F.percentile_approx("yield_value", 0.5).over(w)) \
                .withColumn("outlier", F.col("yield_value") > 5 * F.col("med"))
clean = flagged.where("NOT outlier").drop("med", "outlier")

(clean.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
      .saveAsTable(f"{S}.in_district_yields"))

# COMMAND ----------

# Checks
y = spark.table(f"{S}.in_district_yields")
dups = y.groupBy("state_key", "district_key", "crop", "year").count().where("count > 1").count()
summary = {
    "raw_rows": n_raw,
    "parsed_rows": df.count(),
    "unusable_rows (area or yield missing/zero)": df.count() - usable.count(),
    "outliers_dropped": flagged.where("outlier").count(),
    "clean_rows": y.count(),
    "duplicate_keys": dups,
}
print(summary)
assert summary["parsed_rows"] == n_raw, "rows lost while parsing"
assert dups == 0, "duplicate state-district-crop-year rows"

# Second method: production / area should reproduce the published yield (rounded to 2 dp).
chk = (y.where("production > 0")
        .withColumn("diff", F.abs(F.round(F.col("production") / F.col("area_ha"), 2) - F.col("yield_value"))))
share_ok = chk.where("diff <= 0.011").count() / max(chk.count(), 1)
print(f"production / area matches published yield in {share_ok:.1%} of rows")
assert share_ok > 0.95

display(y.groupBy("crop").agg(F.countDistinct("state_key", "district_key").alias("districts"),
                              F.count("*").alias("district_years"), F.min("year").alias("first"), F.max("year").alias("last"))
         .orderBy("crop"))

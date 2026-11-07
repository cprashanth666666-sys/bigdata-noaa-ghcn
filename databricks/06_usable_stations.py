# Databricks notebook source
# Story 2.2: keep only station-years with usable growing-season data.
#
# Inputs : ghcn_daily (US; PRCP, TMAX)
# Output : workspace.default.station_year_quality (station_id, year, prcp_days, tmax_days,
#          prcp_completeness, tmax_completeness, usable)
# Assumptions:
#   - Growing season = 1 April to 30 September = 183 days.
#   - A day counts only if the value is not null and q_flag is null (passed NOAA QC).
#   - A station-year is usable when BOTH PRCP and TMAX completeness are >= MIN_COMPLETENESS.
#   - Usability is judged per station-year, not per station, because stations open and close.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
MIN_COMPLETENESS = 0.90
SEASON_DAYS = 183

d = (spark.table(f"{S}.ghcn_daily")
     .where("country_code = 'US' AND element IN ('PRCP','TMAX') AND q_flag IS NULL AND value IS NOT NULL")
     .where(F.month("date").between(4, 9)))

q = (d.groupBy("station_id", "year").agg(
        F.countDistinct(F.when(F.col("element") == "PRCP", F.col("date"))).alias("prcp_days"),
        F.countDistinct(F.when(F.col("element") == "TMAX", F.col("date"))).alias("tmax_days"))
     .withColumn("prcp_completeness", F.round(F.col("prcp_days") / SEASON_DAYS, 4))
     .withColumn("tmax_completeness", F.round(F.col("tmax_days") / SEASON_DAYS, 4))
     .withColumn("usable", (F.col("prcp_completeness") >= MIN_COMPLETENESS) &
                           (F.col("tmax_completeness") >= MIN_COMPLETENESS)))

(q.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{S}.station_year_quality"))

# COMMAND ----------

t = spark.table(f"{S}.station_year_quality")
t.groupBy("year").agg(F.count("*").alias("station_years"),
                      F.sum(F.col("usable").cast("int")).alias("usable")).orderBy("year").show(30)
assert t.where("prcp_days > 183 OR tmax_days > 183").count() == 0, "more days than the season has"

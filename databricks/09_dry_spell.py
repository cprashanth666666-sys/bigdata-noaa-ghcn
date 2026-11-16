# Databricks notebook source
# Story 3.3: longest dry spell per county-year (Gold).
#
# Inputs : county_year_station (nearest usable station per county-year), ghcn_daily
# Output : workspace.default.county_year_dry_spell
#            county_fips, year, station_id, distance_km, longest_dry_spell_days
# Assumptions:
#   - Dry day = PRCP < 1 mm (raw value < 10 tenths of mm). Season = 1 April to 30 September.
#   - Same station rule as notebook 08: nearest usable station, only if within MAX_KM = 30 km.
#   - A day with a missing value or QC flag is NOT dry; it breaks the run. This can only shorten a spell
#     (conservative), never invent one.
#   - Runs are found with the gaps-and-islands trick: consecutive dry dates share (date number - row number).
#   - Kept as its own table, joined to notebook 08's output on (county_fips, year), so 08 need not be re-run.

# COMMAND ----------

from pyspark.sql import functions as F, Window

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
MAX_KM = 30.0
DRY_MM = 1.0

pairs = spark.table(f"{S}.county_year_station").where(F.col("distance_km") <= MAX_KM)
station_years = pairs.select("station_id", "year").distinct()

dry = (spark.table(f"{S}.ghcn_daily")
       .where("country_code = 'US' AND element = 'PRCP' AND q_flag IS NULL AND value IS NOT NULL")
       .where(F.month("date").between(4, 9))
       .join(F.broadcast(station_years), ["station_id", "year"])
       .where(F.col("value") < DRY_MM * 10)
       .select("station_id", "year", "date").distinct())

w = Window.partitionBy("station_id", "year").orderBy("date")
runs = (dry.withColumn("grp", F.datediff("date", F.lit("1970-01-01")) - F.row_number().over(w))
           .groupBy("station_id", "year", "grp").agg(F.count("*").alias("run_days"))
           .groupBy("station_id", "year").agg(F.max("run_days").alias("longest_dry_spell_days")))

# A station-year with no dry day has no run row; its longest spell is 0, not NULL.
out = (pairs.join(runs, ["station_id", "year"], "left")
       .withColumn("longest_dry_spell_days", F.coalesce("longest_dry_spell_days", F.lit(0)))
       .select("county_fips", "year", "station_id", "distance_km", "longest_dry_spell_days"))

(out.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{S}.county_year_dry_spell"))

# COMMAND ----------

t = spark.table(f"{S}.county_year_dry_spell")
print("county-years:", t.count(), "counties:", t.select("county_fips").distinct().count())
t.selectExpr("round(avg(longest_dry_spell_days),1) AS avg_days", "max(longest_dry_spell_days) AS max_days",
             "percentile_approx(longest_dry_spell_days, 0.5) AS median_days").show()
assert t.groupBy("county_fips", "year").count().where("count > 1").count() == 0, "duplicate county-year"
assert t.where("longest_dry_spell_days > 183 OR longest_dry_spell_days < 0").count() == 0, "impossible spell length"

# Second-method check (Definition of Done): recompute one station-year row by row in plain Python.
probe = t.where("longest_dry_spell_days > 0").limit(1).first()
rows = spark.sql(f"""
  SELECT date, value FROM {S}.ghcn_daily
  WHERE station_id = '{probe.station_id}' AND year = {probe.year} AND element = 'PRCP'
    AND q_flag IS NULL AND value IS NOT NULL AND month(date) BETWEEN 4 AND 9
  ORDER BY date""").collect()
best = cur = 0
prev = None
for r in rows:
    if r.value < 10:
        cur = cur + 1 if (cur > 0 and prev is not None and (r.date - prev).days == 1) else 1
    else:
        cur = 0
    prev = r.date
    best = max(best, cur)
assert best == probe.longest_dry_spell_days, f"mismatch {best} vs {probe.longest_dry_spell_days}"
print("second-method check passed for", probe.station_id, probe.year, best)

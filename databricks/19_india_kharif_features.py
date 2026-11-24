# Databricks notebook source
# India pilot, story IN-2.1: Kharif weather features per district and year (Gold).
#
# Inputs : imd_rain_daily, imd_temp_daily (16); in_district_cells, in_districts (18)
# Output : workspace.default.in_district_year_weather
#            shape_id, state, district, year, n_cells, season_prcp_mm, jun_jul_mm, aug_sep_mm, deficit_pct,
#            longest_dry_spell_days, onset_delay_days, max_3day_mm, heavy_rain_days, days_tmax_gt35, days_tmax_gt38
# Assumptions (constants below):
#   - Season = 1 June to 30 September (122 days), the IMD south-west monsoon season, for every district.
#     A per-state sowing window is design change A3 in docs/INDIA_EXPANSION_PLAN.md; not applied yet.
#   - District daily rain = mean over the 0.25 deg cells whose centre lies in the district (notebook 18).
#     A district-day is kept only if every one of the district's cells reported that day.
#   - Dry day = rain <= 2.5 mm, the RWBCIS term-sheet definition. Longest run of dry days inside the season.
#   - Monsoon onset = first day from 1 June whose 3-day rain total >= ONSET_MM (20 mm). Delay = days after
#     1 June; 122 if it never happens. A simplified agronomic sowing rule, not IMD's official onset date.
#   - Deficit = season rain vs the district's own 1990-2025 mean (in-sample normal), in percent.
#     IMD's official normal is the 1971-2020 mean; ours uses the years we hold.
#   - Heavy rain day = district rain >= 64.5 mm, IMD's "heavy rainfall" threshold.
#   - Temperature: each rain cell takes the 1.0 deg temperature cell that contains it; the district's daily
#     tmax is the mean over its distinct temperature cells that reported that day.

# COMMAND ----------

import numpy as np, pandas as pd
from pyspark.sql import functions as F, Window

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
DRY_MM, ONSET_MM, HEAVY_MM = 2.5, 20.0, 64.5
SEASON_DAYS = 122

cells = spark.table(f"{S}.in_district_cells").select("shape_id", "lat", "lon")
n_cells = cells.groupBy("shape_id").agg(F.count("*").alias("n_cells"))
rain = (spark.table(f"{S}.imd_rain_daily").where(F.month("date").between(6, 9))
        .join(F.broadcast(cells), ["lat", "lon"]))
daily = (rain.groupBy("shape_id", "year", "date").agg(F.avg("rain_mm").alias("rain_mm"), F.count("*").alias("n"))
         .join(F.broadcast(n_cells), "shape_id")
         .where("n = n_cells").drop("n"))

# COMMAND ----------

schema = ("shape_id string, year int, n_days int, season_prcp_mm double, jun_jul_mm double, aug_sep_mm double, "
          "longest_dry_spell_days int, onset_delay_days int, max_3day_mm double, heavy_rain_days int")


def season_stats(pdf: pd.DataFrame) -> pd.DataFrame:
    pdf = pdf.sort_values("date")
    r = pdf["rain_mm"].to_numpy()
    month = pd.to_datetime(pdf["date"]).dt.month.to_numpy()
    dry = r <= DRY_MM
    longest = run = 0
    for d in dry:                       # longest run of consecutive dry days
        run = run + 1 if d else 0
        longest = max(longest, run)
    three = np.convolve(r, np.ones(3), mode="valid") if len(r) >= 3 else np.array([r.sum()])
    onset = np.flatnonzero(three >= ONSET_MM)
    return pd.DataFrame([{
        "shape_id": pdf["shape_id"].iloc[0], "year": int(pdf["year"].iloc[0]), "n_days": len(r),
        "season_prcp_mm": float(r.sum()), "jun_jul_mm": float(r[month <= 7].sum()), "aug_sep_mm": float(r[month >= 8].sum()),
        "longest_dry_spell_days": int(longest), "onset_delay_days": int(onset[0]) if len(onset) else SEASON_DAYS,
        "max_3day_mm": float(three.max()), "heavy_rain_days": int((r >= HEAVY_MM).sum())}])


feat = daily.groupBy("shape_id", "year").applyInPandas(season_stats, schema).where(f"n_days = {SEASON_DAYS}")

# COMMAND ----------

# Temperature: map each 0.25 deg cell to its 1.0 deg cell (centres 7.5, 8.5, ... so cell k spans k-0.5 to k+0.5).
tcells = (cells.withColumn("tlat", F.floor(F.col("lat") - 7.0) + 7.5).withColumn("tlon", F.floor(F.col("lon") - 67.0) + 67.5)
          .select("shape_id", "tlat", "tlon").distinct())
temp = (spark.table(f"{S}.imd_temp_daily").where(F.month("date").between(6, 9) & F.col("tmax_c").isNotNull())
        .withColumnRenamed("lat", "tlat").withColumnRenamed("lon", "tlon")
        .join(F.broadcast(tcells), ["tlat", "tlon"])
        .groupBy("shape_id", "year", "date").agg(F.avg("tmax_c").alias("tmax_c"))
        .groupBy("shape_id", "year").agg(F.count("*").alias("t_days"),
                                         F.sum((F.col("tmax_c") > 35).cast("int")).alias("days_tmax_gt35"),
                                         F.sum((F.col("tmax_c") > 38).cast("int")).alias("days_tmax_gt38")))

d = spark.table(f"{S}.in_districts").select("shape_id", "state", "district")
out = (feat.join(temp, ["shape_id", "year"], "left").join(d, "shape_id").join(n_cells, "shape_id")
       .withColumn("normal_mm", F.avg("season_prcp_mm").over(Window.partitionBy("shape_id")))
       .withColumn("deficit_pct", F.round(100 * (F.col("season_prcp_mm") - F.col("normal_mm")) / F.col("normal_mm"), 1))
       .select("shape_id", "state", "district", "year", "n_cells", "season_prcp_mm", "jun_jul_mm", "aug_sep_mm",
               "deficit_pct", "longest_dry_spell_days", "onset_delay_days", "max_3day_mm", "heavy_rain_days",
               "t_days", "days_tmax_gt35", "days_tmax_gt38"))
out.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_district_year_weather")

# COMMAND ----------

# Checks
w = spark.table(f"{S}.in_district_year_weather")
print("district-years:", w.count(), "districts:", w.select("shape_id").distinct().count(),
      "years:", w.select("year").distinct().count())
assert w.groupBy("shape_id", "year").count().where("count > 1").count() == 0, "duplicate district-year"
assert w.where("abs(jun_jul_mm + aug_sep_mm - season_prcp_mm) > 0.01").count() == 0, "phases must add to the season"
assert w.where("longest_dry_spell_days < 0 OR longest_dry_spell_days > 122 OR onset_delay_days > 122").count() == 0

# Second method: all-India June-September rainfall by year, computed straight from the cell table (area
# weights ignored on both sides), vs the district table weighted by cells. Years 2002 and 2009 were IMD drought years.
cell_mean = (spark.table(f"{S}.imd_rain_daily").where(F.month("date").between(6, 9)).join(F.broadcast(cells.select("lat", "lon").distinct()), ["lat", "lon"])
             .groupBy("year", "lat", "lon").agg(F.sum("rain_mm").alias("s")).groupBy("year").agg(F.avg("s").alias("cells_mm")))
dist_mean = w.groupBy("year").agg((F.sum(F.col("season_prcp_mm") * F.col("n_cells")) / F.sum("n_cells")).alias("districts_mm"))
cmp = cell_mean.join(dist_mean, "year").withColumn("diff_pct", F.round(100 * (F.col("districts_mm") / F.col("cells_mm") - 1), 2)).orderBy("year")
cmp.show(40)
# Cells counted twice (nearest-cell districts) and incomplete district-days make the two differ slightly.
assert cmp.where("abs(diff_pct) > 2").count() == 0, "district aggregation drifts from the cell mean"
print("driest years (all-India, cell mean):")
cmp.orderBy("cells_mm").show(5)
display(w.groupBy("state").agg(F.countDistinct("shape_id").alias("districts"), F.round(F.avg("season_prcp_mm")).alias("mean_season_mm"),
                               F.round(F.avg("longest_dry_spell_days"), 1).alias("mean_dry_spell"),
                               F.round(F.avg("days_tmax_gt35"), 1).alias("mean_days_gt35")).orderBy("state"))

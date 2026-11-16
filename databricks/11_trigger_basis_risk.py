# Databricks notebook source
# Sprint 4, stories 5.1, 5.2, 5.3: score weather triggers against yield losses, quantify basis risk,
# and pick the best trigger per region.
#
# Inputs : county_year_weather_features (3.1, 3.2), county_year_dry_spell (3.3), county_yield_trend (4.1, 4.2)
# Outputs (workspace.default):
#   trigger_eval_county      one row per county, crop, index, pay_freq: hit / miss / false alarm counts and rates (5.1, 5.2)
#   trigger_eval_dist_band   same, pooled by crop, index, pay_freq and station-distance band (5.2)
#   best_trigger_region      one row per state and crop: the chosen trigger (5.3)
#   trigger_county_year      row level: county, crop, year, index, pay_freq, threshold, trig, is_loss (used by 13)
#
# Definitions
#   Trigger   pays in a year when the weather index is among the worst PAY_FREQ share of that county's years.
#             "Worst" = lowest rainfall, or most heat days, or longest dry spell (sign in INDEXES).
#   Hit       trigger pays AND the county-crop had a loss (yield < 85% of trend, notebook 10).
#   Miss      loss year with NO payout. Basis risk = miss rate = miss / loss years.
#   False alarm  payout in a year with no loss. False-alarm rate = false alarm / non-loss years.
# Assumptions
#   - Thresholds are each county's own percentiles over ALL its years (in-sample). That flatters the
#     result: the trigger has seen the years it is tested on. Out-of-sample testing is a Sprint 6 hardening item.
#   - Ties: heat-day counts are often 0 in many years, which can make a percentile threshold fire in far more
#     years than PAY_FREQ. County-triggers whose actual trigger rate exceeds MAX_TRIGGER_RATE are dropped.
#   - A county-crop-index needs >= MIN_YEARS matched years (weather and yield) to be scored.
#   - Region = state. Best trigger = lowest pooled miss rate among triggers whose pooled false-alarm rate is
#     <= FA_CAP and that cover >= MIN_REGION_LOSSES loss years. Ties go to the lower false-alarm rate.
#   - Payout size is ignored here; a trigger either pays or it does not. Pricing is Sprint 5.

# COMMAND ----------

import numpy as np
from functools import reduce
from pyspark.sql import functions as F, Window

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"

PAY_FREQS = [0.30, 0.25, 0.20, 0.15, 0.10]          # share of years the trigger pays
QUANTILES = [round(1 - p, 2) for p in PAY_FREQS]     # matching percentile of the "stress" index
MIN_YEARS = 12
MAX_TRIGGER_RATE = 0.40
FA_CAP = 0.25
MIN_REGION_LOSSES = 10
BANDS = [(0, 10, "0-10 km"), (10, 20, "10-20 km"), (20, 30.0001, "20-30 km")]

# name: (column, table, sign). sign -1 = low value is bad (rain); +1 = high value is bad (heat, dry spell).
INDEXES = {
    "season_prcp_low":  ("season_prcp_mm",         "county_year_weather_features", -1),
    "min30_prcp_low":   ("min_30d_prcp_mm",        "county_year_weather_features", -1),
    "heat_gt30_high":   ("days_tmax_gt30",         "county_year_weather_features", 1),
    "heat_gt35_high":   ("days_tmax_gt35",         "county_year_weather_features", 1),
    "dry_spell_long":   ("longest_dry_spell_days", "county_year_dry_spell",        1),
}

# COMMAND ----------

# Long format: one row per county, year, index, with stress = sign x value (bigger = worse).
def index_rows(name, col, table, sign):
    return (spark.table(f"{S}.{table}")
            .where(F.col(col).isNotNull())
            .select("county_fips", "year", "distance_km",
                    F.lit(name).alias("index_name"), (F.col(col) * sign).alias("stress")))

long_idx = reduce(lambda a, b: a.unionByName(b), [index_rows(n, *v) for n, v in INDEXES.items()])

# Each county's own thresholds at every pay frequency.
q_sql = "percentile(stress, array(" + ",".join(str(q) for q in QUANTILES) + "))"
thr = (long_idx.groupBy("county_fips", "index_name").agg(F.expr(q_sql).alias("q"))
       .select("county_fips", "index_name", F.posexplode("q").alias("pos", "threshold"))
       .withColumn("pay_freq", F.element_at(F.array(*[F.lit(p) for p in PAY_FREQS]), F.col("pos") + 1))
       .drop("pos"))

losses = spark.table(f"{S}.county_yield_trend").select("county_fips", "crop", "year", "is_loss")

rows = (long_idx.join(thr, ["county_fips", "index_name"])
        .join(losses, ["county_fips", "year"])
        .withColumn("trig", F.col("stress") >= F.col("threshold"))
        .withColumn("hit", (F.col("trig") & F.col("is_loss")).cast("int"))
        .withColumn("miss", ((~F.col("trig")) & F.col("is_loss")).cast("int"))
        .withColumn("false_alarm", (F.col("trig") & (~F.col("is_loss"))).cast("int"))
        .withColumn("loss", F.col("is_loss").cast("int"))
        .withColumn("trig_i", F.col("trig").cast("int")))

# Row-level result, one row per county, crop, year, index, pay_freq. Notebook 13 prices from it.
(rows.select("county_fips", "crop", "year", "index_name", "pay_freq", "distance_km",
             "stress", "threshold", "trig", "is_loss")
     .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
     .saveAsTable(f"{S}.trigger_county_year"))

def rates(df):
    return (df.withColumn("trigger_rate", F.round(F.col("n_trig") / F.col("n_years"), 4))
              .withColumn("miss_rate", F.round(F.col("miss") / F.col("n_loss"), 4))
              .withColumn("false_alarm_rate", F.round(F.col("false_alarm") / (F.col("n_years") - F.col("n_loss")), 4)))

def counts():
    return [F.count("*").alias("n_years"), F.sum("loss").alias("n_loss"), F.sum("trig_i").alias("n_trig"),
            F.sum("hit").alias("hit"), F.sum("miss").alias("miss"), F.sum("false_alarm").alias("false_alarm")]

# COMMAND ----------

# 5.1 / 5.2: confusion counts and basis risk per county.
county = (rates(rows.groupBy("county_fips", "crop", "index_name", "pay_freq").agg(*counts()))
          .where((F.col("n_years") >= MIN_YEARS) & (F.col("n_loss") > 0)
                 & (F.col("trigger_rate") <= MAX_TRIGGER_RATE) & (F.col("n_years") > F.col("n_loss"))))
(county.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{S}.trigger_eval_county"))

# 5.2: basis risk by station-distance band, restricted to the county-triggers that passed the screen above.
band_expr = F.when(F.col("distance_km") < 10, BANDS[0][2]).when(F.col("distance_km") < 20, BANDS[1][2]).otherwise(BANDS[2][2])
ok = spark.table(f"{S}.trigger_eval_county").select("county_fips", "crop", "index_name", "pay_freq")
band = (rates(rows.join(ok, ["county_fips", "crop", "index_name", "pay_freq"])
              .withColumn("dist_band", band_expr)
              .groupBy("crop", "index_name", "pay_freq", "dist_band").agg(*counts()))
        .where(F.col("n_loss") > 0))
(band.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{S}.trigger_eval_dist_band"))

# COMMAND ----------

# 5.3: best trigger per region (state x crop), pooled over its counties.
c = spark.table(f"{S}.trigger_eval_county").withColumn("state_fips", F.substring("county_fips", 1, 2))
pooled = (rates(c.groupBy("state_fips", "crop", "index_name", "pay_freq").agg(
                F.countDistinct("county_fips").alias("counties"),
                F.sum("n_years").alias("n_years"), F.sum("n_loss").alias("n_loss"), F.sum("n_trig").alias("n_trig"),
                F.sum("hit").alias("hit"), F.sum("miss").alias("miss"), F.sum("false_alarm").alias("false_alarm")))
          # A random trigger paying at the same rate would miss (1 - trigger_rate) of losses; lift shows the skill over that.
          .withColumn("naive_miss_rate", F.round(1 - F.col("trigger_rate"), 4))
          .withColumn("miss_rate_lift", F.round(F.col("naive_miss_rate") - F.col("miss_rate"), 4)))

w = Window.partitionBy("state_fips", "crop").orderBy("miss_rate", "false_alarm_rate", "pay_freq")
best = (pooled.where((F.col("false_alarm_rate") <= FA_CAP) & (F.col("n_loss") >= MIN_REGION_LOSSES))
        .withColumn("rank", F.row_number().over(w)).where("rank = 1").drop("rank"))
(best.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{S}.best_trigger_region"))

# COMMAND ----------

# Checks and a readable summary.
ce = spark.table(f"{S}.trigger_eval_county")
print("county-trigger rows:", ce.count(), "counties:", ce.select("county_fips").distinct().count())
assert ce.where("hit + miss <> n_loss").count() == 0, "hit + miss must equal loss years"
assert ce.where("hit + false_alarm <> n_trig").count() == 0, "hit + false alarm must equal trigger years"
assert ce.groupBy("county_fips", "crop", "index_name", "pay_freq").count().where("count > 1").count() == 0, "duplicates"

print("Basis risk (pooled miss rate) by index and pay frequency, all regions:")
(rates(ce.groupBy("crop", "index_name", "pay_freq").agg(*counts())).orderBy("crop", "index_name", "pay_freq")
   .select("crop", "index_name", "pay_freq", "n_loss", "trigger_rate", "miss_rate", "false_alarm_rate").show(60))
print("Basis risk by distance band:")
spark.table(f"{S}.trigger_eval_dist_band").where("pay_freq = 0.20").orderBy("crop", "index_name", "dist_band") \
     .select("crop", "index_name", "dist_band", "n_loss", "miss_rate", "false_alarm_rate").show(60)
print("Chosen trigger per region:")
spark.table(f"{S}.best_trigger_region").orderBy("crop", "state_fips") \
     .select("state_fips", "crop", "index_name", "pay_freq", "counties", "n_loss", "miss_rate",
             "false_alarm_rate", "naive_miss_rate", "miss_rate_lift").show(20, truncate=False)
missing = (spark.table(f"{S}.county_yield_trend").withColumn("state_fips", F.substring("county_fips", 1, 2))
           .select("state_fips", "crop").distinct()
           .join(spark.table(f"{S}.best_trigger_region").select("state_fips", "crop"), ["state_fips", "crop"], "left_anti"))
print("Regions with NO trigger meeting the false-alarm cap and loss-year minimum:", missing.count())
missing.show()

# COMMAND ----------

# Second-method check (Definition of Done): rebuild one county-trigger in plain numpy/Python and compare.
probe = ce.where("n_loss >= 2").limit(1).first()
name = probe.index_name
col, table, sign = INDEXES[name]
vals = {r.year: r[col] for r in spark.table(f"{S}.{table}").where(
        f"county_fips = '{probe.county_fips}' AND {col} IS NOT NULL").collect()}
loss = {r.year: r.is_loss for r in spark.table(f"{S}.county_yield_trend").where(
        f"county_fips = '{probe.county_fips}' AND crop = '{probe.crop}'").collect()}
stress = {y: sign * v for y, v in vals.items()}
thr_py = float(np.percentile(list(stress.values()), 100 * (1 - probe.pay_freq)))   # linear interpolation, like Spark
yrs = [y for y in stress if y in loss]
hit = sum(stress[y] >= thr_py and loss[y] for y in yrs)
miss = sum(stress[y] < thr_py and loss[y] for y in yrs)
fa = sum(stress[y] >= thr_py and not loss[y] for y in yrs)
assert (hit, miss, fa) == (probe.hit, probe.miss, probe.false_alarm), \
    f"mismatch {(hit, miss, fa)} vs {(probe.hit, probe.miss, probe.false_alarm)} for {probe.county_fips} {name}"
print("second-method check passed:", probe.county_fips, probe.crop, name, probe.pay_freq, (hit, miss, fa))

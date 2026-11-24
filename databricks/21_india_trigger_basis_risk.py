# Databricks notebook source
# India pilot, stories IN-3.1 and IN-3.2: score RWBCIS-style weather triggers against district Kharif
# yield losses, measure basis risk, pick the best trigger per state and crop, and relate basis risk to
# district size. Same method as the US notebook 11, so results are comparable.
#
# Inputs : in_district_year_weather (19), in_district_yield_trend (20), in_districts (18)
# Outputs (workspace.default):
#   in_trigger_district_year   row level: district, crop, year, loss_def, index, pay_freq, stress, threshold, trig, is_loss
#   in_trigger_eval_district   hit / miss / false-alarm counts and rates per district, crop, loss_def, index, pay_freq
#   in_best_trigger_state      chosen trigger per state, crop and loss_def
#   in_trigger_eval_size       pooled rates by district area band and by cells-per-district band (IN-3.2)
# Definitions (as notebook 11)
#   Trigger pays when the district's stress index is among its worst PAY_FREQ share of years (own percentiles).
#   Miss = loss year with no payout; basis risk = miss rate. False alarm = payout in a non-loss year.
#   loss_def 'trend85' = yield < 85% of trend; 'pmfby80' = yield < 80% of the best-5-of-7 average.
# Assumptions
#   - Thresholds are in-sample percentiles over all of a district's years (optimistic, as in the US build).
#   - District-trigger kept if >= MIN_YEARS matched years, >= 1 loss year and actual trigger rate <= 0.40
#     (heat-day counts are often 0, so ties can make a percentile fire far too often).
#   - Best trigger per state = lowest pooled miss rate with pooled false-alarm rate <= FA_CAP and
#     >= MIN_REGION_LOSSES loss years; ties go to the lower false-alarm rate.
#   - RAINFED_STATES are the focus states from the plan (design change A6); results are also shown for them alone.

# COMMAND ----------

import numpy as np
from functools import reduce
from pyspark.sql import functions as F, Window

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
PAY_FREQS = [0.30, 0.25, 0.20, 0.15, 0.10]
QUANTILES = [round(1 - p, 2) for p in PAY_FREQS]
MIN_YEARS, MAX_TRIGGER_RATE, FA_CAP, MIN_REGION_LOSSES = 12, 0.40, 0.25, 10
# Matched on state_key (ASCII), because boundary names carry diacritics ("Mahārāshtra").
RAINFED_STATES = ["maharashtra", "madhyapradesh", "rajasthan", "gujarat", "karnataka", "telangana"]

# name: (column, sign). sign -1 = low is bad (deficit rain); +1 = high is bad.
INDEXES = {
    "season_prcp_low":  ("season_prcp_mm", -1),
    "jun_jul_low":      ("jun_jul_mm", -1),
    "aug_sep_low":      ("aug_sep_mm", -1),
    "dry_spell_long":   ("longest_dry_spell_days", 1),
    "onset_late":       ("onset_delay_days", 1),
    "excess_3day_high": ("max_3day_mm", 1),
    "heat_gt35_high":   ("days_tmax_gt35", 1),
}

# COMMAND ----------

wx = spark.table(f"{S}.in_district_year_weather")
long_idx = reduce(lambda a, b: a.unionByName(b), [
    wx.where(F.col(c).isNotNull()).select("shape_id", "year", F.lit(n).alias("index_name"), (F.col(c) * s).alias("stress"))
    for n, (c, s) in INDEXES.items()])

q_sql = "percentile(stress, array(" + ",".join(str(q) for q in QUANTILES) + "))"
thr = (long_idx.groupBy("shape_id", "index_name").agg(F.expr(q_sql).alias("q"))
       .select("shape_id", "index_name", F.posexplode("q").alias("pos", "threshold"))
       .withColumn("pay_freq", F.element_at(F.array(*[F.lit(p) for p in PAY_FREQS]), F.col("pos") + 1)).drop("pos"))

yt = spark.table(f"{S}.in_district_yield_trend").where("trend_yield > 0")
losses = (yt.select("shape_id", "crop", "year", F.lit("trend85").alias("loss_def"), "is_loss")
          .unionByName(yt.where("is_loss_pmfby80 IS NOT NULL")
                       .select("shape_id", "crop", "year", F.lit("pmfby80").alias("loss_def"), F.col("is_loss_pmfby80").alias("is_loss"))))

rows = (long_idx.join(thr, ["shape_id", "index_name"]).join(losses, ["shape_id", "year"])
        .withColumn("trig", F.col("stress") >= F.col("threshold")))
(rows.select("shape_id", "crop", "year", "loss_def", "index_name", "pay_freq", "stress", "threshold", "trig", "is_loss")
     .write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_trigger_district_year"))

CNT = ("n_years", "n_loss", "n_trig", "hit", "miss", "false_alarm")
counts = [F.count("*").alias("n_years"), F.sum("loss").alias("n_loss"), F.sum("trig_i").alias("n_trig"),
          F.sum("hit").alias("hit"), F.sum("miss").alias("miss"), F.sum("false_alarm").alias("false_alarm")]
pooled = [F.sum(c).alias(c) for c in CNT]


def rates(df):
    # try_divide: a group with no loss (or no non-loss) years gets NULL instead of a divide-by-zero error.
    return (df.withColumn("trigger_rate", F.round(F.expr("try_divide(n_trig, n_years)"), 4))
              .withColumn("miss_rate", F.round(F.expr("try_divide(miss, n_loss)"), 4))
              .withColumn("false_alarm_rate", F.round(F.expr("try_divide(false_alarm, n_years - n_loss)"), 4)))

# COMMAND ----------

# IN-3.1: per district, then the best trigger per state.
g = ["shape_id", "crop", "loss_def", "index_name", "pay_freq"]
dist = (rates(spark.table(f"{S}.in_trigger_district_year").withColumn("loss", F.col("is_loss").cast("int"))
              .withColumn("trig_i", F.col("trig").cast("int"))
              .withColumn("hit", (F.col("trig") & F.col("is_loss")).cast("int"))
              .withColumn("miss", ((~F.col("trig")) & F.col("is_loss")).cast("int"))
              .withColumn("false_alarm", (F.col("trig") & (~F.col("is_loss"))).cast("int"))
              .groupBy(*g).agg(*counts))
        .where((F.col("n_years") >= MIN_YEARS) & (F.col("n_loss") > 0) & (F.col("n_years") > F.col("n_loss"))
               & (F.col("trigger_rate") <= MAX_TRIGGER_RATE))
        .join(spark.table(f"{S}.in_districts").select("shape_id", "state", "state_key", "area_km2", "n_cells"), "shape_id"))
dist.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_trigger_eval_district")

de = spark.table(f"{S}.in_trigger_eval_district")
st = (rates(de.groupBy("state", "crop", "loss_def", "index_name", "pay_freq")
            .agg(F.countDistinct("shape_id").alias("districts"), *pooled))
      .withColumn("naive_miss_rate", F.round(1 - F.col("trigger_rate"), 4))
      .withColumn("miss_rate_lift", F.round(F.col("naive_miss_rate") - F.col("miss_rate"), 4)))
w = Window.partitionBy("state", "crop", "loss_def").orderBy("miss_rate", "false_alarm_rate", "pay_freq")
best = (st.where((F.col("false_alarm_rate") <= FA_CAP) & (F.col("n_loss") >= MIN_REGION_LOSSES))
        .withColumn("rank", F.row_number().over(w)).where("rank = 1").drop("rank")
        .join(de.select("state", "state_key").distinct(), "state")
        .withColumn("rainfed_focus", F.col("state_key").isin(RAINFED_STATES)))
best.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_best_trigger_state")

# COMMAND ----------

# IN-3.2: basis risk vs district size, for every district-trigger that passed the screen.
area_band = (F.when(F.col("area_km2") < 2000, "a <2,000 km2").when(F.col("area_km2") < 5000, "b 2,000-5,000")
              .when(F.col("area_km2") < 10000, "c 5,000-10,000").otherwise("d >=10,000"))
cell_band = (F.when(F.col("n_cells") <= 2, "a 1-2 cells").when(F.col("n_cells") <= 5, "b 3-5")
              .when(F.col("n_cells") <= 10, "c 6-10").otherwise("d >10"))
size = (rates(de.withColumn("area_band", area_band).withColumn("cell_band", cell_band)
              .groupBy("loss_def", "crop", "index_name", "pay_freq", "area_band", "cell_band")
              .agg(F.countDistinct("shape_id").alias("districts"), *pooled)))
size.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_trigger_eval_size")

# COMMAND ----------

# Checks and summary
assert de.where("hit + miss <> n_loss OR hit + false_alarm <> n_trig").count() == 0, "confusion counts do not add up"
assert de.groupBy(*g).count().where("count > 1").count() == 0, "duplicates"
print("district-trigger rows:", de.count(), "districts:", de.select("shape_id").distinct().count())

print("Basis risk by index at pay_freq 0.20, trend85 loss rule, all crops pooled:")
rates(de.where("pay_freq = 0.20 AND loss_def = 'trend85'").groupBy("index_name").agg(*pooled)) \
    .select("index_name", "n_loss", "trigger_rate", "miss_rate", "false_alarm_rate").orderBy("miss_rate").show()
print("Same, rain-fed focus states only:")
rates(de.where("pay_freq = 0.20 AND loss_def = 'trend85'").where(F.col("state_key").isin(RAINFED_STATES))
      .groupBy("index_name").agg(*pooled)).select("index_name", "n_loss", "miss_rate", "false_alarm_rate").orderBy("miss_rate").show()
print("Chosen trigger per state and crop (trend85):")
spark.table(f"{S}.in_best_trigger_state").where("loss_def = 'trend85'").orderBy("crop", "state") \
    .select("state", "crop", "index_name", "pay_freq", "districts", "n_loss", "miss_rate", "false_alarm_rate",
            "naive_miss_rate", "miss_rate_lift").show(200, truncate=False)
print("Basis risk by district area band (season_prcp_low, pay_freq 0.20, trend85):")
rates(spark.table(f"{S}.in_trigger_eval_size").where("index_name = 'season_prcp_low' AND pay_freq = 0.20 AND loss_def = 'trend85'")
      .groupBy("area_band").agg(F.sum("districts").alias("districts"), *pooled)).orderBy("area_band") \
    .select("area_band", "districts", "n_loss", "miss_rate", "false_alarm_rate").show()

# COMMAND ----------

# Second-method check: rebuild one district-trigger in plain numpy/Python and compare the counts.
p = de.where("n_loss >= 2 AND loss_def = 'trend85'").orderBy("shape_id", "crop", "index_name", "pay_freq").limit(1).first()
col, sign = INDEXES[p.index_name]
vals = {r.year: sign * r[col] for r in wx.where(f"shape_id = '{p.shape_id}' AND {col} IS NOT NULL").collect()}
loss = {r.year: r.is_loss for r in yt.where(f"shape_id = '{p.shape_id}' AND crop = '{p.crop}'").collect()}
thr_py = float(np.percentile(list(vals.values()), 100 * (1 - p.pay_freq)))
yrs = [y for y in vals if y in loss]
got = (sum(vals[y] >= thr_py and loss[y] for y in yrs), sum(vals[y] < thr_py and loss[y] for y in yrs),
       sum(vals[y] >= thr_py and not loss[y] for y in yrs))
assert got == (p.hit, p.miss, p.false_alarm), (got, p)
print("second-method check passed:", p.shape_id, p.crop, p.index_name, p.pay_freq, got)

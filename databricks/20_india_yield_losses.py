# Databricks notebook source
# India pilot, story IN-2.2: detrend district Kharif yields and flag loss years two ways (Gold).
#
# Inputs : in_district_yields (17), in_district_xwalk, in_districts (18)
# Output : workspace.default.in_district_yield_trend
#            shape_id, state, district, crop, year, area_ha, yield_value, trend_yield, pct_of_trend, is_loss,
#            pmfby_avg_yield, is_loss_pmfby70, is_loss_pmfby80, is_loss_pmfby90
# Definitions
#   is_loss            yield < LOSS_RATIO (0.85) x OLS trend, the rule used for the US counties (notebook 10).
#   pmfby_avg_yield    PMFBY: average of the best 5 of the previous 7 years' yields (Operational Guidelines).
#   is_loss_pmfbyXX    yield < pmfby_avg_yield x indemnity level XX% (PMFBY offers 70, 80 and 90).
#                      Needs all 7 previous years, so the first 7 years of each series have no PMFBY flag.
# Assumptions
#   - Only DES districts matched to a boundary district (in_district_xwalk.match <> 'none') are kept; the
#     mapping is one-to-one (checked 24 Nov 2026), so yields are not mixed across districts.
#   - Trend = OLS of yield on year per district and crop, on all years (in-sample), >= MIN_YEARS = 15 years.
#   - The PMFBY rule uses actual past yields; the scheme also uses crop-cutting experiments and, since
#     2023, YES-TECH estimates. District averages here stand in for the insurance-unit yields it uses.

# COMMAND ----------

import numpy as np, pandas as pd
from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
MIN_YEARS = 15
LOSS_RATIO = 0.85
LEVELS = (70, 80, 90)

xw = spark.table(f"{S}.in_district_xwalk").where("match <> 'none'").select("state_key", "district_key", "shape_id")
base = (spark.table(f"{S}.in_district_yields").join(xw, ["state_key", "district_key"])
        .join(spark.table(f"{S}.in_districts").select("shape_id", F.col("state").alias("b_state"), F.col("district").alias("b_district")), "shape_id")
        .select("shape_id", F.col("b_state").alias("state"), F.col("b_district").alias("district"), "crop", "year", "area_ha", "yield_value"))

schema = ("shape_id string, state string, district string, crop string, year int, area_ha double, yield_value double, "
          "trend_yield double, pct_of_trend double, is_loss boolean, pmfby_avg_yield double, "
          + ", ".join(f"is_loss_pmfby{l} boolean" for l in LEVELS))


def losses(pdf: pd.DataFrame) -> pd.DataFrame:
    pdf = pdf.sort_values("year").reset_index(drop=True)
    if len(pdf) < MIN_YEARS:
        return pd.DataFrame(columns=[c.split()[0] for c in schema.split(", ")])
    x, y = pdf["year"].to_numpy(float), pdf["yield_value"].to_numpy(float)
    slope, icpt = np.polyfit(x, y, 1)
    pdf["trend_yield"] = icpt + slope * x
    pdf["pct_of_trend"] = y / pdf["trend_yield"]
    pdf["is_loss"] = y < LOSS_RATIO * pdf["trend_yield"]
    by_year = dict(zip(pdf["year"], y))
    avg = []
    for yr in pdf["year"]:
        prev = [by_year.get(yr - k) for k in range(1, 8)]
        avg.append(np.mean(sorted(prev)[-5:]) if all(v is not None for v in prev) else np.nan)
    avg = np.array(avg, dtype=float)
    pdf["pmfby_avg_yield"] = avg
    for l in LEVELS:
        flag = pd.Series(y < avg * l / 100, dtype="boolean")
        flag[np.isnan(avg)] = pd.NA
        pdf[f"is_loss_pmfby{l}"] = flag
    return pdf[[c.split()[0] for c in schema.split(", ")]]


out = base.groupBy("shape_id", "crop").applyInPandas(losses, schema)
out.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_district_yield_trend")

# COMMAND ----------

# Checks
t = spark.table(f"{S}.in_district_yield_trend")
print("rows:", t.count(), "district-crops:", t.select("shape_id", "crop").distinct().count())
assert t.groupBy("shape_id", "crop", "year").count().where("count > 1").count() == 0, "duplicate district-crop-year"
bad = t.groupBy("shape_id", "crop").agg(F.sum(F.col("yield_value") - F.col("trend_yield")).alias("s")).where(F.abs("s") > 0.01).count()
assert bad == 0, f"{bad} district-crops whose OLS residuals do not sum to ~0"
neg = t.where("trend_yield <= 0").count()
print("district-crop-years with a non-positive trend (steep decline; loss flag meaningless):", neg)

summary = t.groupBy("crop").agg(
    F.countDistinct("shape_id").alias("districts"), F.count("*").alias("district_years"),
    F.round(F.avg(F.col("is_loss").cast("int")), 3).alias("loss_share_trend85"),
    *[F.round(F.avg(F.col(f"is_loss_pmfby{l}").cast("int")), 3).alias(f"loss_share_pmfby{l}") for l in LEVELS]).orderBy("crop")
summary.show()
print("loss share by year, all crops (2002, 2009, 2014 and 2015 were all-India monsoon deficit years):")
t.groupBy("year").agg(F.round(F.avg(F.col("is_loss").cast("int")), 3).alias("trend85"),
                      F.round(F.avg(F.col("is_loss_pmfby80").cast("int")), 3).alias("pmfby80")).orderBy("year").show(30)

# Second method: rebuild one district-crop's PMFBY average and trend flag in plain Python.
p = t.where("pmfby_avg_yield IS NOT NULL").orderBy("shape_id", "crop", "year").limit(1).first()
hist = {r.year: r.yield_value for r in spark.table(f"{S}.in_district_yield_trend")
        .where(f"shape_id = '{p.shape_id}' AND crop = '{p.crop}'").collect()}
avg_py = sum(sorted(hist[p.year - k] for k in range(1, 8))[-5:]) / 5
assert abs(avg_py - p.pmfby_avg_yield) < 1e-9, (avg_py, p.pmfby_avg_yield)
yrs = sorted(hist)
b, a = np.polyfit(yrs, [hist[y] for y in yrs], 1)
assert abs(a + b * p.year - p.trend_yield) < 1e-6
print("second-method check passed:", p.shape_id, p.crop, p.year, round(avg_py, 3))

# Databricks notebook source
# Pipeline validation: one report of every module's output table, run last in the job.
# It does not rebuild anything; it reads each table and checks the facts the next module relies on.
#
# Inputs : all tables written by notebooks 01 to 14
# Output : workspace.default.pipeline_validation (module, table_name, check_name, value, passed, checked_at)
#          and a notebook exit value (JSON) with the pass/fail count, so a job run shows the verdict.
# Assumptions:
#   - A check fails the notebook only after ALL checks have run, so one bad table does not hide the others.
#   - Thresholds below are sanity bounds, not targets: e.g. a usable-station share outside 1% to 99% means a filter bug.

# COMMAND ----------

import json
from datetime import datetime, timezone
from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
results = []


def check(module, table, name, value, passed):
    results.append((module, table, name, str(value), bool(passed)))
    print(f"[{'PASS' if passed else 'FAIL'}] {module:<4} {table:<30} {name}: {value}")


def exists(t):
    return spark.catalog.tableExists(f"{S}.{t}")


def rows(t):
    return spark.table(f"{S}.{t}").count()


def one(sql):
    return spark.sql(sql).first()[0]

# COMMAND ----------

# Every expected table, the module that writes it, and the minimum sensible row count.
EXPECTED = [
    ("01", "ghcn_daily", 100_000_000), ("01", "ghcn_stations", 100_000),
    ("02", "nass_crops_raw", 10_000_000), ("02", "nass_county_yields", 1_000_000), ("02", "us_counties", 3_000),
    ("04", "dq_report", 1), ("05", "county_station_links", 1_000),
    ("06", "station_year_quality", 1_000), ("07", "county_year_station", 1_000), ("07", "county_coverage_gaps", 100),
    ("08", "county_year_weather_features", 1_000), ("09", "county_year_dry_spell", 1_000),
    ("10", "county_yield_trend", 1_000),
    ("11", "trigger_eval_county", 100), ("11", "trigger_eval_dist_band", 1), ("11", "best_trigger_region", 1),
    ("11", "trigger_county_year", 1_000),
    ("12", "station_pair_corr", 100), ("12", "corr_distance_curve", 5),
    ("13", "premium_county", 10), ("13", "portfolio_year", 10), ("13", "portfolio_summary", 1),
    ("14", "v_county_basis_risk", 10), ("14", "v_county_premium", 10), ("14", "v_trigger_performance", 1),
    ("14", "v_basis_risk_by_distance", 1), ("14", "v_corr_distance", 1), ("14", "v_portfolio_year", 1),
    ("14", "v_portfolio_summary", 1), ("14", "v_coverage_gaps", 1),
]
present = set()
for m, t, min_rows in EXPECTED:
    if not exists(t):
        check(m, t, "exists", False, False)
        continue
    n = rows(t)
    present.add(t)
    check(m, t, f"rows >= {min_rows:,}", f"{n:,}", n >= min_rows)

# COMMAND ----------

# Content checks, each run only if its table exists.
if "ghcn_daily" in present:
    yrs = spark.sql(f"SELECT min(year), max(year) FROM {S}.ghcn_daily").first()
    check("03", "ghcn_daily", "history covers 2000 to 2025", f"{yrs[0]}-{yrs[1]}", yrs[0] <= 2000 and yrs[1] >= 2025)

if "station_year_quality" in present:
    share = one(f"SELECT avg(cast(usable AS INT)) FROM {S}.station_year_quality")
    check("06", "station_year_quality", "usable share between 1% and 99%", round(share, 3), 0.01 < share < 0.99)
    bad = one(f"SELECT count(*) FROM {S}.station_year_quality WHERE prcp_days > 183 OR tmax_days > 183")
    check("06", "station_year_quality", "no station-year above 183 season days", bad, bad == 0)

if "county_year_station" in present:
    d = one(f"SELECT count(*) FROM (SELECT county_fips, year FROM {S}.county_year_station GROUP BY 1, 2 HAVING count(*) > 1)")
    check("07", "county_year_station", "one station per county-year", d, d == 0)

if "county_year_weather_features" in present:
    r = spark.sql(f"""SELECT avg(season_prcp_mm), min(season_prcp_mm), max(days_tmax_gt30)
                      FROM {S}.county_year_weather_features""").first()
    # Corn Belt April-September rain is typically several hundred mm; an average outside 100-1500 mm is a unit bug.
    check("08", "county_year_weather_features", "avg season rain 100-1500 mm", round(r[0] or -1, 1), 100 < (r[0] or -1) < 1500)
    check("08", "county_year_weather_features", "no negative rain", r[1], (r[1] or 0) >= 0)
    check("08", "county_year_weather_features", "heat days <= 62", r[2], (r[2] or 0) <= 62)

if "county_year_dry_spell" in present:
    mx = one(f"SELECT max(longest_dry_spell_days) FROM {S}.county_year_dry_spell")
    check("09", "county_year_dry_spell", "longest spell <= 183 days", mx, mx is not None and mx <= 183)

if "county_yield_trend" in present:
    for crop in ("corn", "soybeans"):
        n = one(f"SELECT count(DISTINCT county_fips) FROM {S}.county_yield_trend WHERE crop = '{crop}'")
        check("10", "county_yield_trend", f"{crop} counties detrended", n, n > 0)
    ls = one(f"SELECT avg(cast(is_loss AS INT)) FROM {S}.county_yield_trend")
    # Below-85%-of-trend years should be uncommon but present; outside 1%-40% suggests the trend or series is wrong.
    check("10", "county_yield_trend", "loss share between 1% and 40%", round(ls, 3), 0.01 < ls < 0.40)
    y12 = one(f"SELECT avg(cast(is_loss AS INT)) FROM {S}.county_yield_trend WHERE crop = 'corn' AND year = 2012")
    check("10", "county_yield_trend", "2012 corn drought shows above-average losses", round(y12 or 0, 3), (y12 or 0) > ls)

if "trigger_eval_county" in present:
    bad = one(f"SELECT count(*) FROM {S}.trigger_eval_county WHERE hit + miss <> n_loss OR hit + false_alarm <> n_trig")
    check("11", "trigger_eval_county", "confusion counts add up", bad, bad == 0)

if "best_trigger_region" in present:
    n = rows("best_trigger_region")
    check("11", "best_trigger_region", "state-crop regions with a chosen trigger (of up to 10)", n, 1 <= n <= 10)

if "corr_distance_curve" in present:
    c = {r[0]: r[1] for r in spark.sql(f"SELECT dist_bin_km, median_corr_prcp FROM {S}.corr_distance_curve").collect()}
    check("12", "corr_distance_curve", "rain correlation falls with distance",
          f"{c[min(c)]} at {min(c)} km vs {c[max(c)]} at {max(c)} km", c[min(c)] > c[max(c)])

if "premium_county" in present:
    r = spark.sql(f"SELECT min(premium_rate), max(premium_rate) FROM {S}.premium_county").first()
    check("13", "premium_county", "premium rate in (0, 1)", f"{r[0]}-{r[1]}", r[0] is not None and 0 < r[0] and r[1] < 1)

# COMMAND ----------

now = datetime.now(timezone.utc)
df = spark.createDataFrame(results, "module STRING, table_name STRING, check_name STRING, value STRING, passed BOOLEAN") \
          .withColumn("checked_at", F.lit(now))
df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.pipeline_validation")

n_fail = sum(1 for r in results if not r[4])
summary = {"checks": len(results), "passed": len(results) - n_fail, "failed": n_fail,
           "failed_checks": [f"{r[0]} {r[1]}: {r[2]} = {r[3]}" for r in results if not r[4]],
           "all_checks": [f"{'PASS' if r[4] else 'FAIL'} {r[0]} {r[1]}: {r[2]} = {r[3]}" for r in results]}
print(json.dumps(summary, indent=2))
if n_fail:
    raise AssertionError(f"{n_fail} validation checks failed: {summary['failed_checks']}")
dbutils.notebook.exit(json.dumps(summary))

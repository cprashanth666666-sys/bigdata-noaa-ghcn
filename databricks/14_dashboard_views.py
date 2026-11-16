# Databricks notebook source
# Story 7.1: SQL views that feed the Databricks SQL (AI/BI) dashboard.
# The dashboard itself is assembled in the Databricks UI from these views; the layout is in docs/DASHBOARD.md.
#
# Inputs : Gold tables from notebooks 07 and 11 to 13, plus us_counties for map coordinates
# Outputs (views in workspace.default, one per dashboard dataset):
#   v_county_basis_risk      county point map: chosen trigger, miss rate, false-alarm rate, station distance
#   v_county_premium         county point map and table: premium rate and premium per acre
#   v_trigger_performance    bar chart: pooled miss and false-alarm rate per index and pay frequency
#   v_basis_risk_by_distance bar chart: miss rate by station-distance band
#   v_corr_distance          line chart: station-pair correlation against distance
#   v_portfolio_year         line/bar chart: payout, premium and loss ratio per year
#   v_portfolio_summary      counters: expected annual payout, worst year, worst-year loss ratio
#   v_coverage_gaps          county point map: counties without a usable station within 30 km
# Assumptions:
#   - Views, not tables: they always reflect the latest run of notebooks 07 to 13 and cost no storage.
#   - Map points use the county internal-point centroid (us_counties), the same point used for station distance.
#   - State names come from us_counties.state_alpha so the dashboard can filter by a readable state code.

# COMMAND ----------

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"

VIEWS = {
"v_county_basis_risk": f"""
  SELECT c.county_fips, u.county_name, u.state_alpha, u.latitude, u.longitude, c.crop,
         c.index_name, c.pay_freq, c.n_years, c.n_loss, c.miss_rate, c.false_alarm_rate,
         d.avg_distance_km
  FROM {S}.trigger_eval_county c
  JOIN {S}.best_trigger_region b
    ON substring(c.county_fips, 1, 2) = b.state_fips AND c.crop = b.crop
   AND c.index_name = b.index_name AND c.pay_freq = b.pay_freq
  JOIN {S}.us_counties u ON u.county_fips = c.county_fips
  LEFT JOIN (SELECT county_fips, crop, index_name, pay_freq, round(avg(distance_km), 1) AS avg_distance_km
             FROM {S}.trigger_county_year GROUP BY ALL) d
    ON d.county_fips = c.county_fips AND d.crop = c.crop AND d.index_name = c.index_name AND d.pay_freq = c.pay_freq""",

"v_county_premium": f"""
  SELECT p.county_fips, u.county_name, u.state_alpha, u.latitude, u.longitude, p.crop, p.index_name, p.pay_freq,
         p.payout_freq, p.premium_rate, p.sum_insured_latest, p.premium_per_acre_usd, p.shortfall_share_paid
  FROM {S}.premium_county p JOIN {S}.us_counties u ON u.county_fips = p.county_fips""",

"v_trigger_performance": f"""
  SELECT crop, index_name, pay_freq, count(*) AS counties, sum(n_loss) AS loss_years,
         round(sum(miss) / sum(n_loss), 4) AS miss_rate,
         round(sum(false_alarm) / sum(n_years - n_loss), 4) AS false_alarm_rate
  FROM {S}.trigger_eval_county GROUP BY crop, index_name, pay_freq""",

"v_basis_risk_by_distance": f"""
  SELECT crop, index_name, pay_freq, dist_band, n_loss, miss_rate, false_alarm_rate
  FROM {S}.trigger_eval_dist_band""",

"v_corr_distance": f"""
  SELECT dist_bin_km, pairs, median_corr_prcp, median_corr_heat FROM {S}.corr_distance_curve""",

"v_portfolio_year": f"""
  SELECT crop, year, counties, counties_paid, payout_usd, premium_usd, shortfall_usd, loss_ratio
  FROM {S}.portfolio_year""",

"v_portfolio_summary": f"""SELECT * FROM {S}.portfolio_summary""",

"v_coverage_gaps": f"""
  SELECT g.county_fips, u.county_name, u.state_alpha, u.latitude, u.longitude,
         g.years_total, g.years_covered_30km,
         round(g.years_covered_30km / g.years_total, 3) AS share_years_covered,
         g.nearest_usable_km_median
  FROM {S}.county_coverage_gaps g JOIN {S}.us_counties u ON u.county_fips = g.county_fips""",
}

for name, sql in VIEWS.items():
    spark.sql(f"CREATE OR REPLACE VIEW {S}.{name} AS {sql}")
    print("created", name)

# COMMAND ----------

# Checks: every view returns rows, and joins did not drop or duplicate rows against their base table.
for name in VIEWS:
    n = spark.table(f"{S}.{name}").count()
    print(f"{name}: {n} rows")
    assert n > 0, f"{name} is empty; run notebooks 07 to 13 first"

def same_count(view, base):
    a, b = spark.table(f"{S}.{view}").count(), spark.table(f"{S}.{base}").count()
    assert a == b, f"{view} has {a} rows but {base} has {b}; a county is missing from us_counties or duplicated"

same_count("v_county_premium", "premium_county")
same_count("v_coverage_gaps", "county_coverage_gaps")
# Every priced county should appear on the basis-risk map, since both use the chosen trigger per region.
a = spark.table(f"{S}.v_county_basis_risk").select("county_fips", "crop").distinct().count()
b = spark.table(f"{S}.premium_county").select("county_fips", "crop").distinct().count()
assert a == b, f"basis-risk map has {a} county-crops, premium table has {b}"
print("view checks passed")

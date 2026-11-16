# Databricks notebook source
# Sprint 5, story 5.4: how fast does weather similarity decay with distance?
# Spatial basis risk in one curve: a station far from the farm measures a different rainfall season.
#
# Inputs : ghcn_daily, ghcn_stations, station_year_quality (2.2)
# Outputs (workspace.default):
#   station_pair_corr        station_a, station_b, distance_km, n_years, corr_season_prcp, corr_heat_days
#   corr_distance_curve      dist_bin_km, pairs, median and mean correlation, per metric
# Assumptions:
#   - Stations: usable station-years only (>=90% growing-season PRCP and TMAX), in the Corn Belt states
#     IA, IL, IN, NE, MN (ghcn_stations.state).
#   - Metrics per station-year: April-September total PRCP (mm) and July-August days with TMAX > 30 C,
#     computed the same way as notebook 08.
#   - A pair is kept if the stations are <= MAX_KM apart and share >= MIN_COMMON_YEARS usable years.
#   - Correlation is Pearson across years. With ~20 years one pair's correlation is noisy; the curve uses the
#     median per 10 km bin, which is robust to that noise.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
STATES = ["IA", "IL", "IN", "NE", "MN"]
MAX_KM = 200.0
BIN_KM = 10
MIN_COMMON_YEARS = 12

stations = (spark.table(f"{S}.ghcn_stations").where(F.col("state").isin(STATES))
            .select("station_id", "latitude", "longitude"))
usable = (spark.table(f"{S}.station_year_quality").where("usable").select("station_id", "year")
          .join(stations.select("station_id"), "station_id"))

d = (spark.table(f"{S}.ghcn_daily")
     .where("country_code = 'US' AND element IN ('PRCP','TMAX') AND q_flag IS NULL AND value IS NOT NULL")
     .where(F.month("date").between(4, 9))
     .join(F.broadcast(usable), ["station_id", "year"]))

sy = (d.groupBy("station_id", "year").agg(
        F.sum(F.when(F.col("element") == "PRCP", F.col("value") / 10)).alias("season_prcp_mm"),
        F.sum(F.when((F.col("element") == "TMAX") & F.month("date").isin(7, 8) & (F.col("value") > 300), 1)
               .otherwise(0)).alias("heat_days")))
sy.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.tmp_station_year_metrics")
sy = spark.table(f"{S}.tmp_station_year_metrics")

# COMMAND ----------

def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = F.radians(lat1), F.radians(lat2)
    dphi, dlam = F.radians(lat2 - lat1), F.radians(lon2 - lon1)
    a = F.sin(dphi / 2) ** 2 + F.cos(p1) * F.cos(p2) * F.sin(dlam / 2) ** 2
    return 2 * 6371.0088 * F.asin(F.sqrt(a))

st = stations.join(sy.select("station_id").distinct(), "station_id")
a, b = st.alias("a"), st.alias("b")
pad_lat = MAX_KM / 111.0
pad_lon = MAX_KM / 75.0     # 1 degree of longitude is ~75-85 km at 40-49 N; 75 keeps the box wide enough
pairs = (a.join(F.broadcast(b),
            (F.col("a.station_id") < F.col("b.station_id"))
            & (F.abs(F.col("a.latitude") - F.col("b.latitude")) <= pad_lat)
            & (F.abs(F.col("a.longitude") - F.col("b.longitude")) <= pad_lon))
         .select(F.col("a.station_id").alias("station_a"), F.col("b.station_id").alias("station_b"),
                 haversine_km(F.col("a.latitude"), F.col("a.longitude"),
                              F.col("b.latitude"), F.col("b.longitude")).alias("distance_km"))
         .where(F.col("distance_km") <= MAX_KM))

ya = sy.select(F.col("station_id").alias("station_a"), "year",
               F.col("season_prcp_mm").alias("pa"), F.col("heat_days").alias("ha"))
yb = sy.select(F.col("station_id").alias("station_b"), "year",
               F.col("season_prcp_mm").alias("pb"), F.col("heat_days").alias("hb"))
corr = (pairs.join(ya, "station_a").join(yb, ["station_b", "year"])
        .groupBy("station_a", "station_b", "distance_km").agg(
            F.count("*").alias("n_years"),
            F.round(F.corr("pa", "pb"), 4).alias("corr_season_prcp"),
            F.round(F.corr("ha", "hb"), 4).alias("corr_heat_days"))
        .where(F.col("n_years") >= MIN_COMMON_YEARS))
(corr.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
     .saveAsTable(f"{S}.station_pair_corr"))

# COMMAND ----------

p = spark.table(f"{S}.station_pair_corr").withColumn(
        "dist_bin_km", (F.floor(F.col("distance_km") / BIN_KM) * BIN_KM).cast("int"))
curve = (p.groupBy("dist_bin_km").agg(
            F.count("*").alias("pairs"),
            F.round(F.expr("percentile(corr_season_prcp, 0.5)"), 3).alias("median_corr_prcp"),
            F.round(F.avg("corr_season_prcp"), 3).alias("mean_corr_prcp"),
            F.round(F.expr("percentile(corr_heat_days, 0.5)"), 3).alias("median_corr_heat"),
            F.round(F.avg("corr_heat_days"), 3).alias("mean_corr_heat"))
         .orderBy("dist_bin_km"))
(curve.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
      .saveAsTable(f"{S}.corr_distance_curve"))
spark.sql(f"DROP TABLE IF EXISTS {S}.tmp_station_year_metrics")

# COMMAND ----------

pc = spark.table(f"{S}.station_pair_corr")
print("pairs:", pc.count(), "stations:", pc.select("station_a").union(pc.select("station_b")).distinct().count())
spark.table(f"{S}.corr_distance_curve").orderBy("dist_bin_km").show(30)
assert pc.where("distance_km > %s OR station_a >= station_b" % MAX_KM).count() == 0, "bad pair"
assert pc.where("abs(corr_season_prcp) > 1.0001").count() == 0, "correlation out of range"
# Expect decay: rainfall correlation in the first bin should beat the last. A flat curve means a join bug.
c = {r.dist_bin_km: r.median_corr_prcp for r in spark.table(f"{S}.corr_distance_curve").collect()}
print("median rainfall correlation, nearest bin vs farthest bin:", c[min(c)], c[max(c)])
assert c[min(c)] > c[max(c)], "no decay of correlation with distance; check the pair join"

# Second-method check: one pair's correlation recomputed in plain Python.
r = pc.where("n_years >= 15").limit(1).first()
m = spark.sql(f"""
  SELECT a.year, a.season_prcp_mm AS pa, b.season_prcp_mm AS pb FROM
   (SELECT station_id, year, sum(value) / 10 AS season_prcp_mm FROM {S}.ghcn_daily
     WHERE station_id = '{r.station_a}' AND element = 'PRCP' AND q_flag IS NULL AND value IS NOT NULL
       AND month(date) BETWEEN 4 AND 9 GROUP BY station_id, year) a
  JOIN (SELECT station_id, year, sum(value) / 10 AS season_prcp_mm FROM {S}.ghcn_daily
     WHERE station_id = '{r.station_b}' AND element = 'PRCP' AND q_flag IS NULL AND value IS NOT NULL
       AND month(date) BETWEEN 4 AND 9 GROUP BY station_id, year) b ON a.year = b.year
  JOIN (SELECT year FROM {S}.station_year_quality WHERE station_id = '{r.station_a}' AND usable) ua ON ua.year = a.year
  JOIN (SELECT year FROM {S}.station_year_quality WHERE station_id = '{r.station_b}' AND usable) ub ON ub.year = a.year
""").collect()
import numpy as np
py = float(np.corrcoef([x.pa for x in m], [x.pb for x in m])[0, 1])
assert len(m) == r.n_years and abs(py - r.corr_season_prcp) < 1e-3, f"mismatch {py} vs {r.corr_season_prcp}"
print("second-method check passed:", r.station_a, r.station_b, round(py, 4))

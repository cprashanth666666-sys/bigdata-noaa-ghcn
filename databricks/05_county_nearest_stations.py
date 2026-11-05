# Databricks notebook source
# Story 2.1: link each county to its k nearest GHCN stations.
#
# Inputs : us_counties (centroids), ghcn_stations, ghcn_daily
# Output : workspace.default.county_station_links (county_fips, station_id, rank, distance_km)
# Assumptions:
#   - Only counties that have yield data are linked (the project scope).
#   - Only US stations that reported PRCP or TMAX in at least one year are candidates.
#     Story 2.2 will apply the stricter >=90% growing-season completeness filter.
#   - K = 10 nearest stations per county, within MAX_KM = 100 km (wide on purpose; 2.3 reports the 30 km gaps).
#   - Distance is haversine from the county's internal-point centroid, in km.

# COMMAND ----------

from pyspark.sql import functions as F, Window

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
K, MAX_KM = 10, 100.0

counties = (spark.table(f"{S}.us_counties")
    .join(spark.table(f"{S}.nass_county_yields").select("county_fips").distinct(), "county_fips")
    .select("county_fips", F.col("latitude").alias("clat"), F.col("longitude").alias("clon")))

active = (spark.table(f"{S}.ghcn_daily")
    .where("country_code = 'US' AND element IN ('PRCP','TMAX') AND q_flag IS NULL")
    .select("station_id").distinct())
stations = (spark.table(f"{S}.ghcn_stations").join(active, "station_id")
    .select("station_id", F.col("latitude").alias("slat"), F.col("longitude").alias("slon")))
print("counties:", counties.count(), "candidate stations:", stations.count())

# COMMAND ----------

def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = (F.col(c) for c in (lat1, lon1, lat2, lon2))
    p1, p2 = F.radians(lat1), F.radians(lat2)
    dphi, dlam = F.radians(lat2 - lat1), F.radians(lon2 - lon1)
    a = F.sin(dphi / 2) ** 2 + F.cos(p1) * F.cos(p2) * F.sin(dlam / 2) ** 2
    return 2 * 6371.0088 * F.asin(F.sqrt(a))

# Cheap bounding-box prefilter (1 degree latitude ~ 111 km) avoids a full 3k x 10k+ cross join cost
# on wide boxes; stations is small enough to broadcast.
pad = MAX_KM / 111.0
joined = (counties.join(F.broadcast(stations),
        (F.abs(F.col("clat") - F.col("slat")) <= pad) &
        (F.abs(F.col("clon") - F.col("slon")) <= pad / F.cos(F.radians(F.col("clat")))))
    .withColumn("distance_km", haversine_km("clat", "clon", "slat", "slon"))
    .where(F.col("distance_km") <= MAX_KM))

w = Window.partitionBy("county_fips").orderBy("distance_km", "station_id")
links = (joined.withColumn("rank", F.row_number().over(w))
    .where(F.col("rank") <= K)
    .select("county_fips", "station_id", "rank", F.round("distance_km", 3).alias("distance_km")))

(links.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{S}.county_station_links"))

# COMMAND ----------

# Checks: second method (pure SQL, one sample county) and coverage summary.
t = spark.table(f"{S}.county_station_links")
print("link rows:", t.count(), "counties linked:", t.select("county_fips").distinct().count(),
      "of", counties.count())
t.where("rank = 1").selectExpr(
    "percentile_approx(distance_km, array(0.5, 0.9, 0.99)) AS nearest_km_p50_p90_p99",
    "max(distance_km) AS max_nearest_km").show(truncate=False)

sample = t.where("rank = 1").orderBy("county_fips").first()
check = spark.sql(f"""
    SELECT s.station_id,
      2*6371.0088*asin(sqrt(pow(sin(radians(s.latitude-c.latitude)/2),2) +
        cos(radians(c.latitude))*cos(radians(s.latitude))*pow(sin(radians(s.longitude-c.longitude)/2),2))) AS d
    FROM {S}.ghcn_stations s JOIN {S}.us_counties c ON c.county_fips = '{sample['county_fips']}'
    WHERE s.station_id IN (SELECT station_id FROM {S}.county_station_links WHERE county_fips = '{sample['county_fips']}')
    ORDER BY d LIMIT 1""").first()
assert check["station_id"] == sample["station_id"] and abs(check["d"] - sample["distance_km"]) < 0.01
print("independent SQL check passed for county", sample["county_fips"])

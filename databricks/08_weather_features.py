# Databricks notebook source
# Stories 3.1 and 3.2: weather index features per county-year (Gold).
#
# Inputs : county_year_station (nearest usable station), ghcn_daily
# Output : workspace.default.county_year_weather_features
#   county_fips, year, station_id, distance_km,
#   season_prcp_mm        April-September total precipitation (mm)
#   min_30d_prcp_mm       driest 30-day window inside April-September (mm)
#   days_tmax_gt30        July-August days with TMAX > 30 C
#   days_tmax_gt35        July-August days with TMAX > 35 C
# Assumptions:
#   - One station per county-year: the nearest usable one, only if within MAX_KM = 30 km.
#   - Raw units: PRCP in tenths of mm, TMAX in tenths of C. Converted here.
#   - Days with a QC flag or null value are ignored, NOT treated as zero. A usable station-year has
#     >=90% of days, so season_prcp_mm is a slight underestimate; missing days are not imputed.
#   - 30-day window = 30 calendar days ending on a season day from 30 April on, needs >= 27 valid days.

# COMMAND ----------

from pyspark.sql import functions as F, Window

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
MAX_KM = 30.0

pairs = (spark.table(f"{S}.county_year_station").where(F.col("distance_km") <= MAX_KM))
station_years = pairs.select("station_id", "year").distinct()

d = (spark.table(f"{S}.ghcn_daily")
     .where("country_code = 'US' AND element IN ('PRCP','TMAX') AND q_flag IS NULL AND value IS NOT NULL")
     .where(F.month("date").between(4, 9))
     .join(F.broadcast(station_years), ["station_id", "year"]))

# COMMAND ----------

# Station-year features.
prcp = d.where("element = 'PRCP'").select("station_id", "year", "date", (F.col("value") / 10).alias("mm"))
season = prcp.groupBy("station_id", "year").agg(F.round(F.sum("mm"), 1).alias("season_prcp_mm"))

w30 = (Window.partitionBy("station_id", "year")
       .orderBy(F.col("date").cast("timestamp").cast("long") / 86400)
       .rangeBetween(-29, 0))
roll = (prcp.withColumn("sum30", F.sum("mm").over(w30)).withColumn("n30", F.count("mm").over(w30))
        .where((F.col("n30") >= 27) & (F.col("date") >= F.make_date(F.col("year"), F.lit(4), F.lit(30))))
        .groupBy("station_id", "year").agg(F.round(F.min("sum30"), 1).alias("min_30d_prcp_mm")))

heat = (d.where("element = 'TMAX' AND month(date) IN (7, 8)")
        .groupBy("station_id", "year").agg(
            F.sum((F.col("value") > 300).cast("int")).alias("days_tmax_gt30"),
            F.sum((F.col("value") > 350).cast("int")).alias("days_tmax_gt35")))

feat = (pairs.join(season, ["station_id", "year"], "left")
              .join(roll, ["station_id", "year"], "left")
              .join(heat, ["station_id", "year"], "left")
        .select("county_fips", "year", "station_id", "distance_km",
                "season_prcp_mm", "min_30d_prcp_mm", "days_tmax_gt30", "days_tmax_gt35"))

(feat.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{S}.county_year_weather_features"))

# COMMAND ----------

t = spark.table(f"{S}.county_year_weather_features")
print("county-years:", t.count(), "counties:", t.select("county_fips").distinct().count())
t.selectExpr("round(avg(season_prcp_mm),0) AS avg_season_mm", "round(avg(min_30d_prcp_mm),1) AS avg_min30_mm",
             "round(avg(days_tmax_gt30),1) AS avg_gt30", "round(avg(days_tmax_gt35),1) AS avg_gt35",
             "sum(case when season_prcp_mm is null then 1 else 0 end) AS null_season",
             "sum(case when min_30d_prcp_mm is null then 1 else 0 end) AS null_min30").show()
assert t.where("days_tmax_gt35 > days_tmax_gt30 OR days_tmax_gt30 > 62").count() == 0, "heat counts impossible"
assert t.groupBy("county_fips", "year").count().where("count > 1").count() == 0, "duplicate county-year"

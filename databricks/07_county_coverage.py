# Databricks notebook source
# Story 2.3: which counties lack a usable station nearby?
#
# Inputs : county_station_links (10 nearest stations within 100 km), station_year_quality, nass_county_yields
# Output : workspace.default.county_year_station (county_fips, year, station_id, distance_km)
#            = the NEAREST USABLE station per county-year, any distance up to 100 km
#          workspace.default.county_coverage_gaps (county_fips, state_fips, years_total, years_covered_30km,
#            nearest_usable_km_median)
# Assumptions:
#   - "Usable" comes from station_year_quality (>=90% growing-season PRCP and TMAX).
#   - Covered = nearest usable station is within COVER_KM = 30 km in that year.
#   - Scope = counties that have yield data. Corn Belt = state FIPS IA 19, IL 17, IN 18, NE 31, MN 27.
#   - Links hold only the 10 nearest stations, so a county whose 10 nearest are all unusable counts as uncovered.

# COMMAND ----------

from pyspark.sql import functions as F, Window

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
COVER_KM = 30.0
YEARS = list(range(2000, 2026))
CORN_BELT = ["19", "17", "18", "31", "27"]

links = spark.table(f"{S}.county_station_links")
usable = spark.table(f"{S}.station_year_quality").where("usable").select("station_id", "year")
years = spark.createDataFrame([(y,) for y in YEARS], "year INT")

cy = (links.crossJoin(years).join(usable, ["station_id", "year"]))
w = Window.partitionBy("county_fips", "year").orderBy("distance_km", "station_id")
nearest = (cy.withColumn("r", F.row_number().over(w)).where("r = 1")
           .select("county_fips", "year", "station_id", "distance_km"))
(nearest.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{S}.county_year_station"))

# COMMAND ----------

scope = (spark.table(f"{S}.nass_county_yields").select("county_fips").distinct()
         .crossJoin(years))
cov = (scope.join(spark.table(f"{S}.county_year_station"), ["county_fips", "year"], "left")
       .withColumn("covered", (F.col("distance_km") <= COVER_KM).cast("int")))
gaps = (cov.groupBy("county_fips").agg(
            F.count("*").alias("years_total"),
            F.sum(F.coalesce("covered", F.lit(0))).alias("years_covered_30km"),
            F.percentile_approx("distance_km", 0.5).alias("nearest_usable_km_median"))
        .withColumn("state_fips", F.substring("county_fips", 1, 2)))
(gaps.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{S}.county_coverage_gaps"))

# COMMAND ----------

g = spark.table(f"{S}.county_coverage_gaps")
print("all counties with yields:", g.count())
g.selectExpr("sum(case when years_covered_30km = years_total then 1 else 0 end) AS always_covered",
             "sum(case when years_covered_30km = 0 then 1 else 0 end) AS never_covered").show()
cb = g.where(F.col("state_fips").isin(CORN_BELT))
cb.selectExpr("count(*) AS corn_belt_counties",
              "sum(case when years_covered_30km = years_total then 1 else 0 end) AS always_covered",
              "sum(case when years_covered_30km = 0 then 1 else 0 end) AS never_covered",
              "round(avg(years_covered_30km / years_total), 3) AS avg_share_years_covered").show()

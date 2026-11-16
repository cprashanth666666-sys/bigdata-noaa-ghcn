# Databricks notebook source
# Stories 4.1 and 4.2: detrend county yields and flag loss years (Silver -> Gold).
#
# Inputs : nass_county_yields
# Output : workspace.default.county_yield_trend
#            county_fips, crop, year, yield_value, trend_yield, residual, pct_of_trend, is_loss
# Assumptions:
#   - Crops: corn for grain and soybeans, the two series in CROPS below. Silage and other series are excluded.
#   - Scope: Corn Belt states IA 19, IL 17, IN 18, NE 31, MN 27 (same as notebook 07). Years 2000-2025.
#   - Trend = ordinary least squares line of yield on year, fitted per county and crop. A county-crop needs
#     >= MIN_YEARS = 15 yield years, otherwise it is dropped (a trend on a few points is noise).
#   - The trend is fitted on ALL years including the one being tested (in-sample). A big loss year pulls the
#     line down a little, so losses are slightly understated. Leave-one-out is the stricter alternative.
#   - Loss = yield < LOSS_RATIO x trend, with LOSS_RATIO = 0.85 (configurable, change it here).
#   - Irrigated and non-irrigated series are NOT split; whichever series NASS publishes under CROPS is used.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
CORN_BELT = ["19", "17", "18", "31", "27"]
CROPS = {"CORN, GRAIN - YIELD, MEASURED IN BU / ACRE": "corn",
         "SOYBEANS - YIELD, MEASURED IN BU / ACRE": "soybeans"}
MIN_YEARS = 15
LOSS_RATIO = 0.85

y = spark.table(f"{S}.nass_county_yields")

# Look before filtering: confirm the series names exist exactly as written above.
(y.where(F.col("commodity").isin("CORN", "SOYBEANS")).groupBy("commodity", "series").count()
  .orderBy("commodity", "series").show(truncate=False))

crop_map = F.create_map(*[x for k, v in CROPS.items() for x in (F.lit(k), F.lit(v))])
base = (y.where(F.col("series").isin(list(CROPS)))
         .where(F.substring("county_fips", 1, 2).isin(CORN_BELT))
         .where(F.col("year").between(2000, 2025))
         .withColumn("crop", crop_map[F.col("series")])
         .groupBy("county_fips", "crop", "year").agg(F.avg("yield_value").alias("yield_value")))  # 1 row per county-crop-year

# COMMAND ----------

# OLS per county-crop with plain aggregates: slope = cov(year, yield) / var(year). No UDF; scales across the cluster.
g = ["county_fips", "crop"]
fit = (base.groupBy(*g).agg(
            F.count("*").alias("n_years"),
            (F.covar_pop("year", "yield_value") / F.var_pop("year")).alias("slope"),
            F.avg("yield_value").alias("mean_y"), F.avg("year").alias("mean_x"))
       .where(F.col("n_years") >= MIN_YEARS))

out = (base.join(fit, g)
       .withColumn("trend_yield", F.round(F.col("mean_y") + F.col("slope") * (F.col("year") - F.col("mean_x")), 2))
       .withColumn("residual", F.round(F.col("yield_value") - F.col("trend_yield"), 2))
       .withColumn("pct_of_trend", F.round(F.col("yield_value") / F.col("trend_yield"), 4))
       .withColumn("is_loss", F.col("yield_value") < LOSS_RATIO * F.col("trend_yield"))
       .select("county_fips", "crop", "year", "yield_value", "trend_yield", "residual", "pct_of_trend", "is_loss"))

(out.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{S}.county_yield_trend"))

# COMMAND ----------

t = spark.table(f"{S}.county_yield_trend")
print("rows:", t.count(), "county-crops:", t.select("county_fips", "crop").distinct().count())
t.groupBy("crop").agg(
    F.countDistinct("county_fips").alias("counties"), F.count("*").alias("county_years"),
    F.round(F.avg(F.col("is_loss").cast("int")), 3).alias("loss_share"),
    F.round(F.avg("pct_of_trend"), 3).alias("avg_pct_of_trend")).show()
print("loss share by year (a few years should stand out, e.g. the 2012 drought):")
t.groupBy("year").agg(F.round(F.avg(F.col("is_loss").cast("int")), 3).alias("loss_share")).orderBy("year").show(30)

assert t.groupBy("county_fips", "crop", "year").count().where("count > 1").count() == 0, "duplicate county-crop-year"
assert t.where("trend_yield <= 0").count() == 0, "non-positive trend; check series or years"
# OLS residuals sum to ~0 within each county-crop: a second-method check on the fit.
bad = t.groupBy("county_fips", "crop").agg(F.sum("residual").alias("s")).where(F.abs("s") > 0.5).count()
assert bad == 0, f"{bad} county-crops whose residuals do not sum to ~0"

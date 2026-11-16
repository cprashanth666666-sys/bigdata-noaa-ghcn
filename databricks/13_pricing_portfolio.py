# Databricks notebook source
# Sprint 5, stories 6.1 and 6.2: burn-cost premium per county and a portfolio view.
#
# Inputs : best_trigger_region, trigger_eval_county, trigger_county_year (notebook 11), county_yield_trend (10)
# Outputs (workspace.default):
#   premium_county         one row per county and crop: chosen trigger, payout frequency, burn rate,
#                          premium rate and premium per acre, share of the farmer's shortfall the trigger paid
#   portfolio_year         one row per crop and year: total payout, premium, loss ratio, counties paid
#   portfolio_summary      one row per crop: expected annual payout, worst year, worst-year loss ratio
# Assumptions (all configurable below; none of these are sourced market figures):
#   - PRICE: illustrative reference prices in USD per bushel. Replace with the RMA projected price for a real quote.
#   - Sum insured per acre = COVERAGE x trend yield x PRICE. COVERAGE = 0.85 matches the loss threshold in notebook 10.
#   - Payout is binary: PAYOUT_SHARE of the sum insured in every year the trigger fires, nothing otherwise.
#   - Burn cost = historic average payout as a share of sum insured. Premium rate = burn rate x (1 + LOADING);
#     LOADING covers expenses, profit and the uncertainty from a short (~20 to 26 year) history.
#   - Each county is ONE insured acre of each crop (equal weight). No acreage data is joined, so the
#     portfolio shows the shape of the risk (which years hurt, how bad), not dollar exposure.
#   - The farmer's shortfall = max(0, COVERAGE x trend - actual yield) x PRICE, i.e. what an indemnity
#     policy at the same coverage would have paid. Its gap to the trigger payout is basis risk in dollars.
#   - Thresholds come from notebook 11 and are in-sample, so premiums here are optimistic for the insurer.

# COMMAND ----------

from pyspark.sql import functions as F, Window

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
PRICE = {"corn": 4.50, "soybeans": 11.00}
COVERAGE = 0.85
PAYOUT_SHARE = 0.25
LOADING = 0.25

price = F.create_map(*[x for k, v in PRICE.items() for x in (F.lit(k), F.lit(v))])
keys = ["index_name", "pay_freq"]

chosen = (spark.table(f"{S}.best_trigger_region").select("state_fips", "crop", *keys)
          .join(spark.table(f"{S}.trigger_eval_county").withColumn("state_fips", F.substring("county_fips", 1, 2))
                .select("county_fips", "state_fips", "crop", *keys), ["state_fips", "crop", *keys]))

cy = (spark.table(f"{S}.trigger_county_year").join(chosen, ["county_fips", "crop", *keys])
      .join(spark.table(f"{S}.county_yield_trend").select("county_fips", "crop", "year", "yield_value", "trend_yield"),
            ["county_fips", "crop", "year"])
      .withColumn("price", price[F.col("crop")])
      .withColumn("sum_insured", COVERAGE * F.col("trend_yield") * F.col("price"))
      .withColumn("payout", F.when(F.col("trig"), PAYOUT_SHARE * F.col("sum_insured")).otherwise(F.lit(0.0)))
      .withColumn("shortfall", F.greatest(F.lit(0.0), COVERAGE * F.col("trend_yield") - F.col("yield_value")) * F.col("price")))

# COMMAND ----------

# 6.1: burn-cost premium per county.
latest = (cy.groupBy("county_fips", "crop").agg(F.max("year").alias("latest_year")))
si_latest = (cy.join(latest, ["county_fips", "crop"]).where(F.col("year") == F.col("latest_year"))
             .select("county_fips", "crop", F.col("sum_insured").alias("sum_insured_latest")))

prem = (cy.groupBy("county_fips", "state_fips", "crop", *keys).agg(
            F.count("*").alias("n_years"),
            F.round(F.avg(F.col("trig").cast("int")), 4).alias("payout_freq"),
            F.round(F.avg(F.col("payout") / F.col("sum_insured")), 5).alias("burn_rate"),
            F.round(F.avg("payout"), 2).alias("avg_payout_usd"),
            F.round(F.avg("shortfall"), 2).alias("avg_shortfall_usd"),
            F.round(F.sum(F.least("payout", "shortfall")) / F.sum("shortfall"), 4).alias("shortfall_share_paid"))
        .withColumn("premium_rate", F.round(F.col("burn_rate") * (1 + LOADING), 5))
        .join(si_latest, ["county_fips", "crop"])
        .withColumn("sum_insured_latest", F.round("sum_insured_latest", 2))
        .withColumn("premium_per_acre_usd", F.round(F.col("premium_rate") * F.col("sum_insured_latest"), 2)))
(prem.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
     .saveAsTable(f"{S}.premium_county"))

# COMMAND ----------

# 6.2: portfolio by year. Premium in each year uses that year's sum insured, so payouts and premium match in scale.
rate = spark.table(f"{S}.premium_county").select("county_fips", "crop", "premium_rate")
py = (cy.join(rate, ["county_fips", "crop"])
      .withColumn("premium", F.col("premium_rate") * F.col("sum_insured"))
      .groupBy("crop", "year").agg(
          F.countDistinct("county_fips").alias("counties"),
          F.sum(F.col("trig").cast("int")).alias("counties_paid"),
          F.round(F.sum("payout"), 2).alias("payout_usd"),
          F.round(F.sum("premium"), 2).alias("premium_usd"),
          F.round(F.sum("shortfall"), 2).alias("shortfall_usd"))
      .withColumn("loss_ratio", F.round(F.col("payout_usd") / F.col("premium_usd"), 3)))
(py.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
   .saveAsTable(f"{S}.portfolio_year"))

p = spark.table(f"{S}.portfolio_year")
worst = (p.withColumn("r", F.row_number().over(Window.partitionBy("crop").orderBy(F.desc("payout_usd"))))
         .where("r = 1").select("crop", F.col("year").alias("worst_year"), F.col("payout_usd").alias("worst_payout_usd"),
                                F.col("loss_ratio").alias("worst_loss_ratio")))
summary = (p.groupBy("crop").agg(
               F.count("*").alias("years"),
               F.round(F.avg("payout_usd"), 2).alias("expected_annual_payout_usd"),
               F.round(F.avg("premium_usd"), 2).alias("avg_annual_premium_usd"),
               F.round(F.sum("payout_usd") / F.sum("premium_usd"), 3).alias("long_run_loss_ratio"),
               F.round(F.sum("payout_usd") / F.sum("shortfall_usd"), 3).alias("payout_to_shortfall"))
           .join(worst, "crop")
           .withColumn("worst_to_expected", F.round(F.col("worst_payout_usd") / F.col("expected_annual_payout_usd"), 2)))
(summary.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
        .saveAsTable(f"{S}.portfolio_summary"))

# COMMAND ----------

pc = spark.table(f"{S}.premium_county")
print("priced county-crops:", pc.count())
pc.groupBy("crop").agg(F.count("*").alias("counties"),
                       F.round(F.avg("premium_rate"), 4).alias("avg_premium_rate"),
                       F.round(F.avg("premium_per_acre_usd"), 2).alias("avg_premium_per_acre_usd"),
                       F.round(F.avg("shortfall_share_paid"), 3).alias("avg_shortfall_share_paid")).show()
spark.table(f"{S}.portfolio_summary").show(truncate=False)
spark.table(f"{S}.portfolio_year").orderBy("crop", "year").show(60)

assert pc.groupBy("county_fips", "crop").count().where("count > 1").count() == 0, "a county-crop priced twice"
# Second-method check: with a binary payout proportional to sum insured, burn rate must equal payout_freq x PAYOUT_SHARE.
bad = pc.where(F.abs(F.col("burn_rate") - F.col("payout_freq") * PAYOUT_SHARE) > 1e-4).count()
assert bad == 0, f"{bad} counties where burn rate != payout frequency x payout share"
# Portfolio totals must equal the sum of county-year payouts.
tot_cy = cy.agg(F.sum("payout")).first()[0]
tot_p = p.agg(F.sum("payout_usd")).first()[0]
assert abs(tot_cy - tot_p) < 1.0, f"portfolio total {tot_p} != county-year total {tot_cy}"
print("checks passed; total historic payout (USD, one acre per county):", round(tot_p, 2))

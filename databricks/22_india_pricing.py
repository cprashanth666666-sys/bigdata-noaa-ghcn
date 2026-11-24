# Databricks notebook source
# India pilot, story IN-4.1: burn-cost premium for the chosen weather trigger per district, set beside
# (a) the PMFBY farmer premium cap and (b) the burn cost of a PMFBY-style yield indemnity on the same district.
#
# Inputs : in_best_trigger_state, in_trigger_eval_district, in_trigger_district_year (21), in_district_yield_trend (20)
# Outputs (workspace.default):
#   in_premium_district   one row per district and crop: trigger, payout frequency, premium rate (% of sum insured),
#                         PMFBY-style indemnity rate, farmer cap, implied subsidy, share of shortfall the trigger paid
#   in_premium_state      the same, averaged per state and crop (equal weight per district)
# Assumptions (configurable; none are market quotes):
#   - Rates are a share of the sum insured, so no crop price is needed. Converting to INR per hectare needs the
#     scale of finance or MSP per crop and year (data item D8, not collected yet).
#   - Weather payout is binary: PAYOUT_SHARE (25%) of sum insured when the trigger fires; same as the US build.
#   - PMFBY-style indemnity = max(0, T - Y) / T with T = best-5-of-7 average x 80% (indemnity level 80%).
#   - Premium rate = burn rate x (1 + LOADING), LOADING = 25%.
#   - Farmer cap: 2% of sum insured for Kharif food and oilseed crops, 5% for commercial crops (cotton)
#     (PMFBY Operational Guidelines; PIB, 29 Aug 2026). Implied subsidy = premium rate - cap, shared by Centre and State.
#   - The trigger is the state's chosen trigger under the trend85 loss rule (notebook 21), applied to every
#     district of that state that passed notebook 21's screen.

# COMMAND ----------

from pyspark.sql import functions as F

CATALOG = spark.sql("SELECT current_catalog()").first()[0]
S = f"{CATALOG}.default"
PAYOUT_SHARE, LOADING, INDEMNITY = 0.25, 0.25, 0.80
FARMER_CAP = {"Cotton(lint)": 0.05}          # every other crop here: 0.02
keys = ["crop", "index_name", "pay_freq"]

chosen = (spark.table(f"{S}.in_best_trigger_state").where("loss_def = 'trend85'").select("state", *keys)
          .join(spark.table(f"{S}.in_trigger_eval_district").where("loss_def = 'trend85'").select("shape_id", "state", *keys),
                ["state", *keys]))
yt = spark.table(f"{S}.in_district_yield_trend").select("shape_id", "crop", "year", "state", "district", "yield_value", "pmfby_avg_yield")
dy = (spark.table(f"{S}.in_trigger_district_year").where("loss_def = 'trend85'")
      .join(chosen.drop("state"), ["shape_id", *keys]).join(yt, ["shape_id", "crop", "year"])
      .withColumn("payout_share", F.when(F.col("trig"), F.lit(PAYOUT_SHARE)).otherwise(F.lit(0.0)))
      .withColumn("T", F.col("pmfby_avg_yield") * INDEMNITY)
      .withColumn("indemnity_share", F.when(F.col("T").isNull(), None)
                  .otherwise(F.greatest(F.lit(0.0), (F.col("T") - F.col("yield_value")) / F.col("T")))))

cap = F.coalesce(F.create_map(*[x for k, v in FARMER_CAP.items() for x in (F.lit(k), F.lit(v))])[F.col("crop")], F.lit(0.02))
prem = (dy.groupBy("shape_id", "state", "district", *keys).agg(
            F.count("*").alias("n_years"),
            F.round(F.avg(F.col("trig").cast("int")), 4).alias("payout_freq"),
            F.avg("payout_share").alias("burn_rate"),
            F.avg("indemnity_share").alias("indemnity_burn_rate"),
            F.count("indemnity_share").alias("n_years_pmfby"),
            # Over years with a PMFBY shortfall, how much of it did the trigger pay (capped at the shortfall)?
            F.expr("try_divide(sum(CASE WHEN indemnity_share IS NOT NULL THEN least(payout_share, indemnity_share) END), "
                   "sum(indemnity_share))").alias("shortfall_paid_share"))
        .withColumn("premium_rate", F.round(F.col("burn_rate") * (1 + LOADING), 4))
        .withColumn("pmfby_style_rate", F.round(F.col("indemnity_burn_rate") * (1 + LOADING), 4))
        .withColumn("farmer_cap", cap)
        .withColumn("implied_subsidy_rate", F.round(F.col("premium_rate") - F.col("farmer_cap"), 4)))
prem.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_premium_district")

pd_ = spark.table(f"{S}.in_premium_district")
state = (pd_.groupBy("state", *keys).agg(
            F.count("*").alias("districts"),
            F.round(F.avg("payout_freq"), 3).alias("payout_freq"),
            F.round(F.avg("premium_rate"), 4).alias("premium_rate"),
            F.round(F.avg("pmfby_style_rate"), 4).alias("pmfby_style_rate"),
            F.first("farmer_cap").alias("farmer_cap"),
            F.round(F.avg("implied_subsidy_rate"), 4).alias("implied_subsidy_rate"),
            F.round(F.avg("shortfall_paid_share"), 3).alias("shortfall_paid_share")))
state.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{S}.in_premium_state")

# COMMAND ----------

# Checks and summary
assert pd_.groupBy("shape_id", "crop").count().where("count > 1").count() == 0, "one trigger per district-crop"
# Second method: burn rate must equal payout frequency x PAYOUT_SHARE exactly (binary payout).
assert pd_.where(f"abs(burn_rate - payout_freq * {PAYOUT_SHARE}) > 1e-3").count() == 0, "burn rate != frequency x share"
assert pd_.where("premium_rate < 0 OR pmfby_style_rate < 0").count() == 0
print("district-crops priced:", pd_.count())
pd_.groupBy("crop").agg(F.count("*").alias("districts"),
                        F.round(F.avg("premium_rate") * 100, 2).alias("trigger_premium_pct"),
                        F.round(F.avg("pmfby_style_rate") * 100, 2).alias("pmfby_style_pct"),
                        F.first("farmer_cap").alias("farmer_cap"),
                        F.round(F.avg("shortfall_paid_share"), 3).alias("shortfall_paid_share")).orderBy("crop").show()
display(spark.table(f"{S}.in_premium_state").orderBy("crop", "state"))

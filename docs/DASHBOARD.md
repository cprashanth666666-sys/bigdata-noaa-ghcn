# Dashboard build guide (story 7.1)

**Dashboard name:** Parametric weather insurance: basis risk and pricing

**Audience:** the insurer, played by the Product Owner. Each page answers one question the insurer would ask.

**Data:** the views created by `databricks/14_dashboard_views.py`. Run notebooks 06 to 14 in order first. Notebook 14 fails with a clear message if a view is empty.

## How to build it

1. In Databricks, open **Dashboards → Create dashboard** (the AI/BI dashboard editor).
2. On the **Data** tab, add one dataset per view below. Each dataset uses a query of the form `SELECT * FROM workspace.default.<view>`.
3. Add three global filters on the **Data** tab: `crop` (single value, default `corn`), `state_alpha` (multi-select), and `pay_freq` (single value, default `0.20`). Each filter applies only to the datasets that have that column.
4. Build the pages below, then **Publish**. Export the finished dashboard as a `.lvdash.json` file into `databricks/dashboard/` so it is version-controlled.

## Datasets

| Dataset | View | Used for |
|---|---|---|
| basis_risk_map | `v_county_basis_risk` | Page 1 map and table |
| premium | `v_county_premium` | Page 3 map and table |
| trigger_perf | `v_trigger_performance` | Page 2 bars |
| distance_bands | `v_basis_risk_by_distance` | Page 2 bars |
| corr_curve | `v_corr_distance` | Page 2 line |
| portfolio_year | `v_portfolio_year` | Page 4 chart |
| portfolio_summary | `v_portfolio_summary` | Page 4 counters |
| coverage | `v_coverage_gaps` | Page 1 second map |

## Page 1: Where does the trigger fail farmers?

| Widget | Type | Fields |
|---|---|---|
| Basis risk by county | Point map | latitude, longitude; colour = `miss_rate` (sequential, higher = darker); tooltip = county_name, index_name, n_loss, false_alarm_rate, avg_distance_km |
| Counties without a usable station within 30 km | Point map | latitude, longitude; colour = `share_years_covered`; filter `share_years_covered < 0.5` |
| Worst 20 counties | Table | county_name, state_alpha, crop, index_name, miss_rate, false_alarm_rate, avg_distance_km; sort by miss_rate descending |

## Page 2: Which trigger works, and why does distance matter?

| Widget | Type | Fields |
|---|---|---|
| Miss rate by index | Bar | x = index_name, y = miss_rate, group = pay_freq; filter crop |
| Miss vs false alarm | Scatter | x = false_alarm_rate, y = miss_rate, colour = index_name, size = loss_years. Points toward the bottom-left are better. |
| Basis risk by station distance | Bar | x = dist_band, y = miss_rate, group = index_name; filter crop and pay_freq |
| Weather similarity vs distance | Line | x = dist_bin_km, y = median_corr_prcp and median_corr_heat |

## Page 3: What does cover cost?

| Widget | Type | Fields |
|---|---|---|
| Premium per acre | Point map | latitude, longitude; colour = premium_per_acre_usd |
| Premium rate distribution | Histogram | premium_rate, filter crop |
| Premium table | Table | county_name, state_alpha, crop, index_name, payout_freq, premium_rate, sum_insured_latest, premium_per_acre_usd, shortfall_share_paid |

## Page 4: How bad can a year get for the insurer?

| Widget | Type | Fields |
|---|---|---|
| Expected annual payout | Counter | expected_annual_payout_usd |
| Worst year and payout | Counter | worst_year, worst_payout_usd |
| Worst-year loss ratio | Counter | worst_loss_ratio |
| Payout vs premium by year | Combo | x = year; bars = payout_usd; line = premium_usd; filter crop |
| Counties paid per year | Bar | x = year, y = counties_paid |

## Caveats to show on the dashboard

Put one text box on page 1 with these points:

- Thresholds are set from the same years they are tested on, so the miss rates shown are optimistic.
- Each county counts as one insured acre. Dollar figures show the shape of the risk, not real exposure.
- Crop prices and the payout share are illustrative assumptions set in notebook 13, not market quotes.

# Gold-table results used in the reports (queried 24 Nov 2026)

Queried on the Databricks SQL warehouse (Serverless Starter Warehouse), catalog `workspace.default`.
Each headline figure was re-derived a second way (column "Check").

| Figure | Value | Query | Check |
|---|---|---|---|
| Pipeline validation | 46 of 46 passed | `pipeline_validation` | - |
| Corn county-years, loss share | 10,768 county-years, 445 counties, 977 losses (9.1%) | `county_yield_trend` | recomputed from `yield_value < 0.85*trend_yield`: 977 |
| Soybean county-years, loss share | 10,420, 433 counties, 1,078 losses (10.4%) | same | 1,078 |
| Worst loss year | 2012: 65.4% of corn county-years, 42.3% of soybean; 2003 soybeans 58.5% | same | - |
| Best trigger, IA corn | days > 35 °C, pays 1 year in 5; miss 31.7%, false alarm 21.5%, 70 counties | `best_trigger_region` | pooled from `trigger_eval_county`: 99 hits, 46 misses = 31.7% |
| Best triggers, all regions | heat index in IL, IN, IA (both crops); rainfall in MN (driest 30 days) and NE (season rain); miss 10.9% to 54.8% vs naive 69% to 74% | `best_trigger_region` | - |
| Miss rate by distance, corn, pay 1 in 5 | days > 35 °C: 32.7% / 31.8% / 32.4%; season rain: 53.1% / 50.6% / 63.9% (0-10 / 10-20 / 20-30 km) | `trigger_eval_dist_band` | - |
| Pooled all indices, corn | 46.6% / 48.8% / 51.1% | same | - |
| Station correlation | rainfall 0.91 (0-10 km) to 0.80 (30-40 km) to 0.52 (180-190 km); heat days 0.90 to 0.89 to 0.82 | `corr_distance_curve` | - |
| Premium, corn | 230 counties; median rate 8.5%; median USD 62.04/acre (35.54 to 96.18); median 66% of shortfall paid | `premium_county` | median via `v_county_premium`: 62.04 |
| Premium, soybeans | 226 counties; median rate 9.1%; median USD 48.95/acre (26.35 to 78.68); median 88% of shortfall paid | same | 48.95 |
| Portfolio | long-run loss ratio 0.785 (both crops); worst year 2012: corn payout USD 29,779 = 2.70x annual premium, 3.72x expected; soybeans USD 21,777 = 2.51x | `portfolio_summary` | `portfolio_year` top year: 2012, 29,779.01 |
| Coverage gaps, Corn Belt | 470 counties scored; 87 never have a usable station within 30 km; 155 covered in under half of years; median nearest usable station 7.4 km | `county_coverage_gaps` filtered to state FIPS 17, 18, 19, 27, 31 | - |

Note: `county_coverage_gaps` holds all 2,807 US yield counties; the Corn Belt figures filter it by state.
Dollar figures assume one insured acre per county and illustrative prices (notebook 13 header).

# India pilot results, 24 Nov 2026 (notebooks 19-22)

All four notebooks ran on Databricks serverless (job run 629608201030392; notebook 21 re-run after the rain-fed state fix). Each notebook's built-in checks passed: no duplicate keys, confusion counts add up (hit + miss = loss years, hit + false alarm = trigger years), OLS residuals sum to zero, and a plain-Python rebuild of one district-trigger and one PMFBY threshold matched Spark exactly. The figures below were re-queried through the SQL warehouse.

## IN-2.1 Kharif weather features (`in_district_year_weather`)

- 26,460 district-years, 735 districts, 1990-2025. 123 district-years have no temperature cell (island and coastal districts).
- Mean district June-September rain 974 mm, longest dry spell (<= 2.5 mm) 14.8 days, onset delay 15.7 days after 1 June.
- **Check against known droughts:** the five driest years in our cell-weighted all-India series are 2002 (678 mm), 2009 (706), 2004 (749), 2014 and 2015 (752 each). 2002 and 2009 are IMD's two big monsoon droughts of the period, and 2014 and 2015 were deficit years. Our level is higher than IMD's all-India normal (about 870 mm) because cells are not area-weighted and districts are weighted by cell count, so the wet north-east and west coast count more. The ranking of years is what the triggers use.

## IN-2.2 Loss years (`in_district_yield_trend`)

| Crop | Districts | District-years | Loss share, 85% of trend | PMFBY 70% | PMFBY 80% | PMFBY 90% |
|---|---|---|---|---|---|---|
| Bajra | 248 | 5,788 | 25.4% | 12.8% | 19.8% | 30.7% |
| Cotton (lint) | 211 | 4,793 | 29.3% | 14.4% | 21.4% | 32.2% |
| Groundnut | 284 | 6,580 | 26.7% | 13.6% | 21.9% | 34.6% |
| Maize | 382 | 9,111 | 26.3% | 12.4% | 20.7% | 33.0% |
| Rice | 377 | 9,077 | 17.2% | 6.0% | 10.9% | 21.8% |
| Soybean | 171 | 3,888 | 27.8% | 21.9% | 31.2% | 43.6% |

Indian district yields are far more volatile than the US Corn Belt counties: 17-29% of district-years fall below 85% of trend, against 9-10% for US corn and soybeans. Rice has the fewest losses, consistent with irrigation. PMFBY shares need the 7 previous years, so they cover fewer years.

## IN-3.1 Triggers and basis risk (`in_trigger_eval_district`, `in_best_trigger_state`)

Pooled over districts, 20% nominal pay frequency, 85%-of-trend losses:

| Index | Six rain-fed states: miss rate | False-alarm rate | Other states: miss rate | False-alarm rate |
|---|---|---|---|---|
| Season rain low | **62.4%** | 18.2% | 68.9% | 23.5% |
| June-July rain low | 66.2% | 20.9% | 73.5% | 20.9% |
| Aug-Sep rain low | 67.0% | 17.6% | 68.9% | 24.9% |
| Longest dry spell | 71.1% | 19.4% | 71.2% | 24.3% |
| Days > 35 °C | 71.1% | 18.1% | 70.2% | 24.6% |
| Late onset | 75.6% | 20.7% | 74.0% | 23.4% |
| Max 3-day rain (excess) | 80.7% | 23.0% | 79.2% | 22.2% |

The six rain-fed states are Maharashtra, Madhya Pradesh, Rajasthan, Gujarat, Karnataka and Telangana. A trigger paying at random at about 24% would miss about 76% of losses. Season-total rain beats it by about 14 points in the rain-fed states, and the gap is smaller elsewhere, where irrigation weakens the rain-yield link. Excess rain and late onset barely beat random at district level.

**Best trigger per state and crop** (97 state-crops under the 85% rule, 56 under PMFBY 80%): average miss rate 57.4% against 73.3% naive (PMFBY 80%: 57.9% vs 74.5%). Season rain is chosen most often (30 of 97), then June-July rain (15) and Aug-Sep rain (14). The best cases are in the rain-fed states:

- Rajasthan: groundnut 40% and bajra 42% miss rate on Aug-Sep rain; rice 38% on season rain.
- Telangana: rice 31% on season rain, but only 9 districts and 29 loss years. This is a thin sample.
- Gujarat: rice 38%, groundnut 49%.
- Maharashtra: soybean 48% (June-July rain), bajra 50%, maize 51%.
- Madhya Pradesh is the weakest rain-fed state: 56-70%, and maize 70% against 75% naive.

## IN-3.2 Basis risk vs district size (`in_trigger_eval_size`)

Season rain, 20% nominal pay frequency, 85% rule:

| District area | Districts × crops | Miss rate | False-alarm rate |
|---|---|---|---|
| < 2,000 km² | 211 | 71.9% | 23.8% |
| 2,000-5,000 km² | 739 | 66.6% | 22.4% |
| 5,000-10,000 km² | 460 | 63.1% | 19.1% |
| >= 10,000 km² | 197 | 62.8% | 17.9% |

By cells per district, the miss rate is 73.5% with 1-2 cells, 68.2% with 3-5, 63.1% with 6-10 and 63.1% with more than 10.

Small districts have the worst basis risk. This is the grid's version of the US station-distance result: a district covered by one or two 0.25° cells takes its rain from interpolated values that may sit outside the district, and averaging over more cells reduces that noise. Large districts average over more cells and fit better. The gain stops at about 6 cells. Block-level WINDS stations would matter most for the smallest districts.

## IN-4.1 Pricing (`in_premium_district`, `in_premium_state`), % of sum insured

| Crop | Districts priced | Payout frequency | Weather-trigger premium | PMFBY-style indemnity cost (80%) | Farmer cap | Implied subsidy (trigger) | Share of PMFBY shortfall the trigger paid |
|---|---|---|---|---|---|---|---|
| Bajra | 231 | 27.3% | 8.53% | 5.81% | 2% | 6.53 pts | 32.2% |
| Cotton (lint) | 198 | 28.6% | 8.93% | 8.54% | 5% | 3.93 pts | 24.5% |
| Groundnut | 270 | 28.0% | 8.74% | 5.69% | 2% | 6.74 pts | 41.7% |
| Maize | 360 | 26.2% | 8.20% | 5.84% | 2% | 6.20 pts | 28.9% |
| Rice | 335 | 26.1% | 8.17% | 3.32% | 2% | 6.17 pts | 42.4% |
| Soybean | 161 | 27.0% | 8.43% | 10.07% | 2% | 6.43 pts | 26.9% |

Second-method check (in notebook 22): for every district, burn rate = payout frequency × 25% payout share, with 25% loading on top.

What this means:

1. A weather trigger of this design costs 8-9% of the sum insured. That is 4-7 times the farmer's 2% Kharif cap, so as under PMFBY, most of the premium would be government subsidy.
2. All-India, the trigger costs less than the yield indemnity on the same districts only for soybean (8.4% vs 10.1%). In the six rain-fed states it is also cheaper for cotton (9.1% vs 10.3%) and maize (8.4% vs 9.2%); soybean there is 8.5% vs 12.1%. For rice and groundnut the trigger costs more than the indemnity it partly replaces.
3. Basis risk in money: the trigger paid 25-42% of the shortfall a PMFBY-style policy would have paid. It is a fast top-up, not a replacement for yield insurance.

## Caveats (same as the US build, plus India-specific)

- Thresholds are in-sample percentiles, so miss rates are optimistic.
- One June-September window is used for all states; plan item A3 (per-state windows) is not applied yet.
- The weather is gridded and interpolated from gauges, so it is smoother than any farm.
- District yields stand in for PMFBY insurance-unit yields.
- 96 DES districts (8.4% of yield rows) are not yet matched to a boundary; the alias table (A7) is pending.
- Rates are a share of the sum insured. Rupee figures need the scale of finance or MSP (item D8).

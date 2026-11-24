# India expansion: action plan (Sprint 7 onward)

**Question carried over from the US project:** for each Indian district, which weather trigger best matches real Kharif yield losses, how often does it fail the farmer (basis risk), and what premium does it imply?

**Why India is a good fit:** India already sells weather-index insurance. The Restructured Weather Based Crop Insurance Scheme (RWBCIS) pays when rainfall, dry spells or temperature measured at notified weather stations cross term-sheet thresholds. Its own guidelines use dry spells with "dry day" = rainfall ≤ 2.5 mm. PMFBY, the yield-based scheme, caps the farmer's premium at 2% of sum insured for Kharif food and oilseed crops, 1.5% for Rabi and 5% for commercial crops; Centre and State share the rest 50:50 (PIB backgrounder, 29 Aug 2026; PMFBY Operational Guidelines 2023, section 13). This project can test RWBCIS-style triggers against 26 years of district yields, which the scheme itself does not publish.

## 1. What changes from the US build

| Piece | United States (done) | India | Why |
|---|---|---|---|
| Weather | GHCN station data, nearest usable station within 30 km | **IMD gridded rainfall 0.25° and temperature 1.0°**, cells inside each district | GHCN holds 3,807 Indian station IDs but only ~143 report each year, and their rainfall rows equal ~43 stations reporting daily (queried 24 Nov 2026), against ~780 districts |
| Yield | USDA NASS county yields | **DES district Area-Production-Yield, Kharif, 1997–2022** | Official district series from the Ministry of Agriculture |
| Unit | County (FIPS) | District (renamed and split over time) | Needs a name crosswalk |
| Crops | Corn, soybeans | Rice, soybean, cotton, groundnut, bajra, maize | Main rain-fed Kharif crops |
| Season | April–September | June–September monsoon (Kharif) | |
| Basis risk driver | Distance to station | **Grid resolution and district size**; later, distance to an IMD/AWS station | No station distance when using a grid |
| Price | USD 4.50/bu corn (illustrative) | Minimum Support Price (MSP) per quintal, CACP notification for each year | To be sourced per crop and year |
| Benchmark | None | Compare the best trigger with PMFBY's 2% farmer premium cap | Direct business comparison |

## 2. Data to download (all checked on 24 Nov 2026)

| # | Dataset | Source and access | Licence / terms | Size | Status |
|---|---|---|---|---|---|
| D1 | IMD daily gridded rainfall, 0.25°, 1990–2025 | POST `https://www.imdpune.gov.in/cmpg/Griddata/rainfall.php`, field `rain=<year>` | Government of India data; credit IMD Pune (Pai et al., 2014) | ~25 MB per year, ~0.9 GB for 36 years | Endpoint works; ingest notebook 16 written and on test |
| D2 | IMD daily max/min temperature, 1.0°, 1990–2025 | `maxtemp.php` and `mintemp.php`, fields `maxtemp`, `mintemp` | As above | ~1.4 MB per year each | Same notebook |
| D3 | District Kharif area, production, yield, 1997–2022, six crops | `data.desagri.gov.in` APY report (token form; Excel/HTML) | DES, MoA&FW; public | ~40 KB per state-crop | Fetch script `scripts/fetch_des_yields.py` works; run must be local (portal's TLS chain is incomplete for Python) |
| D4 | District boundaries (ADM2, 736 units) and states (ADM1) | geoBoundaries gbOpen IND, GeoJSON on GitHub | ODbL 1.0 (attribute geoBoundaries; source lgdirectory.gov.in) | ~30 MB | Reachable |
| D5 | Fallback boundaries | datameet/maps (GitHub) | MIT | | Reachable |
| D6 | Point weather cross-check | NASA POWER daily API (no key) | NASA open data | small | Reachable |
| D7 | Station check | GHCN-Daily India (already in `ghcn_daily`) | CC0 | already loaded | ~143 stations a year |
| D8 | MSP per crop and year | CACP / PIB press releases | Government of India | small table, typed in | To collect |
| — | ICRISAT District Level Database | `data.icrisat.org/dld` | registration | | **Not reachable** (timed out 24 Nov); not needed while D3 works |

Python packages: none new on Databricks (numpy, pandas, requests are present; point-in-polygon uses `matplotlib.path`). `imdlib` (MIT) was read only to confirm the IMD file layout.

## 3. Backlog (epic E8, India pilot)

| ID | Story | Acceptance criteria | Pts | Owner (proposed) |
|---|---|---|---|---|
| IN-1.1 | IMD grids in Delta | `imd_rain_daily`, `imd_temp_daily` for 1990–2025; numpy and Spark June–September means agree within 1 mm | 5 | cprashanth666666-sys |
| IN-1.2 | District yields in Delta | `in_district_yields` for six crops, 1997–2022; row count re-checked against the CSV | 3 | shwetha123920 |
| IN-1.3 | District boundaries and grid mapping | `in_district_cells`: every 0.25° land cell assigned to one district; ≥ 95% of yield districts matched to a boundary by name | 5 | shwetha123920 |
| IN-2.1 | Kharif weather features | Per district-year: June–September rainfall, rainfall deficit vs district normal, longest dry spell (≤ 2.5 mm), monsoon onset delay, days > 35 °C | 5 | Reva-Pradeep |
| IN-2.2 | Losses | Detrend district yields; loss = below 85% of trend. Also flag the PMFBY definition: yield below the threshold yield = average of the best 5 of the previous 7 years × indemnity level (70%, 80% or 90%) | 3 | Reva-Pradeep |
| IN-3.1 | Triggers and basis risk | Reuse notebook 11 logic; miss and false-alarm rates per district, crop and index; best trigger per state | 5 | IshwaryaLaksh |
| IN-3.2 | Basis risk vs district size | Miss rate by district area band and by cells per district | 3 | IshwaryaLaksh |
| IN-4.1 | Pricing | Burn-cost premium in INR using MSP; compare with the 2% farmer cap | 3 | Ashishshri10 |
| IN-4.2 | Dashboard page | India page: district map of basis risk, premium, best trigger | 3 | Ashishshri10 |
| IN-5.1 | Validation | Extend notebook 15 to the India tables | 2 | cprashanth666666-sys |

Total: 37 points, about two one-week sprints. Start after the final report (27 Nov) so the graded deliverables are not put at risk.

## 4. Order of work

1. **Sprint 7, week 1:** IN-1.1, IN-1.2, IN-1.3 (data in place), then IN-2.1.
2. **Sprint 7, week 2:** IN-2.2, IN-3.1, IN-3.2.
3. **Sprint 8:** IN-4.1, IN-4.2, IN-5.1, write-up.

## 5. Risks

| Risk | Mitigation |
|---|---|
| District names change and districts split (e.g. Ahmednagar renamed Ahilyanagar; many new districts after 2011) | Name crosswalk with fuzzy matching inside each state; keep parent-district yields only for years before a split; report the unmatched share |
| DES tables have gaps and outliers (yield 0 or implausible jumps) | Drop zero-area rows; flag yields beyond 5× the district median; require ≥ 15 years per district-crop as in the US build |
| Irrigation hides rainfall stress (Punjab, Haryana rice) | Report results by state; focus on rain-fed states first (Maharashtra, Madhya Pradesh, Rajasthan, Gujarat, Karnataka, Telangana) |
| IMD grid is interpolated from gauges, smoothing local extremes | It is still the reference product for India; cross-check a sample with GHCN stations and NASA POWER |
| DES portal is a session form, not an API | Polite fetch script (1 s between calls), saved CSV committed as a Volume file, not refetched each run |
| Free Edition quota | 36 years × ~1.8 million rain rows a year ≈ 65 million rows; partition by year and load in batches |

## 6. How to adapt the project to the Indian context (research, 24 Nov 2026)

### What Indian evidence says

1. **Basis risk drives farmer demand in India.** In a field experiment with 361 farmers in Maharashtra, telling farmers about basis risk sharply lowered their willingness to buy weather index insurance, and a premium subsidy only partly offset it (Gaurav, 2020, *Climate Risk Management* 27, 100201). Our miss-rate measure is therefore the number farmers actually respond to, so it should be published per district, not hidden.
2. **RWBCIS problems are design problems.** Commentary on the scheme names thin weather coverage, spatial mismatch between station and farm, and poorly calibrated thresholds and payouts. It argues for better index design, not abandoning the parametric approach (The Policy Edge, "India's RWBCIS needs better weather triggers"). That is exactly what notebooks 11 and 13 test.
3. **Hyper-local station data is coming, but is not open yet.** WINDS (Weather Information Network and Data System) is building automatic weather stations at block level and rain gauges at gram-panchayat level for crop insurance. As of the 2 Sep 2026 PIB release, it is in 7 states, with 16,843 sites approved, 892 installed. Until that data is published, the IMD 0.25° grid is the best open source. When WINDS data opens, our distance-based basis-risk method from the US project applies directly.
4. **Yield measurement is moving to technology.** YES-TECH blends remote-sensing yield estimates with crop-cutting experiments: at least 30% weight for paddy and wheat from Kharif 2023 and soybean from Kharif 2024, up to 50% in some states (PIB, Aug–Sep 2026). A later version could use satellite yields to get below district level.

### Design changes this implies

| # | Change | Why it matters in India | Where in the code |
|---|---|---|---|
| A1 | **RWBCIS-style indices**, not one season total: deficit rainfall by crop phase, consecutive dry days (dry day ≤ 2.5 mm, as in the RWBCIS term-sheet example), **excess rainfall**, and heat | Losses come from too much rain as well as too little; RWBCIS covers both | New India features notebook (IN-2.1), reusing 08 and 09 |
| A2 | **Two loss definitions** side by side: 85% of trend (our US rule) and PMFBY threshold yield (best 5 of 7 years × indemnity level) | Lets an insurer compare a weather trigger directly with the scheme it would replace | IN-2.2 |
| A3 | **Configurable season windows per state and crop** (Kharif sowing ranges from late May in Kerala to July in Rajasthan) | One June–September window would misplace the critical phase | One config table read by every India notebook |
| A4 | **Price in INR from MSP**, sum insured per hectare, and premium compared with the 2% farmer cap | Shows whether a fair premium is above or below what farmers pay today | IN-4.1 |
| A5 | **Basis risk by district size and grid cells**, then by station distance once WINDS opens | Without open station data, coarse spatial averaging is the main source of mismatch | IN-3.2 |
| A6 | **Split rain-fed from irrigated districts** (start with Maharashtra, Madhya Pradesh, Rajasthan, Gujarat, Karnataka, Telangana) | Irrigation hides rainfall stress, so triggers will look worse in Punjab and Haryana for reasons unrelated to design | State filter in the config |
| A7 | **District crosswalk with an alias table** for renamed and split districts | 91.6% of yield rows match boundaries automatically; new districts (e.g. Andhra Pradesh 2022) need manual aliases | Notebook 18 |
| A8 | **Data governance**: aggregate data only (district yields, gridded weather); no farmer-level PMFBY records, which fall under the Digital Personal Data Protection Act, 2023 | Keeps the project free of personal data, as in the US build | Governance note |

### Making the code work for both countries

Keep one pipeline and move everything country-specific into a config table: `country, unit (county/district), weather source (station/grid), season window by state and crop, loss rule, currency, price table, premium cap`. Notebooks 10, 11 and 13 already read their thresholds from constants at the top; moving those constants into the table lets the same trigger-scoring and pricing code run for the US and India, and later for any country with a gridded weather product and sub-national yields.

## 7. Progress (24 Nov 2026)

| Story | Status | Notebook | Result |
|---|---|---|---|
| IN-1.1 | Done | 16 | 36 years of IMD rain (65.3 million cell-days) and temperature; numpy and Spark June-September means agree |
| IN-1.2 | Done | 17 + `scripts/fetch_des_yields.py` | 52,149 DES rows, six crops, 1997-2022 |
| IN-1.3 | Done (alias table pending) | 18 | 735 districts; 91.6% of yield rows matched to a boundary |
| IN-2.1 | Done | 19 | 26,460 district-years; driest years 2002 and 2009 match IMD's droughts |
| IN-2.2 | Done | 20 | Losses 17-29% of district-years (85% rule); PMFBY 70/80/90% flags |
| IN-3.1 | Done | 21 | Best trigger per state: 57% miss rate vs 73% naive; season rain best in rain-fed states (62% vs 69% elsewhere) |
| IN-3.2 | Done | 21 | Miss rate falls from 72% (< 2,000 km2) to 63% (>= 10,000 km2) |
| IN-4.1 | Done in % of sum insured (INR pending D8) | 22 | Trigger premium 8-9% of SI vs 2% farmer cap; pays 25-42% of a PMFBY-style shortfall |
| IN-4.2 | To do | | Dashboard page |
| IN-5.1 | To do | | Extend notebook 15 |

32 of 37 points are done. Results and checks: [docs/report/india_results_24nov.md](report/india_results_24nov.md).

Next: A3 (per-state season windows), A7 (district alias table), D8 (MSP to convert rates to INR), out-of-sample thresholds, then IN-4.2 and IN-5.1.

# Big Data Analytics on NOAA GHCN-Daily (Databricks)

Climate analytics on 263 million daily weather observations, processed with PySpark on Databricks.

## Dataset

- **Source:** NOAA Global Historical Climatology Network – Daily, via AWS Open Data: https://registry.opendata.aws/noaa-ghcn/
- **Files used:** `s3://noaa-ghcn-pds/csv/by_year/2019.csv` … `2025.csv`, plus `ghcnd-stations.txt`
- **Access:** public, no API key
- **Raw size:** 9.47 GB of CSV (7 years)

| Table | Contents | Rows |
|---|---|---|
| `workspace.default.ghcn_daily` | One row per station, day and element, partitioned by `year` | 263,437,568 |
| `workspace.default.ghcn_stations` | Station ID, latitude, longitude, elevation, state, name, country | 133,041 |

Units in `ghcn_daily.value` depend on `element`: `TMAX`/`TMIN`/`TAVG` are tenths of °C and `PRCP` is tenths of mm. A non-null `q_flag` means the value failed NOAA's quality checks.

### Second dataset: crop yields

- **Source:** USDA NASS Quick Stats bulk crops file, https://www.nass.usda.gov/datasets/ (no key), plus US Census 2024 county gazetteer for county centroids
- **Volume:** `/Volumes/workspace/default/agri_yield`

| Table | Contents | Rows |
|---|---|---|
| `workspace.default.nass_crops_raw` | Full crops file as published | 23,948,579 |
| `workspace.default.nass_county_yields` | Annual county survey yields, numeric only | 2,219,339 |
| `workspace.default.us_counties` | County FIPS, name, centroid latitude/longitude | 3,222 |

Project plan: [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md)  
Team, task ownership and progress: [docs/TEAM_PROGRESS.md](docs/TEAM_PROGRESS.md) | [Project board](https://github.com/users/cprashanth666666-sys/projects/1)

## Notebooks

| Notebook | Purpose |
|---|---|
| `databricks/00_connectivity_check.py` | Confirms the workspace can reach the public endpoints |
| `databricks/01_ingest_noaa_ghcn.py` | Downloads 2019–2025 into a Unity Catalog Volume and writes the Delta tables |
| `databricks/02_ingest_nass_yields.py` | Downloads NASS crops and county centroids into the `agri_yield` Volume and writes the Delta tables |
| `databricks/03_extend_ghcn_history.py` | Sprint 1 (1.3): appends US PRCP/TMAX/TMIN for 2000–2018 to `ghcn_daily` |
| `databricks/04_data_quality_report.py` | Sprint 1 (1.4): writes `dq_report` (null rates, QC share, station coverage, yield suppression) |
| `databricks/05_county_nearest_stations.py` | Sprint 1 (2.1): writes `county_station_links` (10 nearest stations per county, haversine km) |
| `databricks/06_usable_stations.py` | Sprint 2 (2.2): writes `station_year_quality` (station-years with >=90% growing-season PRCP and TMAX) |
| `databricks/07_county_coverage.py` | Sprint 2 (2.3): writes `county_year_station` and `county_coverage_gaps` |
| `databricks/08_weather_features.py` | Sprint 2 (3.1, 3.2): writes Gold table `county_year_weather_features` (season rainfall, driest 30 days, heat-stress days) |
| `databricks/09_dry_spell.py` | Sprint 3 (3.3): writes `county_year_dry_spell` (longest run of days with PRCP < 1 mm, April-September) |
| `databricks/10_yield_trend_losses.py` | Sprint 3 (4.1, 4.2): writes `county_yield_trend` (per-county linear trend, % of trend, loss flag below 85%) |
| `databricks/11_trigger_basis_risk.py` | Sprint 4 (5.1-5.3): writes `trigger_eval_county`, `trigger_eval_dist_band` and `best_trigger_region` (hit/miss/false alarm, basis risk = miss rate, best trigger per state and crop) |
| `databricks/12_station_correlation_distance.py` | Sprint 5 (5.4): writes `station_pair_corr` and `corr_distance_curve` (how weather similarity between stations falls with distance) |
| `databricks/13_pricing_portfolio.py` | Sprint 5 (6.1, 6.2): writes `premium_county`, `portfolio_year`, `portfolio_summary` (burn-cost premium, worst-year payout) |
| `databricks/14_dashboard_views.py` | Story 7.1: creates the `v_*` views the Databricks SQL dashboard reads; layout in [docs/DASHBOARD.md](docs/DASHBOARD.md) |
| `databricks/15_validate_pipeline.py` | Runs last: checks every module's table (row counts and content rules) and writes `pipeline_validation`; 46 of 46 checks passed on 16 Nov 2026 |

### India pilot (started 24 Nov 2026, beyond the Checkpoint 4 scope)

Plan, data sources and design changes for India: [docs/INDIA_EXPANSION_PLAN.md](docs/INDIA_EXPANSION_PLAN.md)

| Notebook / script | Purpose |
|---|---|
| `databricks/16_india_ingest_imd_grids.py` | IMD gridded daily rainfall (0.25 deg) and max/min temperature (1.0 deg), 1990-2025, into `imd_rain_daily` and `imd_temp_daily` |
| `scripts/fetch_des_yields.py` | Run locally: district Kharif area, production and yield for six crops, 1997-2022, from the DES APY portal |
| `databricks/17_india_district_yields.py` | Loads the DES file into `in_des_apy_raw` and the cleaned `in_district_yields` |
| `databricks/18_india_district_cells.py` | geoBoundaries districts, IMD cell-to-district mapping, and the DES-to-boundary name crosswalk (`in_districts`, `in_district_cells`, `in_district_xwalk`) |
| `databricks/19_india_kharif_features.py` | IN-2.1: `in_district_year_weather` (June-September rain, phase rain, deficit, longest dry spell at <= 2.5 mm, onset delay, 3-day maximum, heat days) |
| `databricks/20_india_yield_losses.py` | IN-2.2: `in_district_yield_trend` (85%-of-trend loss flag and the PMFBY best-5-of-7 threshold at 70/80/90%) |
| `databricks/21_india_trigger_basis_risk.py` | IN-3.1, IN-3.2: `in_trigger_eval_district`, `in_best_trigger_state`, `in_trigger_eval_size` (basis risk per district, best trigger per state, basis risk by district size) |
| `databricks/22_india_pricing.py` | IN-4.1: `in_premium_district`, `in_premium_state` (trigger premium as % of sum insured vs the PMFBY farmer cap and a PMFBY-style indemnity cost) |

## Checkpoint status and reports

- Checkpoint 3 write-up (Agile approach): [docs/Checkpoint3_Agile_Writeup.docx](docs/Checkpoint3_Agile_Writeup.docx)
- Checkpoint 4 (24 Nov 2026): [docs/T04_CP4_Pipeline_Dashboard_Report.docx](docs/T04_CP4_Pipeline_Dashboard_Report.docx): build audit, Gold-table results, evaluation metrics, team progress, burndown, work plan and governance note. Results and their second-method checks: [docs/report/results_24nov.md](docs/report/results_24nov.md)
- Final report draft (due 27 Nov): [docs/T04_Final_Report.docx](docs/T04_Final_Report.docx); only the members' after-project skill ratings remain to be filled
- Dashboard (story 7.1): SQL views built and validated (notebook 14); layout in [docs/DASHBOARD.md](docs/DASHBOARD.md); assembly in the Databricks UI is in progress
- Notebook exports for submission (.ipynb, exported from the Databricks workspace): [notebooks_ipynb/](notebooks_ipynb/)
- Team, owners and progress: [docs/TEAM_PROGRESS.md](docs/TEAM_PROGRESS.md)

The notebooks use Databricks source format. To run one from this machine with the Databricks CLI:

```bash
databricks workspace import /Users/<you>/bigdata/01_ingest_noaa_ghcn --file databricks/01_ingest_noaa_ghcn.py --language PYTHON --format SOURCE --overwrite
```

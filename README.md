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

Checkpoint 3 write-up (Agile approach): [docs/Checkpoint3_Agile_Writeup.docx](docs/Checkpoint3_Agile_Writeup.docx)

The notebooks use Databricks source format. To run one from this machine with the Databricks CLI:

```bash
databricks workspace import /Users/<you>/bigdata/01_ingest_noaa_ghcn --file databricks/01_ingest_noaa_ghcn.py --language PYTHON --format SOURCE --overwrite
```

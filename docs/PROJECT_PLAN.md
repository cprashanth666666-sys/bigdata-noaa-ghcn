# Project Plan: Parametric Weather Insurance with Basis-Risk Analysis

## 1. Product vision

**For** crop insurers and agricultural lenders in the US Corn Belt,
**who** need payouts that are fast and objective,
**we build** a parametric insurance design engine on Databricks
**that** turns 263M+ weather observations and county crop yields into payout triggers, basis-risk scores and premiums,
**unlike** "drought risk maps", which never test whether a trigger would have paid the farmers who actually lost.

**Core question:** For each county, which weather trigger best matches real yield losses, how often does it fail the farmer (basis risk), and what premium does it imply?

## 2. Data

| Layer | Table | Source | Status |
|---|---|---|---|
| Bronze | `workspace.default.ghcn_daily` | NOAA GHCN-Daily 2019–2025, 9.47 GB raw CSV, 263.4M rows | Loaded |
| Bronze | `workspace.default.ghcn_stations` | NOAA station list (133,041 stations) | Loaded |
| Bronze | `workspace.default.nass_crops_raw` | USDA NASS Quick Stats crops bulk file (1.13 GB gzip), 23.9M rows | Loaded |
| Silver | `workspace.default.nass_county_yields` | County annual survey yields, 2.22M rows (34,676 for 2019–2025) | Loaded |
| Silver | `workspace.default.us_counties` | US Census 2024 county gazetteer, 3,222 counties with centroids | Loaded |

Coverage for 2019–2025: corn grain yields in 1,902 counties (9,816 county-years), soybeans in 1,673 counties. 461 corn counties are in the five Corn Belt states. All 2,271 counties with yields matched a centroid.

Raw files live in two Volumes: `bigdata` (weather) and `agri_yield` (crops and counties).

Architecture is medallion: **Bronze** (raw as published) → **Silver** (cleaned, joined, quality-filtered) → **Gold** (county-year features, triggers, prices).

## 3. Team and ceremonies

| Role | Responsibility |
|---|---|
| Product Owner | Owns the backlog and acceptance; plays the "insurer" stakeholder |
| Scrum Master | Runs ceremonies and removes blockers |
| Developers | Build notebooks, tests and dashboards |

For a small academic team, one person can hold two roles; state who holds which in the report.

- **Sprint length:** 1 week.
- **Planning** (Monday, 30 min): pick stories from the top of the backlog.
- **Daily stand-up** (10 min, async is fine): done, doing, blocked.
- **Review** (Friday): demo a working notebook or dashboard against acceptance criteria.
- **Retrospective** (Friday, 15 min): one thing to keep, one to change.
- **Board:** GitHub Projects with columns Backlog → Sprint → In progress → Review → Done. One issue per story; branch per story off `prashbigdata`.

## 4. Definition of Done

A story is done only when:
1. The notebook runs end to end on Databricks serverless without manual steps.
2. Output tables are written as Delta with a documented schema.
3. Row counts and key figures are re-checked with a second method (e.g. SQL warehouse vs notebook).
4. The code is committed, pushed and merged to `prashbigdata` with the issue closed.
5. Any assumption (threshold, season window, distance cut-off) is written down in the notebook header.

## 5. Product backlog (epics and stories)

Priority: **M** = must, **S** = should, **C** = could. Points use a 1/2/3/5/8 scale.

### E1. Data foundation
| ID | Story | Acceptance criteria | Pri | Pts |
|---|---|---|---|---|
| 1.1 | As an analyst, I want GHCN-Daily in Delta so I can query weather at scale | `ghcn_daily` and `ghcn_stations` exist; counts re-verified | M | 3 ✅ |
| 1.2 | As an analyst, I want county yields and county centroids in Delta | `nass_county_yields`, `us_counties` exist; ≥95% of yield counties match a centroid | M | 3 ✅ |
| 1.3 | As an actuary, I want 20+ years of weather so loss events are not too rare | GHCN extended back to at least 2000; per-year counts reported | M | 3 ✅ |
| 1.4 | As a reviewer, I want a data-quality report | Null rates, QC-flag share, station coverage by state, yield suppression `(D)` share | S | 2 ✅ |

### E2. Spatial linking
| ID | Story | Acceptance criteria | Pri | Pts |
|---|---|---|---|---|
| 2.1 | As an analyst, I want each county linked to its nearest stations | Table of county → k nearest stations with haversine distance (km) | M | 5 ✅ |
| 2.2 | As an analyst, I want only stations with usable data | Station kept only if ≥90% of growing-season days have `PRCP` and `TMAX` | M | 3 |
| 2.3 | As a risk manager, I want to know which counties lack a nearby station | Map/list of counties with no qualifying station within 30 km | S | 2 |

### E3. Weather index features (Gold)
| ID | Story | Acceptance criteria | Pri | Pts |
|---|---|---|---|---|
| 3.1 | As an actuary, I want growing-season rainfall per county-year | April–September total `PRCP` (mm), plus 30-day rolling minimum | M | 5 |
| 3.2 | As an actuary, I want heat-stress counts per county-year | Days with `TMAX` > 30 °C and > 35 °C in July–August | M | 3 |
| 3.3 | As an actuary, I want dry-spell length | Longest run of days with `PRCP` < 1 mm in the growing season | S | 5 |

### E4. Loss definition
| ID | Story | Acceptance criteria | Pri | Pts |
|---|---|---|---|---|
| 4.1 | As an actuary, I want yields detrended per county | Linear trend per county and crop; residual and % deviation stored | M | 5 |
| 4.2 | As an insurer, I want a clear loss event | Loss = yield below 85% of trend (threshold configurable); share of loss years reported | M | 2 |

### E5. Trigger design and basis risk
| ID | Story | Acceptance criteria | Pri | Pts |
|---|---|---|---|---|
| 5.1 | As an insurer, I want candidate triggers evaluated against losses | Confusion matrix per trigger: hit, miss (loss, no payout), false alarm | M | 5 |
| 5.2 | As an insurer, I want basis risk quantified | Basis risk = miss rate; reported by county and by station distance band | M | 5 |
| 5.3 | As a product designer, I want the best trigger per region | Trigger chosen by lowest miss rate subject to a false-alarm cap; documented | M | 3 |
| 5.4 | As a risk manager, I want to see how distance drives basis risk | Station-pair correlation vs distance curve | S | 5 |

### E6. Pricing
| ID | Story | Acceptance criteria | Pri | Pts |
|---|---|---|---|---|
| 6.1 | As an actuary, I want a burn-cost premium | Historic payout frequency × payout per county; loading factor stated | M | 3 |
| 6.2 | As an insurer, I want a portfolio view | Expected loss and worst-year payout across all counties | S | 3 |

### E7. Delivery
| ID | Story | Acceptance criteria | Pri | Pts |
|---|---|---|---|---|
| 7.1 | As a stakeholder, I want a dashboard | Databricks SQL dashboard: map of basis risk, premium per county, trigger performance | M | 5 |
| 7.2 | As an examiner, I want a report and viva deck | Problem, data, method, results, limitations, business recommendation | M | 5 |
| 7.3 | As an examiner, I want evidence of big-data engineering | Benchmark of one heavy job with and without partitioning/broadcast join | C | 3 |

## 6. Sprint plan

| Sprint | Goal | Stories |
|---|---|---|
| 0 | Data in place | 1.1 ✅, 1.2 ✅ |
| 1 | Enough history, trustworthy data | 1.3 ✅, 1.4 ✅, 2.1 ✅ |
| 2 | Weather features per county | 2.2, 2.3, 3.1, 3.2 |
| 3 | Losses defined | 3.3, 4.1, 4.2 |
| 4 | Triggers and basis risk | 5.1, 5.2, 5.3 |
| 5 | Pricing and dashboard | 5.4, 6.1, 6.2, 7.1 |
| 6 | Hardening and submission | 7.2, 7.3, buffer for spill-over |

Each sprint ends with a working, demonstrable increment, not just code.

## 7. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Only 7 weather years (2019–2025), so few loss years per county | Trigger stats unreliable | Story 1.3: extend GHCN to 2000+ (raw files exist back to 1763) |
| Many counties have no nearby station with full data | Thin coverage | Focus scope on Corn Belt states (IA, IL, IN, NE, MN) where coverage is dense; report gaps (2.3) |
| NASS suppresses some values as `(D)` and recent years may be incomplete | Missing yields | Exclude non-numeric values; report the share dropped |
| Free Edition compute or storage limits | Jobs fail or slow | Partition by year, filter to target states early, cache only Gold tables |
| Yield losses also come from pests, prices and management, not only weather | Lower trigger hit rates | State it as a limitation; that gap is the basis risk being measured |

## 8. Repository conventions

- `main`: stable, submission-ready. `prashbigdata`: integration branch for sprint work.
- Notebooks are numbered in run order under `databricks/` (`00_`, `01_`, …).
- Each notebook header lists its inputs, outputs and assumptions.

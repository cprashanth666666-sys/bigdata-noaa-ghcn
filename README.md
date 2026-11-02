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

## Notebooks

| Notebook | Purpose |
|---|---|
| `databricks/00_connectivity_check.py` | Confirms the workspace can reach the public endpoints |
| `databricks/01_ingest_noaa_ghcn.py` | Downloads 2019–2025 into a Unity Catalog Volume and writes the Delta tables |

The notebooks use Databricks source format. To run one from this machine with the Databricks CLI:

```bash
databricks workspace import /Users/<you>/bigdata/01_ingest_noaa_ghcn --file databricks/01_ingest_noaa_ghcn.py --language PYTHON --format SOURCE --overwrite
```

# Databricks notebook source
# Checks whether this workspace can reach the public dataset endpoints,
# and whether the built-in samples.tpch fallback is available.
import json
import requests

URLS = {
    "noaa_ghcn": "https://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/2020.csv.gz",
    "commoncrawl_paths": "https://data.commoncrawl.org/crawl-data/CC-MAIN-2025-38/cc-index-table.paths.gz",
    "commoncrawl_index_api": "https://index.commoncrawl.org/collinfo.json",
}

def check(url):
    try:
        return requests.head(url, timeout=20, allow_redirects=True).status_code
    except Exception as e:
        return f"FAILED: {type(e).__name__}: {str(e)[:200]}"

results = {name: check(url) for name, url in URLS.items()}

# COMMAND ----------

try:
    results["samples_tpch_lineitem_rows"] = spark.read.table("samples.tpch.lineitem").count()
except Exception as e:
    results["samples_tpch_lineitem_rows"] = f"FAILED: {str(e)[:200]}"

print(json.dumps(results, indent=2))
dbutils.notebook.exit(json.dumps(results))

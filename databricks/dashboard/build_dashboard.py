"""Story 7.1: build the AI/BI (Lakeview) dashboard definition from the v_* views (notebook 14).

Writes databricks/dashboard/parametric_insurance.lvdash.json. The layout follows docs/DASHBOARD.md:
four pages, each answering one question the insurer would ask. Create or update it in the workspace with
    python databricks/dashboard/build_dashboard.py --deploy
which calls the Databricks CLI (lakeview create/update, then publish on the SQL warehouse).
"""
import argparse, json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "parametric_insurance.lvdash.json")
STATE = os.path.join(HERE, ".dashboard_id")          # local only: id of the deployed dashboard
NAME = "Parametric weather insurance: basis risk and pricing"
WAREHOUSE = "d8487cbf315446a4"
S = "workspace.default"

DATASETS = {
    "basis_risk_map": "v_county_basis_risk", "premium": "v_county_premium", "trigger_perf": "v_trigger_performance",
    "distance_bands": "v_basis_risk_by_distance", "corr_curve": "v_corr_distance", "portfolio_year": "v_portfolio_year",
    "portfolio_summary": "v_portfolio_summary", "coverage": "v_coverage_gaps",
}

# Extra SQL per dataset: the coverage view holds every US county; the study area is the five Corn Belt states.
DATASET_SQL = {
    "coverage": " WHERE state_alpha IN ('IA', 'IL', 'IN', 'NE', 'MN')",
    "basis_risk_map": " ORDER BY miss_rate DESC, false_alarm_rate DESC",
    "premium": " ORDER BY premium_per_acre_usd DESC",
}

# ---------- helpers ----------
_n = [0]


def wid(prefix):
    _n[0] += 1
    return f"{prefix}_{_n[0]}"


def fld(col, agg=None):
    if agg:
        return {"name": f"{agg.lower()}({col})", "expression": f"{agg.upper()}(`{col}`)"}
    return {"name": col, "expression": f"`{col}`"}


def query(ds, fields, disaggregated=False, name="main_query"):
    return {"name": name, "query": {"datasetName": ds, "fields": fields, "disaggregated": disaggregated}}


def frame(title, desc=None):
    f = {"showTitle": True, "title": title}
    if desc:
        f.update(showDescription=True, description=desc)
    return f


def place(widget, x, y, w, h):
    return {"widget": widget, "position": {"x": x, "y": y, "width": w, "height": h}}


def text(lines):
    return {"name": wid("text"), "multilineTextboxSpec": {"lines": [line + "\n\n" for line in lines]}}


def chart(kind, ds, fields, encodings, title, desc=None, disaggregated=False):
    return {"name": wid(kind), "queries": [query(ds, fields, disaggregated)],
            "spec": {"version": 3, "widgetType": kind, "encodings": encodings, "frame": frame(title, desc)}}


def counter(ds, col, title, agg="MAX"):
    f = fld(col, agg)
    return {"name": wid("counter"), "queries": [query(ds, [f])],
            "spec": {"version": 2, "widgetType": "counter",
                     "encodings": {"value": {"fieldName": f["name"], "displayName": title}}, "frame": frame(title)}}


def table(ds, cols, title):
    return {"name": wid("table"), "queries": [query(ds, [fld(c) for c in cols], disaggregated=True)],
            "spec": {"version": 2, "widgetType": "table",
                     "encodings": {"columns": [{"fieldName": c, "displayName": c} for c in cols]}, "frame": frame(title)}}


def point_map(ds, color_col, tooltip, title, desc=None):
    fields = [fld("latitude"), fld("longitude"), fld(color_col)] + [fld(c) for c in tooltip]
    enc = {"coordinates": {"latitude": {"fieldName": "latitude"}, "longitude": {"fieldName": "longitude"}},
           "color": {"fieldName": color_col, "scale": {"type": "quantitative"}, "displayName": color_col},
           "extra": [{"fieldName": c, "displayName": c} for c in tooltip]}
    w = chart("symbol-map", ds, fields, enc, title, desc, disaggregated=True)
    w["spec"]["version"] = 2
    return w


def select_filter(col, title, datasets, multi=False, default=None):
    qs = [query(ds, [fld(col)], name=f"f_{col}_{ds}") for ds in datasets]
    spec = {"version": 2, "widgetType": "filter-multi-select" if multi else "filter-single-select",
            "encodings": {"fields": [{"fieldName": col, "displayName": col, "queryName": q["name"]} for q in qs]},
            "frame": frame(title)}
    if default is not None:
        spec["selection"] = {"defaultSelection": {"values": {"dataType": "STRING", "values": [{"value": default}]}}}
    return {"name": wid("filter"), "queries": qs, "spec": spec}


def bar(ds, x, y, title, color=None, agg="AVG", desc=None):
    fields = [fld(x), fld(y, agg)] + ([fld(color)] if color else [])
    enc = {"x": {"fieldName": x, "scale": {"type": "categorical"}, "displayName": x},
           "y": {"fieldName": f"{agg.lower()}({y})", "scale": {"type": "quantitative"}, "displayName": y}}
    if color:
        enc["color"] = {"fieldName": color, "scale": {"type": "categorical"}, "displayName": color}
    w = chart("bar", ds, fields, enc, title, desc)
    if color:
        w["spec"]["mark"] = {"layout": "group"}      # side by side, not stacked: miss rates do not add up
    return w


# ---------- pages (docs/DASHBOARD.md) ----------
def build():
    p1 = [
        place(text(["## Where does the trigger fail farmers?",
                    "Each point is a Corn Belt county under its state's chosen trigger. Darker = higher miss rate "
                    "(share of loss years with no payout = basis risk).",
                    "**Read with care:** thresholds are set from the same years they are tested on, so miss rates are "
                    "optimistic. Each county counts as one insured acre; dollar figures show the shape of the risk, not "
                    "real exposure. Crop prices and the 25% payout share are illustrative (notebook 13)."]), 0, 0, 4, 4),
        place(select_filter("crop", "Crop", ["basis_risk_map", "premium", "trigger_perf", "distance_bands"], default="corn"), 4, 0, 1, 2),
        place(select_filter("state_alpha", "State", ["basis_risk_map", "premium", "coverage"], multi=True), 5, 0, 1, 2),
        place(point_map("basis_risk_map", "miss_rate", ["county_name", "state_alpha", "index_name", "n_loss",
                                                        "false_alarm_rate", "avg_distance_km"],
                        "Basis risk (miss rate) by county"), 0, 4, 3, 8),
        place(point_map("coverage", "share_years_covered", ["county_name", "state_alpha", "years_covered_30km",
                                                            "nearest_usable_km_median"],
                        "Share of years with a usable station within 30 km",
                        "Corn Belt states. Light points = counties the station network leaves uncovered in most years"), 3, 4, 3, 8),
        place(table("basis_risk_map", ["county_name", "state_alpha", "crop", "index_name", "miss_rate",
                                       "false_alarm_rate", "avg_distance_km"], "Counties, worst basis risk first"),
              0, 12, 6, 7),
    ]
    p2 = [
        place(text(["## Which trigger works, and why does distance matter?",
                    "A trigger that paid at random 20% of years would miss about 80% of losses. "
                    "Lower bars are better; in the scatter, the bottom-left is better."]), 0, 0, 5, 2),
        place(select_filter("crop", "Crop", ["trigger_perf", "distance_bands", "portfolio_year"], default="corn"), 5, 0, 1, 2),
        place(bar("trigger_perf", "index_name", "miss_rate", "Miss rate by index and pay frequency", color="pay_freq"), 0, 2, 3, 7),
        place(chart("scatter", "trigger_perf",
                    [fld("false_alarm_rate"), fld("miss_rate"), fld("index_name"), fld("loss_years")],
                    {"x": {"fieldName": "false_alarm_rate", "scale": {"type": "quantitative"}, "displayName": "false_alarm_rate"},
                     "y": {"fieldName": "miss_rate", "scale": {"type": "quantitative"}, "displayName": "miss_rate"},
                     "color": {"fieldName": "index_name", "scale": {"type": "categorical"}, "displayName": "index_name"}},
                    "Miss rate vs false-alarm rate (each point = index x pay frequency)", disaggregated=True), 3, 2, 3, 7),
        place(bar("distance_bands", "dist_band", "miss_rate", "Miss rate by station distance (all pay frequencies)",
                  color="index_name"), 0, 9, 3, 7),
        place(chart("line", "corr_curve", [fld("dist_bin_km"), fld("median_corr_prcp", "AVG"), fld("median_corr_heat", "AVG")],
                    {"x": {"fieldName": "dist_bin_km", "scale": {"type": "quantitative"}, "displayName": "distance (km)"},
                     "y": {"scale": {"type": "quantitative"}, "fields": [
                         {"fieldName": "avg(median_corr_prcp)", "displayName": "rainfall correlation"},
                         {"fieldName": "avg(median_corr_heat)", "displayName": "heat-day correlation"}]}},
                    "Weather similarity between stations vs distance"), 3, 9, 3, 7),
    ]
    p3 = [
        place(text(["## What does cover cost?",
                    "Burn-cost premium = average past payout x 1.25 loading. Sum insured = 85% of trend yield x an "
                    "illustrative price (corn USD 4.50/bu, soybeans USD 11.00/bu)."]), 0, 0, 5, 2),
        place(select_filter("crop", "Crop", ["premium"], default="corn"), 5, 0, 1, 2),
        place(point_map("premium", "premium_per_acre_usd", ["county_name", "state_alpha", "index_name", "premium_rate",
                                                            "payout_freq"], "Premium per acre (USD)"), 0, 2, 3, 8),
        # Counties per 1-point premium-rate band (the built-in histogram drew one bar per distinct value).
        place(chart("bar", "premium",
                    [{"name": "rate_band_pct", "expression": "ROUND(`premium_rate` * 100, 0)"},
                     {"name": "count(*)", "expression": "COUNT(`*`)"}],
                    {"x": {"fieldName": "rate_band_pct", "scale": {"type": "categorical"}, "displayName": "premium rate (%, rounded)"},
                     "y": {"fieldName": "count(*)", "scale": {"type": "quantitative"}, "displayName": "counties"}},
                    "Premium rate distribution (counties per 1-point band)"), 3, 2, 3, 8),
        place(table("premium", ["county_name", "state_alpha", "crop", "index_name", "payout_freq", "premium_rate",
                                "sum_insured_latest", "premium_per_acre_usd", "shortfall_share_paid"], "Premium by county"),
              0, 10, 6, 7),
    ]
    p4 = [
        place(text(["## How bad can a year get for the insurer?",
                    "Totals over all priced counties, one insured acre each. 2012, the Corn Belt drought, is the worst year."]), 0, 0, 5, 2),
        place(select_filter("crop", "Crop", ["portfolio_summary", "portfolio_year"], default="corn"), 5, 0, 1, 2),
        place(counter("portfolio_summary", "expected_annual_payout_usd", "Expected annual payout (USD)"), 0, 2, 2, 3),
        place(counter("portfolio_summary", "worst_payout_usd", "Worst-year payout (USD)"), 2, 2, 1, 3),
        place(counter("portfolio_summary", "worst_year", "Worst year"), 3, 2, 1, 3),
        place(counter("portfolio_summary", "worst_loss_ratio", "Worst-year loss ratio"), 4, 2, 2, 3),
        place(chart("line", "portfolio_year", [fld("year"), fld("payout_usd", "SUM"), fld("premium_usd", "SUM")],
                    {"x": {"fieldName": "year", "scale": {"type": "quantitative"}, "displayName": "year"},
                     "y": {"scale": {"type": "quantitative"}, "fields": [
                         {"fieldName": "sum(payout_usd)", "displayName": "payout (USD)"},
                         {"fieldName": "sum(premium_usd)", "displayName": "premium (USD)"}]}},
                    "Payout vs premium by year"), 0, 5, 6, 7),
        place(bar("portfolio_year", "year", "counties_paid", "Counties paid per year", agg="SUM"), 0, 12, 6, 6),
    ]
    pages = [("p_fail", "1. Where it fails", p1), ("p_trigger", "2. Which trigger", p2),
             ("p_cost", "3. What it costs", p3), ("p_year", "4. Worst year", p4)]
    return {
        "datasets": [{"name": k, "displayName": k, "queryLines": [f"SELECT * FROM {S}.{v}" + DATASET_SQL.get(k, "")]}
                     for k, v in DATASETS.items()],
        "pages": [{"name": n, "displayName": d, "layout": lay, "pageType": "PAGE_TYPE_CANVAS"} for n, d, lay in pages],
    }


def cli(*args, body=None):
    cmd = [shutil.which("databricks"), *args] + (["--json", json.dumps(body)] if body is not None else []) + ["-o", "json"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env={**os.environ, "MSYS_NO_PATHCONV": "1"})
    if r.returncode:
        sys.exit(f"databricks {' '.join(args)} failed:\n{r.stderr}")
    return json.loads(r.stdout or "{}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", action="store_true")
    a = ap.parse_args()
    spec = build()
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)
    print("wrote", OUT, "| widgets:", sum(len(p["layout"]) for p in spec["pages"]))
    if not a.deploy:
        return
    body = {"display_name": NAME, "warehouse_id": WAREHOUSE, "serialized_dashboard": json.dumps(spec)}
    did = open(STATE).read().strip() if os.path.exists(STATE) else None
    if did:
        d = cli("lakeview", "update", did, body=body)
    else:
        me = cli("current-user", "me")["userName"]          # workspace folder: /Users/<you>/bigdata
        d = cli("lakeview", "create", body={**body, "parent_path": f"/Users/{me}/bigdata"})
        did = d["dashboard_id"]
        open(STATE, "w").write(did)
    cli("lakeview", "publish", did, body={"warehouse_id": WAREHOUSE, "embed_credentials": True})
    print("dashboard", did, "published")


if __name__ == "__main__":
    main()

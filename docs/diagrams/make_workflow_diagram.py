"""Notebook-level workflow diagram with the key functions each notebook runs and the table it writes.

Run from this folder:  python make_workflow_diagram.py  ->  workflow_functions.png
Labels were taken from the notebook code in databricks/ (function names, Spark functions, output tables).
Arrows = "reads the output of". ghcn_daily and nass_county_yields are read by many notebooks; that fan-out
is written inside the 01/03 and 02 boxes instead of drawn, to keep the diagram readable.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

NAVY, GREY, GOLD, RED = "#1F3A5F", "#5F5E5A", "#B8860B", "#8B1E1E"
LAYER = {  # fill, edge
    "src": ("#EEF1F5", NAVY), "bronze": ("#F3E6D3", "#8A5A2B"), "silver": ("#E9EBEE", NAVY),
    "feat": ("#F7EEC8", GOLD), "anal": ("#F5E1C8", "#A0522D"), "serve": ("#E6EFE6", "#2F6B3A"),
}
SERIF = "serif"
W, H = 3.35, 2.05
COLX = [1.9, 5.7, 9.5, 13.3, 17.1, 20.9]

# id: (column, y, layer, title, function lines, output line)
N = {
    "S1": (0, 10.0, "src", "NOAA GHCN-Daily", ["AWS Open Data (S3)", "daily station weather", "CC0 public domain"], ""),
    "S2": (0, 6.4, "src", "USDA NASS Quick Stats", ["crops bulk file (1.13 GB)", "county yields since 1910", "US government work"], ""),
    "S3": (0, 3.0, "src", "US Census gazetteer", ["2024 county centroids", "3,222 counties", "open data"], ""),
    "00": (0, 0.6, "src", "00 connectivity_check", ["check(): can the workspace", "reach the public endpoints?"], "pre-flight, no table"),

    "01": (1, 10.0, "bronze", "01 ingest_noaa_ghcn", ["download(): requests.get to Volume", "Delta write, partitionBy(\"year\")", "read later by 04-06, 08, 09, 12"], "ghcn_daily, ghcn_stations"),
    "03": (1, 7.4, "bronze", "03 extend_ghcn_history", ["load_year(): 2000-2018, US only", "already_loaded(): skip done years", "keeps PRCP, TMAX, TMIN"], "appends to ghcn_daily"),
    "02": (1, 3.6, "bronze", "02 ingest_nass_yields", ["download(); filter COUNTY/YIELD/", "SURVEY; try_cast drops \"(D)\"", "read later by 05, 07, 10, 14"], "nass_county_yields, us_counties"),

    "06": (2, 10.6, "silver", "06 usable_stations", ["countDistinct days, Apr-Sep", "usable if PRCP and TMAX", "cover >= 90% of 183 days"], "station_year_quality"),
    "05": (2, 5.2, "silver", "05 county_nearest_stations", ["haversine_km(); F.broadcast", "bounding-box join;", "row_number() keeps 10 nearest"], "county_station_links"),
    "07": (2, 7.9, "silver", "07 county_coverage", ["crossJoin years; row_number()", "nearest usable station;", "30 km cover, percentile_approx"], "county_year_station, _coverage_gaps"),
    "04": (2, 2.2, "silver", "04 data_quality_report", ["null and QC-flag rates,", "station coverage by state,", "NASS \"(D)\" suppressed share"], "dq_report"),

    "08": (3, 9.7, "feat", "08 weather_features", ["season rain sum; 30-day window", "rangeBetween(-29, 0) minimum;", "Jul-Aug days TMAX > 30 / 35 C"], "county_year_weather_features"),
    "09": (3, 7.0, "feat", "09 dry_spell", ["gaps-and-islands:", "datediff - row_number()", "= longest run < 1 mm"], "county_year_dry_spell"),
    "10": (3, 3.6, "feat", "10 yield_trend_losses", ["OLS per county: covar_pop /", "var_pop; loss = yield", "< 0.85 x trend"], "county_yield_trend"),

    "12": (4, 10.6, "anal", "12 station_correlation", ["haversine_km() self-join <= 200 km;", "F.corr() per station pair;", "median per 10 km bin"], "station_pair_corr, corr_distance_curve"),
    "11": (4, 7.0, "anal", "11 trigger_basis_risk", ["index_rows(); percentile thresholds;", "counts()/rates(): hit, miss, false", "alarm; row_number() best per state"], "trigger_eval_*, best_trigger_region"),
    "13": (4, 3.6, "anal", "13 pricing_portfolio", ["burn rate x (1 + loading);", "greatest/least: farmer shortfall;", "row_number() worst year"], "premium_county, portfolio_*"),

    "14": (5, 8.6, "serve", "14 dashboard_views", ["CREATE OR REPLACE VIEW x 8;", "same_count(): no dropped or", "duplicated counties"], "v_* views -> SQL dashboard"),
    "15": (5, 4.6, "serve", "15 validate_pipeline", ["exists(), rows(), check():", "46 checks on every module;", "fails only after all checks run"], "pipeline_validation"),
}
EDGES = [("S1", "01"), ("S1", "03"), ("S2", "02"), ("S3", "02"), ("01", "03"),
         ("01", "06"), ("01", "05"), ("02", "05"), ("02", "04"), ("06", "07"), ("05", "07"),
         ("07", "08"), ("07", "09"), ("02", "10"), ("06", "12"),
         ("08", "11"), ("09", "11"), ("10", "11"), ("11", "13"), ("10", "13"),
         ("12", "14"), ("11", "14"), ("13", "14"), ("14", "15")]   # 14 also reads 07: noted in the footer

fig, ax = plt.subplots(figsize=(23, 13.2), dpi=170)
ax.set_xlim(0, 22.8)
ax.set_ylim(-1.3, 13.3)
ax.axis("off")

# Layer headers
HEAD = ["Public data", "Bronze: ingest", "Silver: clean and link", "Gold: features", "Gold: analytics", "Serve and validate"]
for c, t in enumerate(HEAD):
    ax.text(COLX[c], 12.15, t, ha="center", va="center", fontsize=13, fontweight="bold", color=NAVY, family=SERIF)
ax.text(11.4, 12.95, "Workflow of the parametric weather insurance pipeline: what each Databricks notebook does",
        ha="center", va="center", fontsize=15, fontweight="bold", color=RED, family=SERIF)


def center(k):
    c, y = N[k][0], N[k][1]
    return COLX[c], y


for k, (c, y, layer, title, lines, out) in N.items():
    fill, edge = LAYER[layer]
    x0, y0 = COLX[c] - W / 2, y - H / 2
    ax.add_patch(FancyBboxPatch((x0, y0), W, H, boxstyle="round,pad=0.04,rounding_size=0.15",
                                fc=fill, ec=edge, lw=1.2, zorder=2))
    ax.text(COLX[c], y + H / 2 - 0.28, title, ha="center", va="center", fontsize=10.2,
            fontweight="bold", color=NAVY, family=SERIF, zorder=3)
    for i, line in enumerate(lines):
        ax.text(COLX[c], y + H / 2 - 0.66 - i * 0.33, line, ha="center", va="center", fontsize=8.6,
                color="#222222", family=SERIF, zorder=3)
    if out:
        ax.text(COLX[c], y - H / 2 + 0.24, "-> " + out, ha="center", va="center", fontsize=8.2,
                style="italic", color=edge, family=SERIF, zorder=3)


def head(p_from, p_to):
    ax.add_patch(FancyArrowPatch(p_from, p_to, arrowstyle="-|>", mutation_scale=13, lw=1.0, color=GREY,
                                 zorder=4, shrinkA=0, shrinkB=1))


# Skip-column edges that need a lane clear of the boxes they pass (06 -> 12 runs above 08).
SKIP_Y = {("06", "12"): 11.4}

# Each target gets its own vertical lane in the gap before it, so edges into different boxes never share a lane.
lane_of = {}
for a, b in EDGES:
    if N[a][0] != N[b][0] and b not in lane_of:
        gap = N[b][0]
        used = sum(1 for t in lane_of if N[t][0] == gap)
        lane_of[b] = COLX[gap] - W / 2 - 0.12 - 0.1 * used   # gap is 0.45 wide; up to 3 lanes fit


def arrow(a, b):
    (xa, ya), (xb, yb) = center(a), center(b)
    ca, cb = N[a][0], N[b][0]
    if ca == cb:                                   # same column: straight vertical
        s = 1 if yb > ya else -1
        head((xa, ya + s * H / 2), (xb, yb - s * H / 2))
        return
    # Exit and entry heights: within each box, keep them inside the box's vertical span.
    y_out = ya if abs(ya - yb) < 0.01 else ya + max(-0.75, min(0.75, (yb - ya) * 0.15))
    y_in = yb if abs(ya - yb) < 0.01 else yb + max(-0.75, min(0.75, (ya - yb) * 0.15))
    if cb - ca > 1 and abs(y_out - y_in) < 1.2:    # skip-column edge through a clear horizontal lane
        y_out = y_in = SKIP_Y.get((a, b), y_out)
        head((xa + W / 2, y_out), (xb - W / 2, y_in))
        return
    lane = lane_of[b]
    ax.plot([xa + W / 2, lane, lane], [y_out, y_out, y_in], color=GREY, lw=1.0, zorder=1,
            solid_joinstyle="round")
    head((lane, y_in), (xb - W / 2, y_in))


for a, b in EDGES:
    arrow(a, b)

ax.text(11.4, -1.0, "Arrow = reads the output of (14 also reads 07's coverage gaps). Databricks job runs 06 -> 15; "
        "15 runs even if a step fails. Serverless PySpark and SQL, Delta tables in Unity Catalog.", ha="center", va="center", fontsize=10,
        style="italic", color=GREY, family=SERIF)

plt.savefig("workflow_functions.png", bbox_inches="tight", facecolor="white")
print("wrote workflow_functions.png")

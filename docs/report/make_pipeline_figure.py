"""Figure 1 of the final report: business problem, data and pipeline in one diagram (brief, report item 2).

Run from this folder:  python make_pipeline_figure.py   ->  fig1_pipeline.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

NAVY, GREY, GOLD, RED = "#1F3A5F", "#5F5E5A", "#B8860B", "#8B1E1E"
FILL = {"src": "#EEF1F5", "bronze": "#F3E6D3", "silver": "#E9EBEE", "gold": "#F7EEC8", "out": "#E6EFE6"}
SERIF = {"family": "serif"}

fig, ax = plt.subplots(figsize=(11, 5.2), dpi=200)
ax.set_xlim(0, 110)
ax.set_ylim(0, 52.5)
ax.axis("off")


def box(x, y, w, h, title, lines, fill, edge=NAVY):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.2",
                                fc=fill, ec=edge, lw=1.0))
    ax.text(x + w / 2, y + h - 2.6, title, ha="center", va="center", fontsize=10.5,
            fontweight="bold", color=NAVY, **SERIF)
    for i, line in enumerate(lines):
        ax.text(x + w / 2, y + h - 6.4 - i * 3.3, line, ha="center", va="center", fontsize=8.6,
                color="#222222", **SERIF)


def arrow(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=16,
                                 lw=1.1, color=GREY))


# Business problem banner
ax.add_patch(FancyBboxPatch((2, 41.5), 106, 9.5, boxstyle="round,pad=0.3,rounding_size=1.2",
                            fc="white", ec=RED, lw=1.2))
ax.text(55, 49.0, "Business problem", ha="center", va="center", fontsize=11, fontweight="bold", color=RED, **SERIF)
ax.text(55, 44.6, "Which weather trigger best matches real county yield losses, how often does it miss\n"
                  "the farmer (basis risk), and what premium does it imply?",
        ha="center", va="center", fontsize=9.2, color="#222222", **SERIF)

W, H, Y = 18, 32, 4.5
xs = [2, 24, 46, 68, 90]
box(xs[0], Y, W, H, "Public data", [
    "NOAA GHCN-Daily", "AWS Open Data (S3)", "", "USDA NASS", "Quick Stats yields", "",
    "US Census", "county centroids"], FILL["src"])
box(xs[1], Y, W, H, "Bronze (raw)", [
    "ghcn_daily", "2000-2025, by year", "ghcn_stations", "", "nass_crops_raw", "us_counties",
    "", "notebooks 01-03"], FILL["bronze"])
box(xs[2], Y, W, H, "Silver (clean)", [
    "dq_report", "nass_county_yields", "county_station_links", "station_year_quality",
    "county_year_station", "county_coverage_gaps", "", "notebooks 02, 04-07"], FILL["silver"])
box(xs[3], Y, W, H, "Gold (analyse)", [
    "weather indices", "dry spells", "yield trend, loss flag", "trigger scores",
    "basis risk by distance", "premiums, portfolio", "", "notebooks 08-13"], FILL["gold"], edge=GOLD)
box(xs[4], Y, W, H, "Decision", [
    "SQL dashboard", "(notebook 14 views)", "", "Insurer: trigger,", "basis risk and", "premium per county",
    "", "report and viva"], FILL["out"])

for i in range(4):
    arrow(xs[i] + W + 0.6, Y + H / 2, xs[i + 1] - 0.6, Y + H / 2)

ax.text(55, 1.2, "Databricks Free Edition, serverless PySpark and SQL, Delta tables in Unity Catalog",
        ha="center", va="center", fontsize=8.6, style="italic", color=GREY, **SERIF)

plt.savefig("fig1_pipeline.png", bbox_inches="tight", facecolor="white")
print("wrote fig1_pipeline.png")

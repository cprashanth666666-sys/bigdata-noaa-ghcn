"""Figure: basis risk vs station distance. Numbers are the Gold-table query results of 24 Nov 2026
(trigger_eval_dist_band at pay_freq 0.20, and corr_distance_curve), copied verbatim; see results_24nov.md.
Run from docs/report:  python make_results_figure.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, RED, INK = "#2E62A8", "#C0392B", "#222222"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"], "font.size": 9.5})

bands = ["0-10 km", "10-20 km", "20-30 km"]
# corn, pay_freq 0.20: miss rate by distance band (trigger_eval_dist_band)
heat35 = [0.327, 0.318, 0.324]
rain = [0.531, 0.506, 0.639]
# corr_distance_curve: median station-pair correlation per 10 km bin
dist = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190]
c_prcp = [0.912, 0.858, 0.831, 0.799, 0.777, 0.734, 0.723, 0.698, 0.686, 0.658, 0.652, 0.634, 0.61, 0.606, 0.591, 0.56, 0.562, 0.541, 0.522, 0.524]
c_heat = [0.9, 0.889, 0.885, 0.885, 0.873, 0.875, 0.874, 0.865, 0.861, 0.857, 0.847, 0.847, 0.837, 0.838, 0.833, 0.826, 0.824, 0.822, 0.816, 0.803]

fig, (a, b) = plt.subplots(1, 2, figsize=(7.4, 3.2), dpi=200, gridspec_kw={"width_ratios": [1, 1.25]})
x = range(3); w = 0.36
a.bar([i - w / 2 for i in x], heat35, w, color=RED, edgecolor="white", lw=2, label="Days > 35 °C")
a.bar([i + w / 2 for i in x], rain, w, color=BLUE, edgecolor="white", lw=2, label="Season rainfall")
for i in x:
    a.text(i - w / 2, heat35[i] + 0.01, f"{heat35[i]:.0%}", ha="center", fontsize=8, color=INK)
    a.text(i + w / 2, rain[i] + 0.01, f"{rain[i]:.0%}", ha="center", fontsize=8, color=INK)
a.set_xticks(list(x)); a.set_xticklabels(bands); a.set_ylim(0, 0.75)
a.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
a.set_xlabel("County-to-station distance"); a.set_ylabel("Miss rate (basis risk)")
a.set_title("(a) Corn miss rate, trigger pays 1 year in 5", fontsize=9.5)
a.legend(fontsize=7.5, frameon=False, loc="upper left")

b.plot(dist, c_prcp, color=BLUE, lw=2, marker="o", ms=3, label="Rainfall")
b.plot(dist, c_heat, color=RED, lw=2, marker="o", ms=3, label="Heat days")
b.axvspan(0, 30, color="#EEEEEE", zorder=0); b.text(15, 0.53, "insured\nrange", ha="center", fontsize=7.5, color=INK)
b.text(190, c_prcp[-1] - 0.04, "Rainfall", ha="right", fontsize=8, color=INK)
b.text(190, c_heat[-1] + 0.02, "Heat days", ha="right", fontsize=8, color=INK)
b.set_ylim(0.5, 0.95); b.set_xlabel("Distance between station pairs (km)"); b.set_ylabel("Median correlation")
b.set_title("(b) Weather similarity falls with distance", fontsize=9.5)
for ax in (a, b):
    ax.spines[["top", "right"]].set_visible(False); ax.grid(axis="y", color="#E5E5E5", lw=0.6); ax.set_axisbelow(True)
fig.tight_layout(); fig.savefig("fig2_distance.png"); plt.close(fig)
print("wrote fig2_distance.png")

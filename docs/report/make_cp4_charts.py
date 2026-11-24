"""Checkpoint 4 charts: sprint burndown and progress by team member.

Every number comes from docs/PROJECT_PLAN.md (story points) and the git history
(dates each story's notebook was committed); see STORIES below. Run from docs/report:
    python make_cp4_charts.py
"""
from datetime import date, timedelta
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

BLUE, RED, GOLD, GREY, INK = "#2E62A8", "#C0392B", "#B07D00", "#9A9A9A", "#222222"
plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                     "font.size": 10, "axes.edgecolor": "#888888", "axes.labelcolor": INK})

# story: (points, owner, date code committed, date run-verified on Databricks (DoD))
# Commit dates from `git log`; DoD date = 16 Nov for notebooks 06-14 (validation notebook 15, 46/46).
STORIES = {
    "1.1": (3, "C. Prashanth", date(2026, 11, 3), date(2026, 11, 3)),
    "1.2": (3, "C. Prashanth", date(2026, 11, 3), date(2026, 11, 3)),
    "1.3": (3, "C. Prashanth", date(2026, 11, 5), date(2026, 11, 5)),
    "1.4": (2, "C. Prashanth", date(2026, 11, 5), date(2026, 11, 5)),
    "2.1": (5, "Shwetha", date(2026, 11, 5), date(2026, 11, 5)),
    "2.2": (3, "Shwetha", date(2026, 11, 7), date(2026, 11, 16)),
    "2.3": (2, "Shwetha", date(2026, 11, 7), date(2026, 11, 16)),
    "3.1": (5, "Reva", date(2026, 11, 7), date(2026, 11, 16)),
    "3.2": (3, "Reva", date(2026, 11, 7), date(2026, 11, 16)),
    "3.3": (5, "Reva", date(2026, 11, 16), date(2026, 11, 16)),
    "4.1": (5, "Shwetha", date(2026, 11, 16), date(2026, 11, 16)),
    "4.2": (2, "Shwetha", date(2026, 11, 16), date(2026, 11, 16)),
    "5.1": (5, "Ishwarya", date(2026, 11, 16), date(2026, 11, 16)),
    "5.2": (5, "Ishwarya", date(2026, 11, 16), date(2026, 11, 16)),
    "5.3": (3, "Ishwarya", date(2026, 11, 16), date(2026, 11, 16)),
    "5.4": (5, "Ishwarya", date(2026, 11, 16), date(2026, 11, 16)),
    "6.1": (3, "Ashish", date(2026, 11, 16), date(2026, 11, 16)),
    "6.2": (3, "Ashish", date(2026, 11, 16), date(2026, 11, 16)),
    "7.1": (5, "Ashish", date(2026, 11, 24), date(2026, 11, 24)),
    "7.2": (5, "Ashish", None, None),
    "7.3": (3, "C. Prashanth", None, None),
}
TOTAL = sum(s[0] for s in STORIES.values())
assert TOTAL == 78, TOTAL

START, TODAY, END = date(2026, 11, 3), date(2026, 11, 24), date(2026, 11, 27)
# Plan for the 13 open points (work-distribution table of the CP4 report): 7.1 dashboard 24 Nov (CP4),
# 7.3 benchmark 26 Nov, 7.2 report 27 Nov (3 pts), 7.2 viva deck 29 Nov (2 pts).
PLAN_LEFT = {date(2026, 11, 26): 3, date(2026, 11, 27): 3, date(2026, 11, 29): 2}
PLAN_END = date(2026, 11, 29)


def remaining(idx):
    days, vals = [], []
    d = START - timedelta(days=1)
    while d <= TODAY:
        done = sum(v[0] for v in STORIES.values() if v[idx] is not None and v[idx] <= d)
        days.append(d); vals.append(TOTAL - done); d += timedelta(days=1)
    return days, vals


def burndown(out):
    fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=200)
    d0 = START - timedelta(days=1)
    ax.plot([d0, END], [TOTAL, 0], color=GREY, lw=1.5, ls="--", label="Ideal (78 points, 3 to 27 Nov)")
    dc, vc = remaining(2)
    ax.step(dc, vc, where="post", color=RED, lw=2, label="Code committed (git)")
    dd, vd = remaining(3)
    ax.step(dd, vd, where="post", color=BLUE, lw=2, label="Done: run-verified on Databricks")
    left, pd, pv = vd[-1], [TODAY], [vd[-1]]
    for day in sorted(PLAN_LEFT):
        left -= PLAN_LEFT[day]; pd.append(day); pv.append(left)
    ax.step(pd, pv, where="post", color=GOLD, lw=2, ls=":", label="Plan for open stories (to 29 Nov)")
    ax.axvline(TODAY, color="#666666", lw=0.8)
    ax.text(TODAY, 45, " Today\n (CP4,\n 24 Nov)", fontsize=8, color=INK, va="top")
    ax.annotate(f"{vd[-1]} left", (TODAY, vd[-1]), xytext=(6, -14), textcoords="offset points", fontsize=8, color=INK)
    ax.annotate("16 Nov: notebooks 06-15 run as\nDatabricks jobs; 46/46 checks pass",
                (date(2026, 11, 16), 13), xytext=(-150, -2), textcoords="offset points", fontsize=8, color=INK,
                arrowprops=dict(arrowstyle="-", color="#888888", lw=0.8))
    ax.set_xlim(d0, PLAN_END + timedelta(days=1)); ax.set_ylim(0, 82)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    ax.set_ylabel("Story points remaining"); ax.set_xlabel("Date (2026)")
    ax.set_title("Sprint burndown: 21 stories, 78 points", fontsize=11, color=INK)
    ax.grid(axis="y", color="#E5E5E5", lw=0.6); ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    fig.tight_layout(); fig.savefig(out); plt.close(fig)


def member_progress(out):
    members = ["Shwetha", "Reva", "Ishwarya", "Ashish", "C. Prashanth"]
    done = {m: 0 for m in members}; open_ = {m: 0 for m in members}
    for p, owner, _, dod in STORIES.values():
        (done if dod else open_)[owner] += p
    fig, ax = plt.subplots(figsize=(7.2, 2.9), dpi=200)
    y = range(len(members))[::-1]
    for yi, m in zip(y, members):
        ax.barh(yi, done[m], color=BLUE, height=0.55, edgecolor="white", lw=2)
        ax.barh(yi, open_[m], left=done[m], color="#D9D9D9", height=0.55, edgecolor="white", lw=2, hatch="///")
        tot = done[m] + open_[m]
        ax.text(tot + 0.3, yi, f"{done[m]}/{tot} pts ({100*done[m]/tot:.0f}%)", va="center", fontsize=9, color=INK)
    ax.set_yticks(list(y)); ax.set_yticklabels(members)
    ax.set_xlim(0, 24); ax.set_xlabel("Story points owned")
    ax.set_title("Progress by owner: points done vs open (24 Nov 2026)", fontsize=11, color=INK)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=BLUE, label="Done (run-verified)"),
                       Patch(facecolor="#D9D9D9", hatch="///", label="Open")],
              fontsize=8, frameon=False, loc="lower right")
    ax.grid(axis="x", color="#E5E5E5", lw=0.6); ax.set_axisbelow(True)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    return done, open_


if __name__ == "__main__":
    burndown("fig_burndown.png")
    d, o = member_progress("fig_member_progress.png")
    print("done", d, "open", o, "total done", sum(d.values()), "of", TOTAL)

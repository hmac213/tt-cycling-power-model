"""Draws the figures for the analysis in outputs/analysis/.

    python analysis/plot_analysis.py

Run after `run_analysis.py`. Writes PDF figures to outputs/analysis/figures/.
Parts whose results are missing are skipped.
"""

import json
import pathlib
import sys

import matplotlib
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
matplotlib.use("Agg")
from matplotlib import pyplot as plt  # pylint: disable=wrong-import-position

from course_loader import gpx  # pylint: disable=wrong-import-position
from profiles import rider as rider_profiles  # pylint: disable=wrong-import-position

DATA = ROOT / "outputs" / "analysis"
FIGS = DATA / "figures"
BLUE, GREY, INK, FILL = "#2a78d6", "#8a8984", "#0b0b0b", "#d9d8d2"
PALETTE = ["#2a78d6", "#d6602a", "#2a9d6b", "#8a4fd6"]
plt.rcParams.update({"font.size": 9, "axes.grid": True, "grid.alpha": 0.3})


def _course(name):
    return gpx.load_gpx(ROOT / "courses" / f"{name}.gpx")


def power_curves():
    fig, ax = plt.subplots(figsize=(6, 3.4))
    t = np.logspace(0, np.log10(3600), 300)
    for color, name in zip(PALETTE, ("tt_specialist", "climber",
                                     "tt_specialist_women", "climber_women")):
        p = rider_profiles.load(name)
        ax.plot(t / 60, np.minimum(p.cp + p.w_prime / t, p.p_max),
                color=color, label=p.name)
        ax.axhline(p.cp, color=color, ls=":", lw=0.8)
    ax.set_xscale("log")
    ax.set_xlabel("Duration (min)")
    ax.set_ylabel("Maximum sustainable power (W)")
    ax.set_xticks([1 / 60, 0.1, 1, 5, 20, 60])
    ax.set_xticklabels(["1 s", "6 s", "1", "5", "20", "60"])
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGS / "power_curves.pdf")
    plt.close(fig)


def courses_overview():
    names = [("tokyo_2021_women", "Tokyo 2021 (one lap)"),
             ("flanders_2021_men", "Flanders 2021 (men)"),
             ("custom_loop", "Custom loop")]
    fig, ax = plt.subplots(2, 3, figsize=(9, 5), gridspec_kw={"height_ratios": [1.4, 1]})
    for i, (name, title) in enumerate(names):
        c = _course(name)
        x = (c.lon - c.lon[0]) * 111.32 * np.cos(np.radians(c.lat[0]))
        y = (c.lat - c.lat[0]) * 110.95
        tight = np.abs(c.mean_curvature(20.0)) > 1 / 30.0
        ax[0, i].plot(x, y, color=INK, lw=1)
        ax[0, i].scatter(x[tight], y[tight], s=4, color="#d6602a", zorder=3,
                         label="corner, radius < 30 m")
        ax[0, i].plot(x[0], y[0], "o", color="#2a9d6b", label="start")
        ax[0, i].plot(x[-1], y[-1], "x", color="k", label="finish")
        ax[0, i].set_aspect("equal")
        ax[0, i].set_title(title)
        ax[0, i].set_xlabel("km east")
        ax[0, i].set_ylabel("km north")
        ax[1, i].fill_between(c.distance / 1000, c.elevation, c.elevation.min() - 5, color=FILL)
        ax[1, i].plot(c.distance / 1000, c.elevation, color=INK, lw=0.8)
        ax[1, i].set_xlabel("Distance (km)")
        ax[1, i].set_ylabel("Elevation (m)")
    ax[0, 0].legend(fontsize=6, loc="lower left")
    fig.tight_layout()
    fig.savefig(FIGS / "courses_overview.pdf")
    plt.close(fig)


def plan(tag, course_name, title, cp):
    path = DATA / f"courses__{tag}.npz"
    if not path.exists():
        return
    d = np.load(path)
    c = _course(course_name)
    km = d["distance"] / 1000
    fig, ax = plt.subplots(4, 1, figsize=(7, 7.5), sharex=True)
    ax[0].fill_between(c.distance / 1000, c.elevation, c.elevation.min() - 5, color=FILL)
    ax[0].set_ylabel("Elevation (m)")
    ax[1].step(km[:-1], d["power"], where="post", color=BLUE, lw=0.9, label="Optimal")
    ax[1].step(km[:-1], d["c_power"], where="post", color=GREY, lw=1.2, label="Constant")
    ax[1].axhline(cp, ls=":", color="k", lw=0.8)
    ax[1].set_ylabel("Power (W)")
    ax[1].legend(fontsize=7, loc="upper right")
    ax[2].plot(km, d["speed"] * 3.6, color=BLUE, lw=0.9)
    ax[2].plot(km, d["c_speed"] * 3.6, color=GREY, lw=0.9)
    ax[2].set_ylabel("Speed (km/h)")
    ax[3].plot(km, d["reserve"] / 1000, color=BLUE, lw=0.9)
    ax[3].plot(km, d["c_reserve"] / 1000, color=GREY, lw=0.9)
    ax[3].set_ylabel("$B$ (kJ)")
    ax[3].set_xlabel("Distance (km)")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(FIGS / f"plan_{tag}.pdf")
    plt.close(fig)


def wind():
    path = DATA / "wind.json"
    if not path.exists():
        return
    rows = json.loads(path.read_text())
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    for ax, label, title in zip(axes, ("flanders", "tokyo"),
                                ("Flanders, men's TT specialist (point to point)",
                                 "Tokyo, women's TT specialist (loop)")):
        calm = next((r for r in rows if r["tag"] == f"{label}__calm"), None)
        if calm is None:
            continue
        calm = calm["optimal_time"]
        for color, speed in zip(PALETTE, (2.0, 4.0, 6.0)):
            pts = sorted((r["wind_from"], r["optimal_time"] - calm) for r in rows
                         if r["tag"].startswith(label) and r.get("wind_speed") == speed)
            if not pts:
                continue
            ang = [p[0] for p in pts] + [360]
            val = [p[1] for p in pts] + [pts[0][1]]
            ax.plot(ang, val, "o-", ms=3, color=color, label=f"{speed:g} m/s")
        ax.axhline(0, color="k", lw=0.8)
        ax.set_xticks(range(0, 361, 45))
        ax.set_xticklabels(["N", "NE", "E", "SE", "S", "SW", "W", "NW", "N"])
        ax.set_xlabel("Direction the wind blows from")
        ax.set_ylabel("Optimal time minus calm-day time (s)")
        ax.set_title(title, fontsize=8)
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIGS / "wind_sensitivity.pdf")
    plt.close(fig)


def deviation():
    path = DATA / "deviation.json"
    if not path.exists():
        return
    summary = json.loads(path.read_text())
    fig, ax = plt.subplots(1, 2, figsize=(9, 3.4))
    exact = summary["exact_time"]
    names = [s["scenario"] for s in summary["scenarios"]]
    for i, name in enumerate(names):
        times = np.load(DATA / f"deviation__{name.replace(' ', '_').replace('%', 'pct')}.npy")
        parts = ax[0].violinplot((times - exact), positions=[i], showextrema=False, widths=0.8)
        for body in parts["bodies"]:
            body.set_facecolor(PALETTE[i % 4])
            body.set_alpha(0.5)
        ax[0].plot([i - 0.3, i + 0.3], [np.median(times - exact)] * 2, color=INK, lw=1)
    ax[0].axhline(0, color="k", lw=0.8)
    ax[0].set_xticks(range(len(names)))
    ax[0].set_xticklabels(names, rotation=30, ha="right", fontsize=7)
    ax[0].set_ylabel("Finish time vs. perfect execution (s)")
    ax[0].set_title("Missing the power targets", fontsize=9)

    scen = next(s for s in summary["scenarios"] if s["scenario"] == "random 5%")
    labels = list(scen["splits"])
    exact_s = np.array([scen["splits"][k]["exact"] for k in labels])
    lo = np.array([scen["splits"][k]["p05"] for k in labels]) - exact_s
    hi = np.array([scen["splits"][k]["p95"] for k in labels]) - exact_s
    mid = np.array([scen["splits"][k]["p50"] for k in labels]) - exact_s
    y = np.arange(len(labels))
    ax[1].hlines(y, lo, hi, color=BLUE, lw=6, alpha=0.5)
    ax[1].plot(mid, y, "|", color=INK, ms=10)
    ax[1].axvline(0, color="k", lw=0.8)
    ax[1].set_yticks(y)
    ax[1].set_yticklabels([f"{k} ({exact_s[j] / 60:.1f} min)" for j, k in enumerate(labels)],
                          fontsize=7)
    ax[1].invert_yaxis()
    ax[1].set_xlabel("Split time vs. plan (s), 5-95% range")
    ax[1].set_title("Split-time ranges, random 5% error", fontsize=9)
    fig.tight_layout()
    fig.savefig(FIGS / "deviation.pdf")
    plt.close(fig)


def main():
    FIGS.mkdir(parents=True, exist_ok=True)
    power_curves()
    courses_overview()
    plan("tokyo__tt_specialist", "tokyo_2021_men",
         "Tokyo 2021, men's course, TT specialist", 410)
    plan("flanders__tt_specialist_women", "flanders_2021_women",
         "Flanders 2021, women's course, TT specialist (women)", 300)
    plan("custom__climber", "custom_loop", "Custom loop, climber", 350)
    wind()
    deviation()
    print("figures in", FIGS)


if __name__ == "__main__":
    main()

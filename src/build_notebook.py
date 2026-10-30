"""Builds notebooks/flowmetrics_analysis.ipynb (run it, then execute the notebook)."""

from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
nb = nbf.v4.new_notebook()
cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))

md("""
# flowmetrics: Where does a fulfillment network lose its delivery promise?

**Business question:** A 12-site East Coast fulfillment network is missing its ship-by promise on about
1 in 17 orders, and almost all of the misses are Priority orders. Leadership wants to know *where*,
*when*, and *why*, and what to fix first.

**Data:** one month (March 2026) of order-level scan events (order, pick, pack, ship), a shift-level
staffing plan, and site reference data. The data is synthetic but modeled on real fulfillment
operations; see the README for how it's generated.

**Approach:** clean the raw feed in SQL (DuckDB), answer six business questions with SQL, and chart
the results here. Every query lives in `sql/` so it can be read and reused on its own.
""")

code("""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
sys.path.insert(0, str(ROOT / "src"))
from run_analysis import connect

con = connect()
FIG = ROOT / "reports" / "figures"
FIG.mkdir(parents=True, exist_ok=True)

def sql(name):
    return con.execute((ROOT / "sql" / f"{name}.sql").read_text()).df()

INK, MUTED, ACCENT, ALERT = "#1f2933", "#9aa5b1", "#2563eb", "#dc2626"
plt.rcParams.update({
    "figure.dpi": 120, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
})
pd.set_option("display.width", 140)
""")

md("""
## Q0. Is the data trustworthy?
Scanner feeds are messy. Before any KPI, profile and remove defects: duplicate scans, missing pack
scans (cycle time can't be measured), and clock-skew rows where a pick starts before the order exists.
The cleaning logic is in `sql/clean_orders.sql`.
""")
code("""
dq = sql("00_data_quality")
dq
""")
code("""
removed = dq.loc[0, "row_count"] - dq.loc[4, "row_count"]
print(f"Removed {removed:,} rows ({removed / dq.loc[0, 'row_count']:.1%} of the raw feed) before analysis.")
""")

md("## Q1. How is the network performing overall?")
code("""
kpi = sql("01_network_kpis")
kpi
""")
code("""
overall = con.execute("SELECT AVG(CASE WHEN sla_breach THEN 1.0 ELSE 0 END) FROM clean_orders").fetchone()[0]
print(f"Network SLA breach rate: {overall:.2%}")
""")
md("""
Standard orders (24-hour promise) almost never miss. **Priority orders (8-hour promise) miss about 14% of
the time**, so the rest of the analysis focuses on what drives Priority breaches.
""")

md("## Q2. Which sites breach SLA most?")
code("""
site = sql("02_sla_by_site")
site
""")
code("""
s = site.sort_values("breach_rate_pct")
colors = [ALERT if r > 1.5 else MUTED for r in s["vs_network_x"]]
fig, ax = plt.subplots(figsize=(8, 4.5))
ax.barh(s["city"], s["breach_rate_pct"], color=colors)
ax.axvline(overall * 100, color=INK, ls="--", lw=1)
ax.text(overall * 100 + 0.15, 0.2, f"Network {overall:.1%}", fontsize=9, color=INK)
ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax.set_title("Charlotte misses SLA at nearly 2x the network rate")
ax.set_xlabel("Orders shipped after promise")
fig.tight_layout(); fig.savefig(FIG / "01_breach_by_site.png", bbox_inches="tight")
""")

md("## Q3. When during the day do breaches happen?")
code("""
hourly = sql("03_sla_by_hour")
pri = hourly[hourly.service_tier == "Priority"]
std = hourly[hourly.service_tier == "Standard"]

fig, ax1 = plt.subplots(figsize=(9, 4.5))
ax1.bar(pri["order_hour"], pri["orders"] + std["orders"].values, color="#dbe4f0", label="Orders placed (all tiers)")
ax1.set_ylabel("Orders placed")
ax2 = ax1.twinx()
ax2.plot(pri["order_hour"], pri["breach_rate_pct"], color=ALERT, lw=2.2, marker="o", ms=4, label="Priority breach rate")
ax2.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax2.set_ylabel("Priority breach rate")
ax2.spines["right"].set_visible(True)
ax1.set_xticks(range(0, 24, 2)); ax1.set_xlabel("Hour order was placed")
ax1.set_title("Priority orders placed 6-10 PM breach up to 60% of the time")
fig.tight_layout(); fig.savefig(FIG / "02_breach_by_hour.png", bbox_inches="tight")
""")
code("""
con.execute('''
    SELECT
        ROUND(100.0 * AVG(CASE WHEN order_hour BETWEEN 17 AND 21 THEN 1 ELSE 0 END), 1)          AS pct_of_orders_placed_5_to_10pm,
        ROUND(100.0 * SUM(CASE WHEN sla_breach AND order_hour BETWEEN 17 AND 21 THEN 1 ELSE 0 END)
              / SUM(CASE WHEN sla_breach THEN 1 ELSE 0 END), 1)                                   AS pct_of_breaches_placed_5_to_10pm
    FROM clean_orders
''').df()
""")
md("""
The evening surge is the whole story at the network level: orders placed between 5 and 10 PM are
about 38% of volume but about 98% of SLA breaches. Those orders land on the night shift.
""")

md("## Q4. Which process stage is the bottleneck, and where?")
code("""
stages = sql("04_stage_bottlenecks")
stages.head(8)
""")
code("""
order = ["median_queue_min", "median_pick_min", "median_pack_min", "median_dock_wait_min"]
labels = ["Queue before pick", "Pick", "Pack", "Wait for truck"]
night = stages[stages["shift"] == "Night"].copy()
compare = pd.DataFrame({
    "Charlotte night": night[night.site_id == "FC07"][order].iloc[0].values,
    "Other sites, night (median)": night[night.site_id != "FC07"][order].median().values,
}, index=labels)

fig, ax = plt.subplots(figsize=(8, 4))
y = range(len(labels))
ax.barh([i + 0.2 for i in y], compare.iloc[:, 1], height=0.4, color=MUTED, label=compare.columns[1])
ax.barh([i - 0.2 for i in y], compare.iloc[:, 0], height=0.4, color=ALERT, label=compare.columns[0])
ax.set_yticks(list(y)); ax.set_yticklabels(labels); ax.invert_yaxis()
ax.set_xlabel("Median minutes in stage")
ax.legend(frameon=False, loc="lower right")
ax.set_title("Charlotte's night-shift pack stage takes 2.3x longer than its peers")
fig.tight_layout(); fig.savefig(FIG / "03_stage_bottleneck.png", bbox_inches="tight")
compare.round(1)
""")
md("""
Across the network, night-shift orders spend about four times longer waiting in the pick queue than
day-shift orders. That's a labor capacity problem, not a process one. Charlotte has a second, local
problem on top of it: its night pack stage is more than twice as slow as every other site.
""")

md("## Q5. Does labor explain the breaches?")
code("""
labor = sql("05_staffing_vs_breach")
labor
""")
code("""
hc = con.execute('''
    WITH u AS (SELECT shift, SUM(units) * 10 AS units FROM clean_orders GROUP BY shift),
         h AS (SELECT shift, SUM(actual_headcount) AS head_shifts FROM staffing GROUP BY shift)
    SELECT shift, units, head_shifts, ROUND(units / head_shifts, 0) AS units_per_associate_shift
    FROM u JOIN h USING (shift) ORDER BY shift
''').df()
hc
""")
code("""
fig, ax = plt.subplots(figsize=(7, 4))
g = (labor.assign(w=labor["site_shifts"] * labor["avg_breach_rate_pct"])
          .groupby(["shift", "attendance_band"])[["w", "site_shifts"]].sum())
g = (g["w"] / g["site_shifts"]).unstack()   # weighted breach rate, weekday + weekend combined
x = range(len(g.index))
ax.bar([i - 0.2 for i in x], g["Normal attendance"], width=0.4, color=MUTED, label="Normal attendance")
ax.bar([i + 0.2 for i in x], g["Call-out day (<88%)"], width=0.4, color=ALERT, label="Call-out day (<88% of plan)")
for i, sh in enumerate(g.index):
    for off, col in ((-0.2, "Normal attendance"), (0.2, "Call-out day (<88%)")):
        ax.text(i + off, g.loc[sh, col] + 0.4, f"{g.loc[sh, col]:.1f}%", ha="center", fontsize=9)
ax.set_xticks(list(x)); ax.set_xticklabels([f"{sh} shift" for sh in g.index])
ax.yaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
ax.set_ylabel("Avg SLA breach rate")
ax.legend(frameon=False, loc="upper left")
ax.set_title("Night shifts breach; short-staffed nights breach even more")
fig.tight_layout(); fig.savefig(FIG / "04_staffing_vs_breach.png", bbox_inches="tight")
""")
md("""
Night shifts carry about 43% of the units with about 60% of the day shift's headcount, so each night
associate moves roughly 25% more volume. Day shifts barely breach regardless of attendance. On nights
when attendance falls below 88% of plan, the breach rate jumps from about 13% to about 20%.
""")

md("## Q6. Were there one-off incidents?")
code("""
daily = sql("06_daily_trend")
daily[daily.is_anomaly]
""")
code("""
tpa = daily[daily.site_id == "FC03"]
fig, ax = plt.subplots(figsize=(9, 3.8))
ax.plot(pd.to_datetime(tpa["order_date"]), tpa["median_cycle_hours"], color=ACCENT, lw=2)
spike = tpa[tpa.is_anomaly]
ax.scatter(pd.to_datetime(spike["order_date"]), spike["median_cycle_hours"], color=ALERT, s=60, zorder=3)
for _, r in spike.iterrows():
    ax.annotate("Mar 12: 8.4 hr median,\\n19% breach rate", (pd.to_datetime(r["order_date"]), r["median_cycle_hours"]),
                xytext=(12, -6), textcoords="offset points", fontsize=9, color=ALERT)
ax.set_ylabel("Median order-to-ship hours"); ax.set_ylim(0, None)
import matplotlib.dates as mdates
ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
ax.set_title("Tampa: a single-day spike consistent with an equipment outage")
fig.tight_layout(); fig.savefig(FIG / "05_tampa_incident.png", bbox_inches="tight")
""")
md("""
Two flags are clearly real incidents:

- **Tampa, March 12.** Median cycle time more than doubled and the breach rate hit about 19%. Pick and
  pack times were only modestly higher; the big jump was the wait between pack and truck, the
  signature of a dock or sortation outage.
- **Jacksonville, March 7.** The night shift ran at 72% of planned headcount and breaches spiked.

The other three flags are mild cycle-time blips (z-scores just over 3) worth watching but not
acting on.

## Recommendations
1. **Re-plan night-shift labor to the evening surge.** Night shifts are planned about 20% lean even
   though the 5-10 PM order peak lands on them. A swing shift (for example 4 PM-2 AM) targets the window
   that produces about 98% of breaches.
2. **Fix Charlotte's night pack line first.** It's the single largest site-level gap: about 2x the
   network breach rate and a pack stage 2.3x slower than peers.
3. **Build a call-out buffer for nights.** A flex pool or overtime trigger when night attendance drops
   below 88% of plan.
4. **Turn Q6 into a daily alert.** The anomaly query catches outages within a day; Tampa's would have
   been flagged on March 12.
""")

nb["cells"] = cells
nb["metadata"]["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
out = ROOT / "notebooks" / "flowmetrics_analysis.ipynb"
out.parent.mkdir(exist_ok=True)
nbf.write(nb, out)
print(f"Wrote {out.relative_to(ROOT)}")

"""
Generate a synthetic fulfillment event dataset for the flowmetrics case study.

The data is fictional but modeled on how a regional fulfillment network behaves:
orders arrive with a daily/hourly rhythm, move through pick -> pack -> ship,
and leave on scheduled carrier departures. Labor capacity comes from a
shift-level staffing table, and congestion grows when hourly volume exceeds
what the floor can handle.

Several operational problems are deliberately built in so the analysis has
something real to find (see README "Data" section). Everything is seeded,
so the output is reproducible.

Usage:
    python src/generate_data.py            # writes data/raw/ (sites.csv, staffing.csv, order_events.csv.gz)
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
START = pd.Timestamp("2026-03-01")
DAYS = 31
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

# Fictional East Coast sites. daily_orders = average weekday order volume.
SITES = pd.DataFrame(
    [
        ("FC01", "Jacksonville", "FL", 6200),
        ("FC02", "Orlando", "FL", 5800),
        ("FC03", "Tampa", "FL", 5400),
        ("FC04", "Miami", "FL", 4900),
        ("FC05", "Atlanta", "GA", 7000),
        ("FC06", "Savannah", "GA", 3600),
        ("FC07", "Charlotte", "NC", 5600),
        ("FC08", "Raleigh", "NC", 4200),
        ("FC09", "Richmond", "VA", 3900),
        ("FC10", "Baltimore", "MD", 5100),
        ("FC11", "Philadelphia", "PA", 6400),
        ("FC12", "Newark", "NJ", 6800),
    ],
    columns=["site_id", "city", "state", "daily_orders"],
)

# Share of daily orders arriving in each hour (customers order more in the evening).
HOURLY_SHAPE = np.array(
    [1.2, 0.8, 0.6, 0.5, 0.5, 0.8, 1.6, 2.8, 3.8, 4.6, 5.0, 5.2,
     5.4, 5.2, 5.0, 5.0, 5.4, 6.2, 7.4, 8.2, 8.0, 6.6, 4.4, 2.4]
)
HOURLY_SHAPE = HOURLY_SHAPE / HOURLY_SHAPE.sum()

DAY_SHIFT_HOURS = range(6, 18)  # 06:00-17:59; night shift covers the rest
UNITS_PER_LABOR_HOUR = 22       # units one associate can move through pick+pack per hour
SLA_HOURS = {"Priority": 8, "Standard": 24}


def build_staffing(rng: np.random.Generator) -> pd.DataFrame:
    """Planned vs. actual headcount per site, day, and shift."""
    rows = []
    for _, site in SITES.iterrows():
        for d in range(DAYS):
            date = START + pd.Timedelta(days=d)
            weekend = date.dayofweek >= 5
            for shift in ("Day", "Night"):
                # Plan to the expected volume share of each shift.
                shift_share = HOURLY_SHAPE[list(DAY_SHIFT_HOURS)].sum()
                if shift == "Night":
                    shift_share = 1 - shift_share
                expected_units = site.daily_orders * 2.4 * shift_share
                planned = expected_units / (UNITS_PER_LABOR_HOUR * 12) * 1.10

                # Built-in issue: night shifts are planned ~20% lean network-wide,
                # even though the evening order surge lands on them.
                if shift == "Night":
                    planned *= 0.80
                # Built-in issue: weekend plans are cut another 15%.
                if weekend:
                    planned *= 0.85

                planned = int(round(planned))
                # Attendance: normally 92-100% of plan; occasional bad call-out days.
                attendance = rng.uniform(0.92, 1.0)
                if rng.random() < 0.06:
                    attendance = rng.uniform(0.70, 0.85)
                actual = int(round(planned * attendance))
                rows.append((site.site_id, date.date(), shift, planned, actual))
    return pd.DataFrame(rows, columns=["site_id", "date", "shift", "planned_headcount", "actual_headcount"])


def build_orders(rng: np.random.Generator, staffing: pd.DataFrame) -> pd.DataFrame:
    frames = []
    order_seq = 0
    for _, site in SITES.iterrows():
        for d in range(DAYS):
            date = START + pd.Timedelta(days=d)
            dow_factor = {0: 1.05, 1: 1.0, 2: 1.0, 3: 1.02, 4: 1.08, 5: 0.92, 6: 0.85}[date.dayofweek]
            n = rng.poisson(site.daily_orders * dow_factor / 10)  # 1-in-10 sample keeps the file small
            hours = rng.choice(24, size=n, p=HOURLY_SHAPE)
            minutes = rng.uniform(0, 60, size=n)
            ts = date + pd.to_timedelta(hours, unit="h") + pd.to_timedelta(minutes, unit="m")
            tier = np.where(rng.random(n) < 0.38, "Priority", "Standard")
            units = rng.choice([1, 1, 1, 2, 2, 3, 4, 6], size=n)
            ids = [f"ORD{order_seq + i:07d}" for i in range(n)]
            order_seq += n
            frames.append(pd.DataFrame({
                "order_id": ids, "site_id": site.site_id, "service_tier": tier,
                "units": units, "order_ts": ts,
            }))
    orders = pd.concat(frames, ignore_index=True)

    # --- Congestion: hourly load vs. labor capacity --------------------------
    orders["date"] = orders["order_ts"].dt.date
    orders["hour"] = orders["order_ts"].dt.hour
    orders["shift"] = np.where(orders["hour"].isin(list(DAY_SHIFT_HOURS)), "Day", "Night")
    hourly_units = (orders.groupby(["site_id", "date", "hour"])["units"].sum() * 10).rename("hour_units")
    orders = orders.join(hourly_units, on=["site_id", "date", "hour"])
    orders = orders.merge(staffing, on=["site_id", "date", "shift"], how="left")
    capacity = orders["actual_headcount"] * UNITS_PER_LABOR_HOUR
    orders["utilization"] = orders["hour_units"] / capacity
    congestion = 1 + np.clip(orders["utilization"] - 0.85, 0, None) * 6

    n = len(orders)
    pick_wait = rng.lognormal(np.log(25), 0.5, n) * congestion          # minutes in queue before pick
    pick_dur = rng.lognormal(np.log(9), 0.35, n) * (1 + 0.15 * (orders["units"] - 1))
    pack_dur = rng.lognormal(np.log(12), 0.4, n) * congestion

    # Built-in issue: Charlotte (FC07) lost two pack stations; night-shift packing runs ~2.3x slower.
    fc07_night = (orders["site_id"] == "FC07") & (orders["shift"] == "Night")
    pack_dur = np.where(fc07_night, pack_dur * 2.3, pack_dur)

    # Priority orders get jumped ahead in the pick queue.
    pick_wait = np.where(orders["service_tier"] == "Priority", pick_wait * 0.55, pick_wait)

    orders["pick_start_ts"] = orders["order_ts"] + pd.to_timedelta(pick_wait, unit="m")
    orders["pick_end_ts"] = orders["pick_start_ts"] + pd.to_timedelta(pick_dur, unit="m")
    orders["pack_end_ts"] = orders["pick_end_ts"] + pd.to_timedelta(pack_dur, unit="m")

    # Carrier departures every 2 hours on even hours; parcels leave on the next truck
    # after a 15-minute staging buffer.
    ready = orders["pack_end_ts"] + pd.Timedelta(minutes=15)
    orders["ship_ts"] = ready.dt.floor("2h") + pd.Timedelta(hours=2)

    # Built-in issue: Tampa (FC03) sortation conveyor outage, 2026-03-12 08:00-18:00.
    # Packed parcels can't reach the dock until the conveyor is back, then the
    # backlog drains over roughly six hours.
    outage_start, outage_end = pd.Timestamp("2026-03-12 08:00"), pd.Timestamp("2026-03-12 18:00")
    in_outage = (orders["site_id"] == "FC03") & orders["pack_end_ts"].between(outage_start, outage_end)
    drained = outage_end + pd.to_timedelta(rng.uniform(0, 360, in_outage.sum()), unit="m")
    orders.loc[in_outage, "ship_ts"] = (drained.floor("2h") + pd.Timedelta(hours=2)).values

    orders["sla_hours"] = orders["service_tier"].map(SLA_HOURS)
    orders["promised_ship_ts"] = orders["order_ts"] + pd.to_timedelta(orders["sla_hours"], unit="h")

    cols = ["order_id", "site_id", "service_tier", "units", "order_ts", "pick_start_ts",
            "pick_end_ts", "pack_end_ts", "ship_ts", "sla_hours", "promised_ship_ts"]
    out = orders[cols].copy()
    for c in ["order_ts", "pick_start_ts", "pick_end_ts", "pack_end_ts", "ship_ts", "promised_ship_ts"]:
        out[c] = out[c].dt.round("s")
    return out.sort_values("order_ts").reset_index(drop=True)


def add_data_quality_issues(rng: np.random.Generator, orders: pd.DataFrame) -> pd.DataFrame:
    """Real event feeds are messy. Add the kinds of defects the analysis must clean."""
    orders = orders.copy()
    n = len(orders)
    # ~0.4% duplicated events (scanner double-reads).
    dupes = orders.sample(frac=0.004, random_state=SEED)
    # ~0.3% missing pack scans.
    miss = rng.choice(n, size=int(n * 0.003), replace=False)
    orders.loc[miss, "pack_end_ts"] = pd.NaT
    # ~0.1% clock-skew rows where pick_start precedes order time.
    skew = rng.choice(n, size=int(n * 0.001), replace=False)
    orders.loc[skew, "pick_start_ts"] = orders.loc[skew, "order_ts"] - pd.Timedelta(minutes=30)
    return pd.concat([orders, dupes], ignore_index=True).sample(frac=1, random_state=SEED).reset_index(drop=True)


def main() -> None:
    rng = np.random.default_rng(SEED)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    staffing = build_staffing(rng)
    orders = build_orders(rng, staffing)
    orders = add_data_quality_issues(rng, orders)

    SITES.drop(columns="daily_orders").to_csv(OUT_DIR / "sites.csv", index=False)
    staffing.to_csv(OUT_DIR / "staffing.csv", index=False)
    orders.to_csv(OUT_DIR / "order_events.csv.gz", index=False, compression="gzip")
    print(f"order_events: {len(orders):,} rows | staffing: {len(staffing):,} rows | sites: {len(SITES)}")


if __name__ == "__main__":
    main()

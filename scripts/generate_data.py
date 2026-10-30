"""Generate a deterministic synthetic fulfillment dataset.

The generated files are intentionally ignored by git. Re-run this script to
rebuild the source data used by the notebook and SQL analysis.
"""

from pathlib import Path
import argparse

import numpy as np
import pandas as pd


SITES = {
    "ATL": ("Southeast", 0.95, 1.00),
    "DAL": ("South Central", 1.08, 1.03),
    "LAX": ("West", 1.22, 1.07),
    "ORD": ("Midwest", 1.15, 1.04),
    "PHL": ("Northeast", 1.30, 1.10),
}


def build_orders(n_orders: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    start = pd.Timestamp("2025-01-01", tz="UTC")
    days = rng.integers(0, 90, size=n_orders)
    hour_weights = np.array(
        [0.55, 0.45, 0.40, 0.40, 0.55, 0.80, 1.05, 1.35, 1.50, 1.25, 1.15, 1.30,
         1.45, 1.45, 1.20, 1.00, 0.95, 1.05, 1.25, 1.35, 1.20, 0.95, 0.75, 0.60]
    )
    hour_weights = hour_weights / hour_weights.sum()
    hours = rng.choice(24, size=n_orders, p=hour_weights)
    seconds = hours * 60 * 60 + rng.integers(0, 60 * 60, size=n_orders)
    order_ts = start + pd.to_timedelta(days, unit="D") + pd.to_timedelta(seconds, unit="s")
    site_ids = rng.choice(list(SITES), size=n_orders, p=[0.24, 0.20, 0.18, 0.20, 0.18])
    priority = rng.choice(["Standard", "Expedited", "Priority"], size=n_orders, p=[0.68, 0.22, 0.10])
    channel = rng.choice(["Web", "Mobile", "Marketplace", "B2B"], size=n_orders, p=[0.42, 0.30, 0.20, 0.08])
    item_count = np.clip(rng.lognormal(mean=0.55, sigma=0.65, size=n_orders).round().astype(int), 1, 12)
    promised_hours = np.select(
        [priority == "Expedited", priority == "Priority"],
        [36, 24],
        default=72,
    )
    weekday_load = np.where(pd.Series(order_ts).dt.dayofweek.to_numpy() >= 5, 1.12, 1.0)
    hour = pd.Series(order_ts).dt.hour.to_numpy()
    peak_load = np.where((hour >= 11) & (hour < 15), 1.22, np.where((hour >= 18) & (hour < 21), 1.12, 1.0))
    site_factor = np.array([SITES[s][1] for s in site_ids])
    complexity = 1 + (item_count - 1) * 0.07
    process_hours = rng.gamma(shape=3.0, scale=2.2, size=n_orders) * site_factor * complexity * weekday_load * peak_load
    process_hours += np.where(priority == "Expedited", -1.4, np.where(priority == "Priority", -2.0, 0))
    process_hours = np.maximum(process_hours, 1.5)
    ship_ts = order_ts + pd.to_timedelta(process_hours, unit="h")
    delivery_hours = rng.lognormal(mean=np.log(30), sigma=0.35, size=n_orders)
    delivery_ts = ship_ts + pd.to_timedelta(delivery_hours, unit="h")
    promised_delivery_ts = order_ts + pd.to_timedelta(promised_hours, unit="h")
    return pd.DataFrame(
        {
            "order_id": [f"ORD-{i:07d}" for i in range(1, n_orders + 1)],
            "site_id": site_ids,
            "region": [SITES[s][0] for s in site_ids],
            "channel": channel,
            "priority": priority,
            "item_count": item_count,
            "order_ts": order_ts,
            "promised_delivery_ts": promised_delivery_ts,
            "ship_ts": ship_ts,
            "delivery_ts": delivery_ts,
            "process_hours": process_hours.round(2),
        }
    )


def build_events(orders: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 1)
    rows = []
    stages = [
        ("order_created", "order_ts"),
        ("picked", None),
        ("packed", None),
        ("shipped", "ship_ts"),
        ("delivered", "delivery_ts"),
    ]
    for row in orders.itertuples(index=False):
        created = row.order_ts
        pick_delay = max(0.25, row.process_hours * rng.uniform(0.28, 0.42))
        pack_delay = max(0.20, row.process_hours * rng.uniform(0.16, 0.28))
        timestamps = {
            "order_created": created,
            "picked": created + pd.to_timedelta(pick_delay, unit="h"),
            "packed": created + pd.to_timedelta(pick_delay + pack_delay, unit="h"),
            "shipped": row.ship_ts,
            "delivered": row.delivery_ts,
        }
        for event_type, _ in stages:
            rows.append(
                {
                    "order_id": row.order_id,
                    "event_type": event_type,
                    "event_ts": timestamps[event_type],
                    "site_id": row.site_id,
                    "priority": row.priority,
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--orders", type=int, default=120_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="data/raw")
    args = parser.parse_args()
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    orders = build_orders(args.orders, args.seed)
    events = build_events(orders, args.seed)
    orders.to_csv(output / "orders.csv", index=False)
    events.to_csv(output / "fulfillment_events.csv", index=False)
    print(f"Wrote {len(orders):,} orders and {len(events):,} events to {output}")


if __name__ == "__main__":
    main()

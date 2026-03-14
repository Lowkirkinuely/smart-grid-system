"""
Grid Simulator — sends realistic grid state scenarios to the backend.

Usage:
  python simulator.py                  # run all scenarios in order
  python simulator.py --scenario 3     # run a specific scenario
  python simulator.py --loop           # loop forever (live demo mode)
  python simulator.py --random         # send random data continuously
"""

import argparse
import httpx
import json
import time
import random

BASE_URL = "http://localhost:8000"

# ── Scenarios ──────────────────────────────────────────────────────────────────
# Each scenario simulates a real-world grid condition.

SCENARIOS = [
    {
        "name": "✅  Normal Operation",
        "description": "Grid is stable. Supply exceeds demand comfortably.",
        "payload": {
            "demand": 320.0,
            "supply": 410.0,
            "temperature": 28.0,
            "zones": [
                {"name": "zone_hospital_delhi",     "demand": 60.0,  "protected": True},
                {"name": "zone_metro_rail",          "demand": 45.0,  "protected": True},
                {"name": "zone_industrial_noida",    "demand": 90.0,  "protected": False},
                {"name": "zone_residential_east",    "demand": 70.0,  "protected": False},
                {"name": "zone_residential_west",    "demand": 55.0,  "protected": False},
            ]
        }
    },
    {
        "name": "⚠️  Rising Demand (Afternoon Peak)",
        "description": "Temperature climbing. Demand rising due to AC load.",
        "payload": {
            "demand": 480.0,
            "supply": 460.0,
            "temperature": 38.5,
            "zones": [
                {"name": "zone_hospital_delhi",     "demand": 65.0,  "protected": True},
                {"name": "zone_metro_rail",          "demand": 50.0,  "protected": True},
                {"name": "zone_industrial_noida",    "demand": 110.0, "protected": False},
                {"name": "zone_residential_east",    "demand": 130.0, "protected": False},
                {"name": "zone_residential_west",    "demand": 125.0, "protected": False},
            ]
        }
    },
    {
        "name": "🔴  Heatwave Overload",
        "description": "Severe heatwave. Demand far exceeds supply. Load shedding required.",
        "payload": {
            "demand": 580.0,
            "supply": 430.0,
            "temperature": 46.0,
            "zones": [
                {"name": "zone_hospital_delhi",     "demand": 70.0,  "protected": True},
                {"name": "zone_metro_rail",          "demand": 55.0,  "protected": True},
                {"name": "zone_industrial_noida",    "demand": 130.0, "protected": False},
                {"name": "zone_industrial_gurgaon",  "demand": 115.0, "protected": False},
                {"name": "zone_residential_east",    "demand": 110.0, "protected": False},
                {"name": "zone_residential_west",    "demand": 100.0, "protected": False},
            ]
        }
    },
    {
        "name": "🚨  Generator Trip + Heatwave (Critical)",
        "description": "A major generator tripped offline during peak heatwave. Critical deficit.",
        "payload": {
            "demand": 610.0,
            "supply": 350.0,
            "temperature": 48.5,
            "zones": [
                {"name": "zone_hospital_delhi",     "demand": 75.0,  "protected": True},
                {"name": "zone_metro_rail",          "demand": 60.0,  "protected": True},
                {"name": "zone_airport",             "demand": 80.0,  "protected": True},
                {"name": "zone_industrial_noida",    "demand": 140.0, "protected": False},
                {"name": "zone_industrial_gurgaon",  "demand": 120.0, "protected": False},
                {"name": "zone_residential_east",    "demand": 70.0,  "protected": False},
                {"name": "zone_residential_west",    "demand": 65.0,  "protected": False},
            ]
        }
    },
    {
        "name": "🌙  Night Recovery",
        "description": "Demand dropping after midnight. Grid stabilising.",
        "payload": {
            "demand": 210.0,
            "supply": 380.0,
            "temperature": 31.0,
            "zones": [
                {"name": "zone_hospital_delhi",     "demand": 55.0,  "protected": True},
                {"name": "zone_metro_rail",          "demand": 20.0,  "protected": True},
                {"name": "zone_industrial_noida",    "demand": 60.0,  "protected": False},
                {"name": "zone_residential_east",    "demand": 45.0,  "protected": False},
                {"name": "zone_residential_west",    "demand": 30.0,  "protected": False},
            ]
        }
    },
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def send_grid_state(payload: dict) -> None:
    try:
        r = httpx.post(f"{BASE_URL}/grid-state", json=payload, timeout=20)
        data = r.json()
        print(f"    → Risk: {data.get('risk_level', '?').upper():<10} "
              f"ML: {data.get('ml_risk_level', '?'):<10} "
              f"LLM: {data.get('llm_risk_level', '?'):<10} "
              f"HITL: {data.get('requires_human_approval', False)}")
    except httpx.ConnectError:
        print("    ✗ Could not connect. Is the backend running? (cd backend && uvicorn main:app --reload)")
    except Exception as e:
        print(f"    ✗ Error: {e}")


def run_scenario(idx: int) -> None:
    s = SCENARIOS[idx]
    print(f"\n{'─'*55}")
    print(f"  Scenario {idx + 1}: {s['name']}")
    print(f"  {s['description']}")
    p = s["payload"]
    deficit = p["demand"] - p["supply"]
    print(f"  Demand: {p['demand']}MW  Supply: {p['supply']}MW  "
          f"Deficit: {deficit:+.1f}MW  Temp: {p['temperature']}°C")
    print(f"{'─'*55}")
    send_grid_state(p)


def random_payload() -> dict:
    """Generate a random but plausible grid state."""
    temp = random.uniform(25, 52)
    demand = random.uniform(250, 650)
    # Supply is correlated with demand but can be below it
    supply = demand * random.uniform(0.7, 1.3)

    zones = [
        {"name": "zone_hospital",         "demand": round(random.uniform(50, 90), 1),  "protected": True},
        {"name": "zone_metro_rail",        "demand": round(random.uniform(30, 70), 1),  "protected": True},
        {"name": "zone_industrial_a",      "demand": round(random.uniform(60, 150), 1), "protected": False},
        {"name": "zone_industrial_b",      "demand": round(random.uniform(50, 130), 1), "protected": False},
        {"name": "zone_residential_north", "demand": round(random.uniform(40, 120), 1), "protected": False},
        {"name": "zone_residential_south", "demand": round(random.uniform(40, 110), 1), "protected": False},
    ]
    return {
        "demand":      round(demand, 1),
        "supply":      round(supply, 1),
        "temperature": round(temp, 1),
        "zones":       zones
    }


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Smart Grid Simulator")
    parser.add_argument("--scenario", type=int, help="Run a single scenario (1-5)")
    parser.add_argument("--loop",     action="store_true", help="Loop all scenarios forever")
    parser.add_argument("--random",   action="store_true", help="Send random data every N seconds")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between sends (default: 5)")
    args = parser.parse_args()

    print("\n🔌 Smart Grid Simulator")
    print(f"   Sending to: {BASE_URL}/grid-state")

    if args.scenario:
        idx = args.scenario - 1
        if idx < 0 or idx >= len(SCENARIOS):
            print(f"✗ Scenario must be between 1 and {len(SCENARIOS)}")
            return
        run_scenario(idx)

    elif args.random:
        print(f"   Mode: random  |  Interval: {args.interval}s  |  Ctrl+C to stop\n")
        i = 1
        while True:
            print(f"\n  [{i}] Sending random grid state...")
            payload = random_payload()
            deficit = payload["demand"] - payload["supply"]
            print(f"  Demand: {payload['demand']}MW  Supply: {payload['supply']}MW  "
                  f"Deficit: {deficit:+.1f}MW  Temp: {payload['temperature']}°C")
            send_grid_state(payload)
            i += 1
            time.sleep(args.interval)

    elif args.loop:
        print(f"   Mode: loop all scenarios  |  Interval: {args.interval}s  |  Ctrl+C to stop")
        while True:
            for i in range(len(SCENARIOS)):
                run_scenario(i)
                time.sleep(args.interval)

    else:
        # Default: run all scenarios once
        print(f"   Mode: all scenarios (one shot)\n")
        for i in range(len(SCENARIOS)):
            run_scenario(i)
            if i < len(SCENARIOS) - 1:
                print(f"\n  ⏳ Waiting {args.interval}s before next scenario...")
                time.sleep(args.interval)

    print("\n✅ Done.\n")


if __name__ == "__main__":
    main()

"""
Smart Grid Simulator — Enhanced Version (Sanya)
===============================================
Imports weather logic from weather.py (clean separation of concerns).

Usage:
  python simulator.py                        # run all 5 scenarios once
  python simulator.py --mode escalate        # best for live demo
  python simulator.py --mode weather         # real/mock weather, one city
  python simulator.py --mode cities          # cycles all Indian cities
  python simulator.py --mode random          # random data forever
  python simulator.py --scenario 3           # single scenario by number
  python simulator.py --city Mumbai          # set city for weather mode
  python simulator.py --interval 3           # seconds between each send
"""

import asyncio
import argparse
import random
import os
import httpx
from typing import Optional

from weather import fetch_weather, get_mock_weather, get_city_supply, INDIAN_CITIES

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Config ─────────────────────────────────────────────────────────────────────

BACKEND_URL        = os.getenv("BACKEND_URL", "http://localhost:8000")
HEATWAVE_THRESHOLD = 40.0

# Grid zones — realistic Indian power distribution zones
BASE_ZONES = [
    {"name": "zone_hospital_district",   "protected": True,  "base_demand": 80},
    {"name": "zone_metro_rail",          "protected": True,  "base_demand": 120},
    {"name": "zone_airport",             "protected": True,  "base_demand": 100},
    {"name": "zone_industrial_east",     "protected": False, "base_demand": 300},
    {"name": "zone_industrial_west",     "protected": False, "base_demand": 250},
    {"name": "zone_residential_north",   "protected": False, "base_demand": 200},
    {"name": "zone_residential_south",   "protected": False, "base_demand": 180},
    {"name": "zone_commercial_downtown", "protected": False, "base_demand": 160},
]

# Preset scenarios — from calm to critical
SCENARIOS = [
    {
        "name": "Normal Operation",
        "description": "Grid stable. Supply comfortably meets demand.",
        "demand": 1200, "supply": 1500, "temperature": 27.0, "zone_multiplier": 0.85,
    },
    {
        "name": "Afternoon Peak",
        "description": "Temperature rising. AC load pushing demand up.",
        "demand": 1600, "supply": 1550, "temperature": 37.0, "zone_multiplier": 1.1,
    },
    {
        "name": "Heatwave Stress",
        "description": "Heatwave. Demand significantly exceeds supply.",
        "demand": 1900, "supply": 1500, "temperature": 44.0, "zone_multiplier": 1.35,
    },
    {
        "name": "Generator Trip (Critical)",
        "description": "Major generator offline during peak. Critical deficit.",
        "demand": 2100, "supply": 1100, "temperature": 47.5, "zone_multiplier": 1.5,
    },
    {
        "name": "Night Recovery",
        "description": "Late night. Demand falling, grid stabilising.",
        "demand": 850, "supply": 1400, "temperature": 30.0, "zone_multiplier": 0.6,
    },
]

# ── Grid helpers ───────────────────────────────────────────────────────────────

def temperature_multiplier(temp: float) -> float:
    """
    Higher temperature = more AC usage = higher demand.
    Tuned for Indian climate — heatwaves above 40C are common.
    """
    if temp > HEATWAVE_THRESHOLD:
        # +5% demand per degree above 40C, capped at 2.2x
        return min(1.0 + (temp - HEATWAVE_THRESHOLD) * 0.05, 2.2)
    elif temp < 10:
        # Cold weather heating
        return min(1.0 + (10 - temp) * 0.02, 1.4)
    elif temp > 32:
        # Warm — moderate AC load
        return 1.0 + (temp - 32) * 0.02
    return 1.0


def build_zones(multiplier: float) -> list:
    """Generate zone list with demand scaled by multiplier + small random noise."""
    zones = []
    for z in BASE_ZONES:
        demand = z["base_demand"] * multiplier * random.uniform(0.95, 1.05)
        zones.append({
            "name":      z["name"],
            "protected": z["protected"],
            "demand":    round(demand, 2),
        })
    return zones


def build_payload(demand: float, supply: float, temperature: float, zone_multiplier: float) -> dict:
    return {
        "demand":      round(demand, 2),
        "supply":      round(supply, 2),
        "temperature": round(temperature, 1),
        "zones":       build_zones(zone_multiplier),
    }

# ── Backend send ───────────────────────────────────────────────────────────────

async def send(payload: dict) -> None:
    """POST grid state to backend and print the AI response."""
    deficit = payload["demand"] - payload["supply"]
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r    = await client.post(f"{BACKEND_URL}/grid-state", json=payload)
            data = r.json()

            risk  = data.get("risk_level",    "?").upper()
            ml    = data.get("ml_risk_level", "?")
            hitl  = "HUMAN REQUIRED" if data.get("requires_human_approval") else "auto"
            plans = data.get("plans_generated", "?")
            icon  = {"LOW": "✅", "MEDIUM": "⚠️", "HIGH": "🔴", "CRITICAL": "🚨"}.get(risk, "❓")

            print(f"  {icon} Risk: {risk:<10} ML: {ml:<10} Plans: {plans}  HITL: {hitl}")
            if deficit > 0:
                print(f"     Deficit: {deficit:.1f} MW  |  Temp: {payload['temperature']}C")

    except httpx.ConnectError:
        print("  Cannot connect to backend.")
        print("  Make sure it is running: cd backend && uvicorn main:app --reload")
    except Exception as e:
        print(f"  Error: {e}")

# ── Simulation modes ───────────────────────────────────────────────────────────

async def mode_scenarios(interval: float, single: Optional[int] = None):
    """Run preset scenarios — all at once or pick one by number."""
    indices = [single - 1] if single else range(len(SCENARIOS))
    for i in indices:
        s = SCENARIOS[i]
        print(f"\n{'─'*60}")
        print(f"  Scenario {i+1}: {s['name']}")
        print(f"  {s['description']}")
        print(f"  Demand: {s['demand']} MW  |  Supply: {s['supply']} MW  |  Temp: {s['temperature']}C")
        print(f"{'─'*60}")
        payload = build_payload(s["demand"], s["supply"], s["temperature"], s["zone_multiplier"])
        await send(payload)
        if single is None and i < len(SCENARIOS) - 1:
            print(f"\n  Waiting {interval}s...")
            await asyncio.sleep(interval)


async def mode_escalate(interval: float):
    """
    Best mode for live demo.
    Grid starts calm, stress builds step by step, hits critical,
    then recovers. Loops forever so judges can watch the full arc.
    """
    steps = [
        (1100, 1500, 26,  "Morning — grid calm"),
        (1300, 1500, 30,  "Mid-morning — demand rising"),
        (1550, 1500, 35,  "Noon — approaching threshold"),
        (1750, 1480, 39,  "Early afternoon — tight supply"),
        (1950, 1450, 43,  "Peak heatwave — overload begins"),
        (2150, 1400, 46,  "Generator struggling"),
        (2300, 1100, 48,  "CRITICAL — generator trip"),
        (2100, 1200, 47,  "Still critical — cascading risk"),
        (1800, 1350, 44,  "Emergency supply restored"),
        (1500, 1450, 40,  "Slowly recovering"),
        (1200, 1500, 34,  "Evening cool-down"),
        (900,  1500, 29,  "Night — grid stable"),
    ]

    cycle = 0
    print(f"\n  Escalation mode | Interval: {interval}s | Ctrl+C to stop\n")

    while True:
        cycle += 1
        print(f"\n{'='*60}")
        print(f"  ESCALATION CYCLE {cycle}")
        print(f"{'='*60}")

        for demand, supply, temp, label in steps:
            # Small random noise so it looks like live data
            d  = demand + random.uniform(-30, 30)
            s  = supply + random.uniform(-20, 20)
            t  = temp   + random.uniform(-0.5, 0.5)
            zm = temperature_multiplier(t)

            print(f"\n  {label}")
            print(f"  Demand: {d:.0f} MW  |  Supply: {s:.0f} MW  |  Temp: {t:.1f}C")
            payload = build_payload(d, s, t, zm)
            await send(payload)
            await asyncio.sleep(interval)


async def mode_weather(city: str, interval: float):
    """Fetch real (or mock) weather for one city and simulate grid."""
    print(f"\n  Weather mode | City: {city} | Interval: {interval}s | Ctrl+C to stop\n")
    base_supply = get_city_supply(city)
    iteration   = 0

    while True:
        weather      = await fetch_weather(city)
        temp         = weather["temperature"]
        mult         = temperature_multiplier(temp)
        supply       = base_supply * random.uniform(0.95, 1.05)
        total_demand = sum(z["base_demand"] for z in BASE_ZONES) * mult * random.uniform(0.97, 1.03)

        print(f"\n  [{iteration}] {weather['city']} | {temp}C | {weather['description']}")
        print(f"  Source: {'real API' if weather.get('real') else 'mock data — add OPENWEATHER_API_KEY to .env for real weather'}")

        payload = build_payload(total_demand, supply, temp, mult)
        await send(payload)

        iteration += 1
        await asyncio.sleep(interval)


async def mode_cities(interval: float):
    """Cycle through all Indian cities continuously."""
    print(f"\n  Multi-city mode | Interval: {interval}s | Ctrl+C to stop\n")
    i = 0

    while True:
        city_data = INDIAN_CITIES[i % len(INDIAN_CITIES)]
        weather   = await fetch_weather(city_data["city"])
        temp      = weather["temperature"]
        mult      = temperature_multiplier(temp)
        supply    = city_data["supply"] * random.uniform(0.93, 1.07)
        demand    = sum(z["base_demand"] for z in BASE_ZONES) * mult * (city_data["supply"] / 1500)

        print(f"\n  {city_data['city']} | {temp}C | {weather['description']}")
        payload = build_payload(demand, supply, temp, mult)
        await send(payload)

        i += 1
        await asyncio.sleep(interval)


async def mode_random(interval: float):
    """Send random but plausible grid states forever."""
    print(f"\n  Random mode | Interval: {interval}s | Ctrl+C to stop\n")
    i = 0

    while True:
        temp   = random.uniform(24, 52)
        mult   = temperature_multiplier(temp)
        demand = random.uniform(800, 2400)
        supply = demand * random.uniform(0.65, 1.35)

        print(f"\n  [{i}] Temp: {temp:.1f}C | Demand: {demand:.0f} MW | Supply: {supply:.0f} MW")
        payload = build_payload(demand, supply, temp, mult)
        await send(payload)

        i += 1
        await asyncio.sleep(interval)

# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Smart Grid Simulator (Sanya)")
    parser.add_argument("--mode",     default="scenarios",
                        choices=["scenarios", "escalate", "weather", "cities", "random"],
                        help="Simulation mode (default: scenarios)")
    parser.add_argument("--scenario", type=int,    help="Run single scenario 1-5")
    parser.add_argument("--city",     default="Delhi", help="City for weather mode")
    parser.add_argument("--interval", type=float,  default=5.0,
                        help="Seconds between sends (default: 5)")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  Smart Grid Simulator — Enhanced (Sanya)")
    print("="*60)
    print(f"  Backend  : {BACKEND_URL}")
    print(f"  Mode     : {args.mode}")
    print(f"  Interval : {args.interval}s")
    print(f"  Weather  : {'real API' if os.getenv('OPENWEATHER_API_KEY') else 'mock (add OPENWEATHER_API_KEY to .env for real data)'}")
    print("="*60)

    try:
        if args.scenario:
            await mode_scenarios(args.interval, single=args.scenario)
        elif args.mode == "escalate":
            await mode_escalate(args.interval)
        elif args.mode == "weather":
            await mode_weather(args.city, args.interval)
        elif args.mode == "cities":
            await mode_cities(args.interval)
        elif args.mode == "random":
            await mode_random(args.interval)
        else:
            await mode_scenarios(args.interval)
    except KeyboardInterrupt:
        print("\n\n  Simulator stopped.\n")

    print("\n  Done.\n")


if __name__ == "__main__":
    asyncio.run(main())

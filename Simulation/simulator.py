"""
Smart Grid Simulator
====================
Usage:
  python simulator.py                    # run all 5 scenarios once
  python simulator.py --mode escalate    # best for live demo
  python simulator.py --mode weather     # real/mock weather
  python simulator.py --mode cities      # cycles Indian cities
  python simulator.py --mode random      # random data forever
  python simulator.py --scenario 3       # single scenario
  python simulator.py --city Mumbai      # set city for weather mode
  python simulator.py --interval 3       # seconds between sends
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

# Zone names match exactly what backend optimizer expects
BASE_ZONES = [
    {"name": "hospital",     "protected": True,  "base_demand": 80},
    {"name": "airport",      "protected": True,  "base_demand": 100},
    {"name": "metro_rail",   "protected": True,  "base_demand": 120},
    {"name": "industry1",    "protected": False, "base_demand": 300},
    {"name": "industry2",    "protected": False, "base_demand": 250},
    {"name": "residential1", "protected": False, "base_demand": 200},
    {"name": "residential2", "protected": False, "base_demand": 180},
    {"name": "commercial1",  "protected": False, "base_demand": 160},
]

# Preset scenarios — calm to critical
SCENARIOS = [
    {
        "name":        "Normal Operation",
        "description": "Grid stable. Supply comfortably meets demand.",
        "demand": 1200, "supply": 1500, "temperature": 27.0, "zone_multiplier": 0.85,
    },
    {
        "name":        "Afternoon Peak",
        "description": "Temperature rising. AC load pushing demand up.",
        "demand": 1600, "supply": 1550, "temperature": 37.0, "zone_multiplier": 1.1,
    },
    {
        "name":        "Heatwave Stress",
        "description": "Heatwave. Demand significantly exceeds supply.",
        "demand": 1900, "supply": 1500, "temperature": 44.0, "zone_multiplier": 1.35,
    },
    {
        "name":        "Generator Trip (Critical)",
        "description": "Major generator offline during peak. Critical deficit.",
        "demand": 2100, "supply": 1100, "temperature": 47.5, "zone_multiplier": 1.5,
    },
    {
        "name":        "Night Recovery",
        "description": "Late night. Demand falling, grid stabilising.",
        "demand": 850, "supply": 1400, "temperature": 30.0, "zone_multiplier": 0.6,
    },
]

# ── Grid helpers ───────────────────────────────────────────────────────────────

def temperature_multiplier(temp: float) -> float:
    """Higher temp = more AC = higher demand. Tuned for Indian climate."""
    if temp > HEATWAVE_THRESHOLD:
        return min(1.0 + (temp - HEATWAVE_THRESHOLD) * 0.05, 2.2)
    elif temp < 10:
        return min(1.0 + (10 - temp) * 0.02, 1.4)
    elif temp > 32:
        return 1.0 + (temp - 32) * 0.02
    return 1.0


def build_zones(multiplier: float) -> list:
    """Zone list with demand scaled by multiplier + small random noise."""
    return [
        {
            "name":      z["name"],
            "protected": z["protected"],
            "demand":    round(z["base_demand"] * multiplier * random.uniform(0.95, 1.05), 2),
        }
        for z in BASE_ZONES
    ]


def build_payload(demand: float, supply: float, temperature: float, zone_multiplier: float) -> dict:
    """Build exact payload shape expected by POST /grid-state."""
    return {
        "demand":      round(demand, 2),
        "supply":      round(supply, 2),
        "temperature": round(temperature, 1),
        "zones":       build_zones(zone_multiplier),
    }

# ── Backend send ───────────────────────────────────────────────────────────────

async def send(payload: dict) -> None:
    """POST grid state to backend and print the AI response summary."""
    deficit = payload["demand"] - payload["supply"]
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r    = await client.post(f"{BACKEND_URL}/grid-state", json=payload)
            data = r.json()

            risk  = data.get("risk_level",    "?").upper()
            ml    = data.get("ml_risk_level", "?")
            llm   = data.get("llm_risk_level","?")
            hitl  = "🚨 HUMAN REQUIRED" if data.get("requires_human_approval") else "✅ auto"
            plans = data.get("plans_generated", "?")
            icon  = {"LOW": "✅", "MEDIUM": "⚠️ ", "HIGH": "🔴", "CRITICAL": "🚨"}.get(risk, "❓")

            print(f"  {icon} Risk: {risk:<10} ML:{ml:<10} LLM:{llm:<10} Plans:{plans}  {hitl}")
            if deficit > 0:
                print(f"     Deficit: {deficit:.1f}MW | Temp: {payload['temperature']}°C")

    except httpx.ConnectError:
        print(f"  ✗ Cannot connect to {BACKEND_URL}")
        print("    Run: cd backend && python3 -m uvicorn main:app --reload")
    except Exception as e:
        print(f"  ✗ Error: {e}")

# ── Simulation modes ───────────────────────────────────────────────────────────

async def mode_scenarios(interval: float, single: Optional[int] = None):
    """Run preset scenarios — all at once or pick one by number."""
    indices = [single - 1] if single else range(len(SCENARIOS))
    for i in indices:
        s = SCENARIOS[i]
        print(f"\n{'─'*60}")
        print(f"  Scenario {i+1}: {s['name']}")
        print(f"  {s['description']}")
        print(f"  D:{s['demand']}MW  S:{s['supply']}MW  T:{s['temperature']}°C")
        print(f"{'─'*60}")
        payload = build_payload(s["demand"], s["supply"], s["temperature"], s["zone_multiplier"])
        await send(payload)
        if single is None and i < len(SCENARIOS) - 1:
            print(f"\n  Waiting {interval}s...")
            await asyncio.sleep(interval)


async def mode_escalate(interval: float):
    """
    Best mode for live demo.
    Grid starts calm → builds stress → hits critical → recovers.
    Loops forever so judges can watch the full arc.
    """
    steps = [
        (1100, 1500, 26,   "🌅 Morning — grid calm"),
        (1300, 1500, 30,   "☀️  Mid-morning — demand rising"),
        (1550, 1500, 35,   "🌤  Noon — approaching threshold"),
        (1750, 1480, 39,   "🌡  Early afternoon — tight supply"),
        (1950, 1450, 43,   "🔥 Peak heatwave — overload begins"),
        (2150, 1400, 46,   "⚡ Generator struggling"),
        (2300, 1100, 48,   "🚨 CRITICAL — generator trip"),
        (2100, 1200, 47,   "🚨 Still critical — cascading risk"),
        (1800, 1350, 44,   "🔴 Emergency supply restored"),
        (1500, 1450, 40,   "⚠️  Slowly recovering"),
        (1200, 1500, 34,   "✅ Evening cool-down"),
        (900,  1500, 29,   "✅ Night — grid stable"),
    ]

    cycle = 0
    print(f"\n  Escalation mode | Interval: {interval}s | Ctrl+C to stop\n")

    while True:
        cycle += 1
        print(f"\n{'='*60}")
        print(f"  ESCALATION CYCLE {cycle}")
        print(f"{'='*60}")

        for demand, supply, temp, label in steps:
            d  = demand + random.uniform(-30, 30)
            s  = supply + random.uniform(-20, 20)
            t  = temp   + random.uniform(-0.5, 0.5)
            zm = temperature_multiplier(t)

            print(f"\n  {label}")
            print(f"  D:{d:.0f}MW  S:{s:.0f}MW  T:{t:.1f}°C")
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

        src = "real API" if weather.get("real") else "mock"
        print(f"\n  [{iteration:03}] {weather['city']} | {temp}°C | {weather['description']} ({src})")
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

        print(f"\n  {city_data['city']} | {temp}°C | {weather['description']}")
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

        print(f"\n  [{i:03}] T:{temp:.1f}°C  D:{demand:.0f}MW  S:{supply:.0f}MW")
        payload = build_payload(demand, supply, temp, mult)
        await send(payload)

        i += 1
        await asyncio.sleep(interval)

# ── Entry point ────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Smart Grid Simulator")
    parser.add_argument(
        "--mode", default="scenarios",
        choices=["scenarios", "escalate", "weather", "cities", "random"],
        help="Simulation mode (default: scenarios)"
    )
    parser.add_argument("--scenario", type=int,   help="Run single scenario 1-5")
    parser.add_argument("--city",     default="Delhi", help="City for weather mode")
    parser.add_argument("--interval", type=float, default=5.0, help="Seconds between sends")
    args = parser.parse_args()

    api_status = "real API ✅" if os.getenv("OPENWEATHER_API_KEY") else "mock data (add OPENWEATHER_API_KEY to .env for real weather)"

    print("\n" + "="*60)
    print("  Smart Grid Simulator")
    print("="*60)
    print(f"  Backend  : {BACKEND_URL}")
    print(f"  Mode     : {args.mode}")
    print(f"  Interval : {args.interval}s")
    print(f"  Weather  : {api_status}")
    print(f"  Zones    : {len(BASE_ZONES)} ({sum(1 for z in BASE_ZONES if z['protected'])} protected)")
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


if __name__ == "__main__":
    asyncio.run(main())
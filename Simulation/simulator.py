"""
Smart Grid Simulator — Enhanced Version (Sanya)
================================================
Usage:
  python simulator.py                        # run all 5 scenarios once
  python simulator.py --mode escalate        # best for live demo
  python simulator.py --mode weather         # real/mock weather, one city
  python simulator.py --mode cities          # cycles all Indian cities
  python simulator.py --mode random          # random data forever
  python simulator.py --scenario 3           # single scenario by number
  python simulator.py --city Mumbai          # set city for weather mode
  python simulator.py --interval 15          # seconds between each send
"""

import asyncio
import argparse
import random
import os
import httpx
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BACKEND_URL         = os.getenv("BACKEND_URL", "http://localhost:8000")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_URL     = "https://api.openweathermap.org/data/2.5/weather"
HEATWAVE_THRESHOLD  = 40.0

INDIAN_CITIES = [
    {"city": "Delhi",   "supply": 7000},
    {"city": "Mumbai",  "supply": 4500},
    {"city": "Chennai", "supply": 3800},
    {"city": "Kolkata", "supply": 3200},
    {"city": "Pune",    "supply": 2800},
]

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

# 5 scenarios covering ALL risk levels — low, medium, high, critical, recovery
SCENARIOS = [
    {
        "name": "Normal Operation",
        "description": "Grid stable. Supply comfortably exceeds demand. Expected: LOW risk.",
        "demand": 900,   "supply": 1500, "temperature": 24.0, "zone_multiplier": 0.65,
    },
    {
        "name": "Afternoon Peak",
        "description": "Warm day, AC load rising. Supply still ahead. Expected: MEDIUM risk.",
        "demand": 1420,  "supply": 1500, "temperature": 34.0, "zone_multiplier": 1.0,
    },
    {
        "name": "Heatwave Stress",
        "description": "Heatwave. Demand exceeds supply. Expected: HIGH risk, HITL triggered.",
        "demand": 1800,  "supply": 1500, "temperature": 43.0, "zone_multiplier": 1.3,
    },
    {
        "name": "Generator Trip (Critical)",
        "description": "Generator offline during peak heatwave. Expected: CRITICAL, HITL triggered.",
        "demand": 2100,  "supply": 1000, "temperature": 48.0, "zone_multiplier": 1.5,
    },
    {
        "name": "Night Recovery",
        "description": "Late night. Demand falling sharply. Expected: LOW risk.",
        "demand": 750,   "supply": 1500, "temperature": 27.0, "zone_multiplier": 0.55,
    },
]

# ── Weather ────────────────────────────────────────────────────────────────────

async def fetch_weather(city: str) -> dict:
    if not OPENWEATHER_API_KEY:
        return mock_weather(city)
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(OPENWEATHER_URL, params={
                "q": city, "appid": OPENWEATHER_API_KEY, "units": "metric"
            })
            if r.status_code == 200:
                d = r.json()
                return {
                    "city":        d["name"],
                    "temperature": d["main"]["temp"],
                    "humidity":    d["main"]["humidity"],
                    "description": d["weather"][0]["description"],
                    "wind_speed":  d["wind"]["speed"],
                    "real":        True,
                }
            return mock_weather(city)
    except Exception:
        return mock_weather(city)


def mock_weather(city: str) -> dict:
    temp = random.choices(
        [random.uniform(25, 33), random.uniform(33, 39),
         random.uniform(39, 45), random.uniform(45, 50)],
        weights=[0.3, 0.35, 0.25, 0.1]
    )[0]
    return {
        "city": city, "temperature": round(temp, 1),
        "humidity": random.randint(30, 85),
        "description": random.choice(["clear sky", "haze", "hot and humid", "dust haze"]),
        "wind_speed": round(random.uniform(0, 25), 1), "real": False,
    }

# ── Grid helpers ───────────────────────────────────────────────────────────────

def temperature_multiplier(temp: float) -> float:
    if temp > HEATWAVE_THRESHOLD:
        return min(1.0 + (temp - HEATWAVE_THRESHOLD) * 0.05, 2.2)
    elif temp < 10:
        return min(1.0 + (10 - temp) * 0.02, 1.4)
    elif temp > 32:
        return 1.0 + (temp - 32) * 0.02
    return 1.0


def build_zones(multiplier: float) -> list:
    return [
        {"name": z["name"], "protected": z["protected"],
         "demand": round(z["base_demand"] * multiplier * random.uniform(0.95, 1.05), 2)}
        for z in BASE_ZONES
    ]


def build_payload(demand: float, supply: float, temperature: float, zone_multiplier: float) -> dict:
    return {
        "demand":      round(demand, 2),
        "supply":      round(supply, 2),
        "temperature": round(temperature, 1),
        "zones":       build_zones(zone_multiplier),
    }

# ── Backend send ───────────────────────────────────────────────────────────────

async def send(payload: dict) -> None:
    deficit = payload["demand"] - payload["supply"]
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r    = await client.post(f"{BACKEND_URL}/grid-state", json=payload)
            data = r.json()
            risk  = data.get("risk_level",    "?").upper()
            ml    = data.get("ml_risk_level", "?")
            hitl  = "🚨 HUMAN REQUIRED" if data.get("requires_human_approval") else "✅ auto"
            plans = data.get("plans_generated", "?")
            icon  = {"LOW": "✅", "MEDIUM": "⚠️", "HIGH": "🔴", "CRITICAL": "🚨"}.get(risk, "❓")
            print(f"  {icon} Risk: {risk:<10} ML: {ml:<10} Plans: {plans}  HITL: {hitl}")
            if deficit > 0:
                print(f"     Deficit: {deficit:.1f} MW  |  Temp: {payload['temperature']}C")
    except httpx.ConnectError:
        print("  Cannot connect to backend.")
        print("  Run: cd backend && python -m uvicorn main:app --reload")
    except Exception as e:
        print(f"  Error: {e}")

# ── Modes ──────────────────────────────────────────────────────────────────────

async def mode_scenarios(interval: float, single: Optional[int] = None):
    """Runs all 5 scenarios covering LOW → MEDIUM → HIGH → CRITICAL → LOW"""
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
    Best for live demo. Grid starts LOW, builds to CRITICAL, then recovers.
    Clearly shows all 4 risk levels including HITL trigger. Loops forever.
    """
    steps = [
        # (demand, supply, temp,  label,                        expected risk)
        (800,  1500, 24,  "Early morning — grid very calm",     "LOW"),
        (1000, 1500, 27,  "Morning — stable operation",         "LOW"),
        (1300, 1500, 32,  "Mid-morning — demand rising",        "LOW/MEDIUM"),
        (1450, 1500, 36,  "Noon — approaching supply limit",    "MEDIUM"),
        (1600, 1480, 39,  "Early afternoon — tight supply",     "MEDIUM"),
        (1800, 1450, 43,  "Peak heatwave — demand over supply", "HIGH"),
        (1950, 1400, 46,  "Generator struggling badly",         "HIGH"),
        (2200, 1000, 49,  "CRITICAL — generator trip",          "CRITICAL"),
        (2100, 1100, 48,  "Still critical — cascading risk",    "CRITICAL"),
        (1700, 1350, 44,  "Emergency supply restored",          "HIGH"),
        (1400, 1480, 38,  "Slowly recovering",                  "MEDIUM"),
        (1100, 1500, 32,  "Evening cool-down",                  "LOW"),
        (800,  1500, 26,  "Night — grid fully stable",          "LOW"),
    ]

    cycle = 0
    print(f"\n  Escalation mode | Interval: {interval}s | Ctrl+C to stop\n")

    while True:
        cycle += 1
        print(f"\n{'='*60}")
        print(f"  ESCALATION CYCLE {cycle}")
        print(f"{'='*60}")

        for demand, supply, temp, label, expected in steps:
            d  = demand + random.uniform(-20, 20)
            s  = supply + random.uniform(-15, 15)
            t  = temp   + random.uniform(-0.3, 0.3)
            zm = temperature_multiplier(t)
            print(f"\n  {label}  (expected: {expected})")
            print(f"  Demand: {d:.0f} MW  |  Supply: {s:.0f} MW  |  Temp: {t:.1f}C")
            payload = build_payload(d, s, t, zm)
            await send(payload)
            await asyncio.sleep(interval)


async def mode_weather(city: str, interval: float):
    print(f"\n  Weather mode | City: {city} | Interval: {interval}s | Ctrl+C to stop\n")
    base_supply = next((c["supply"] for c in INDIAN_CITIES if c["city"] == city), 1500)
    i = 0
    while True:
        weather      = await fetch_weather(city)
        temp         = weather["temperature"]
        mult         = temperature_multiplier(temp)
        supply       = base_supply * random.uniform(0.95, 1.05)
        total_demand = sum(z["base_demand"] for z in BASE_ZONES) * mult * random.uniform(0.97, 1.03)
        print(f"\n  [{i}] {weather['city']} | {temp}C | {weather['description']}")
        print(f"  Source: {'real API' if weather.get('real') else 'mock data'}")
        payload = build_payload(total_demand, supply, temp, mult)
        await send(payload)
        i += 1
        await asyncio.sleep(interval)


async def mode_cities(interval: float):
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

# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    parser = argparse.ArgumentParser(description="Smart Grid Simulator (Sanya)")
    parser.add_argument("--mode",     default="scenarios",
                        choices=["scenarios", "escalate", "weather", "cities", "random"])
    parser.add_argument("--scenario", type=int,   help="Run single scenario 1-5")
    parser.add_argument("--city",     default="Delhi")
    parser.add_argument("--interval", type=float, default=15.0,
                        help="Seconds between sends (default: 15)")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  Smart Grid Simulator — Enhanced (Sanya)")
    print("="*60)
    print(f"  Backend  : {BACKEND_URL}")
    print(f"  Mode     : {args.mode}")
    print(f"  Interval : {args.interval}s")
    print(f"  Weather  : {'real API' if OPENWEATHER_API_KEY else 'mock'}")
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

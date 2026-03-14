"""
Weather module — fetches real-time weather data.
Uses OpenWeatherMap free API with async httpx (faster than requests).

Setup (optional):
  Add OPENWEATHER_API_KEY=your_key to your .env file
  Get a free key at: https://openweathermap.org/api
  Works fine without a key — just uses mock data instead.
"""

import random
import os
import httpx
from typing import Dict, Any

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OPENWEATHER_URL     = "https://api.openweathermap.org/data/2.5/weather"

# Indian cities with realistic base grid supply in MW
INDIAN_CITIES = [
    {"city": "Delhi",   "supply": 7000},
    {"city": "Mumbai",  "supply": 4500},
    {"city": "Chennai", "supply": 3800},
    {"city": "Kolkata", "supply": 3200},
    {"city": "Pune",    "supply": 2800},
]


async def fetch_weather(city: str) -> Dict[str, Any]:
    """
    Fetch real weather for a city asynchronously.
    Falls back to mock data if no API key or call fails.
    """
    if not OPENWEATHER_API_KEY:
        return get_mock_weather(city)

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(OPENWEATHER_URL, params={
                "q":     city,
                "appid": OPENWEATHER_API_KEY,
                "units": "metric"
            })

            if response.status_code == 200:
                d = response.json()
                return {
                    "city":        d["name"],
                    "country":     d["sys"]["country"],
                    "temperature": d["main"]["temp"],
                    "feels_like":  d["main"]["feels_like"],
                    "humidity":    d["main"]["humidity"],
                    "pressure":    d["main"]["pressure"],
                    "description": d["weather"][0]["description"],
                    "wind_speed":  d["wind"]["speed"],
                    "clouds":      d["clouds"]["all"],
                    "real":        True,
                }

            elif response.status_code == 401:
                print("  Weather API: invalid key — using mock data")
            elif response.status_code == 404:
                print(f"  Weather API: city '{city}' not found — using mock data")
            else:
                print(f"  Weather API returned {response.status_code} — using mock data")

            return get_mock_weather(city)

    except httpx.TimeoutException:
        print("  Weather API timed out — using mock data")
        return get_mock_weather(city)
    except Exception as e:
        print(f"  Weather fetch failed ({e}) — using mock data")
        return get_mock_weather(city)


def get_mock_weather(city: str) -> Dict[str, Any]:
    """
    Returns realistic mock weather biased toward Indian summer conditions.
    """
    temp = random.choices(
        population=[
            random.uniform(25, 33),  # pleasant
            random.uniform(33, 39),  # warm
            random.uniform(39, 45),  # heatwave
            random.uniform(45, 50),  # extreme heat
        ],
        weights=[0.3, 0.35, 0.25, 0.1]
    )[0]

    return {
        "city":        city,
        "country":     "IN",
        "temperature": round(temp, 1),
        "feels_like":  round(temp + random.uniform(1, 4), 1),
        "humidity":    random.randint(30, 85),
        "pressure":    random.randint(990, 1015),
        "description": random.choice([
            "clear sky", "haze", "hot and humid",
            "dust haze", "partly cloudy", "thunderstorm nearby"
        ]),
        "wind_speed":  round(random.uniform(0, 25), 1),
        "clouds":      random.randint(0, 80),
        "real":        False,
    }


def get_city_supply(city: str) -> int:
    """
    Returns base grid supply in MW for a known Indian city.
    Falls back to 1500 MW if city not in list.
    """
    for c in INDIAN_CITIES:
        if c["city"].lower() == city.lower():
            return c["supply"]
    return 1500
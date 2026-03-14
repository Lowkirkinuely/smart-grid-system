"""
Weather API integration for fetching real-time weather data.
Uses OpenWeatherMap free API.

Setup:
1. Get free API key at: https://openweathermap.org/api
2. Set OPENWEATHER_API_KEY in .env file
"""

import requests
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "demo")
OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


class WeatherAPI:
    """Interface for OpenWeatherMap API."""
    
    def __init__(self, api_key: str = OPENWEATHER_API_KEY):
        """
        Initialize WeatherAPI client.
        
        Args:
            api_key: OpenWeatherMap API key (get free key at https://openweathermap.org/api)
        """
        self.api_key = api_key
        self.base_url = OPENWEATHER_URL
    
    def get_weather(self, city: str) -> Dict[str, Any]:
        """
        Fetch weather data for a city.
        
        Args:
            city: City name (e.g., "London", "New York")
        
        Returns:
            Dictionary with temperature, humidity, description
        """
        try:
            params = {
                "q": city,
                "appid": self.api_key,
                "units": "metric"  # Use Celsius
            }
            
            response = requests.get(self.base_url, params=params, timeout=5)
            response.raise_for_status()
            
            data = response.json()
            
            return {
                "status": "success",
                "city": data["name"],
                "country": data["sys"]["country"],
                "temperature": data["main"]["temp"],
                "feels_like": data["main"]["feels_like"],
                "humidity": data["main"]["humidity"],
                "pressure": data["main"]["pressure"],
                "description": data["weather"][0]["description"],
                "wind_speed": data["wind"]["speed"],
                "clouds": data["clouds"]["all"],
            }
        
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                return {
                    "status": "error",
                    "error": "Invalid API key. Get free key at https://openweathermap.org/api",
                    "using_mock": True
                }
            elif response.status_code == 404:
                return {
                    "status": "error",
                    "error": f"City not found: {city}",
                    "using_mock": True
                }
            else:
                return {
                    "status": "error",
                    "error": str(e),
                    "using_mock": True
                }
        
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "using_mock": True
            }
    
    @staticmethod
    def get_mock_weather(city: str = "London") -> Dict[str, Any]:
        """
        Return mock weather data (for testing without API key).
        
        Args:
            city: City name
        
        Returns:
            Mock weather dictionary
        """
        import random
        
        # Generate realistic mock data
        base_temp = random.uniform(15, 42)  # Range from cold to heatwave
        
        return {
            "status": "success (mock)",
            "city": city,
            "country": "UK",
            "temperature": round(base_temp, 1),
            "feels_like": round(base_temp - 2, 1),
            "humidity": random.randint(30, 90),
            "pressure": random.randint(990, 1030),
            "description": random.choice(["clear sky", "few clouds", "scattered clouds", "broken clouds"]),
            "wind_speed": random.uniform(0, 20),
            "clouds": random.randint(0, 100),
        }


def fetch_weather(city: str, use_mock: bool = False) -> Dict[str, Any]:
    """
    Convenience function to fetch weather data.
    
    Args:
        city: City name
        use_mock: Use mock data instead of real API
    
    Returns:
        Weather data dictionary
    """
    if use_mock:
        return WeatherAPI.get_mock_weather(city)
    
    weather = WeatherAPI()
    result = weather.get_weather(city)
    
    # If API fails, use mock data as fallback
    if result.get("status") == "error" or result.get("using_mock"):
        print(f"⚠️  Weather API error: {result.get('error')}")
        print("📊 Using mock weather data instead")
        return WeatherAPI.get_mock_weather(city)
    
    return result

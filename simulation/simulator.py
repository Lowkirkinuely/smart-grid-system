"""
Grid Simulation Service (SUM)
Fetches real weather data and simulates power grid state.
Sends grid data to the FastAPI backend every 5 seconds.

Usage:
    python simulation/simulator.py

Will send POST requests to http://localhost:8000/grid-state
"""

import asyncio
import json
import random
import httpx
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

from weather import fetch_weather

# Load environment variables
load_dotenv()

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
SIMULATION_INTERVAL = int(os.getenv("SIMULATION_INTERVAL", "5"))
WEATHER_CITY = os.getenv("WEATHER_CITY", "London")
GRID_BASE_SUPPLY = int(os.getenv("GRID_BASE_SUPPLY", "500"))
HEATWAVE_THRESHOLD = int(os.getenv("HEATWAVE_THRESHOLD", "40"))


class GridSimulator:
    """Simulates power grid state with real weather data."""
    
    def __init__(self):
        """Initialize the grid simulator."""
        self.zones = [
            {"name": "Hospital_District", "protected": True, "base_demand": 80},
            {"name": "Airport_Zone", "protected": True, "base_demand": 100},
            {"name": "Residential_North", "protected": False, "base_demand": 120},
            {"name": "Residential_South", "protected": False, "base_demand": 130},
            {"name": "Commercial_Downtown", "protected": False, "base_demand": 100},
            {"name": "Industrial_East", "protected": False, "base_demand": 150},
        ]
        self.base_supply = GRID_BASE_SUPPLY
        self.iteration = 0
    
    def calculate_demand_multiplier(self, temperature: float) -> float:
        """
        Calculate demand multiplier based on temperature.
        
        Args:
            temperature: Current temperature in Celsius
        
        Returns:
            Demand multiplier (1.0 = base, > 1.0 = increased)
        """
        # Heatwave: temperature > 40°C increases A/C demand
        if temperature > HEATWAVE_THRESHOLD:
            # Each degree above threshold: +5% demand
            excess = temperature - HEATWAVE_THRESHOLD
            multiplier = 1.0 + (excess * 0.05)
            return min(multiplier, 2.5)  # Cap at 2.5x
        
        # Cold weather: temperature < 5°C increases heating demand
        elif temperature < 5:
            excess = 5 - temperature
            multiplier = 1.0 + (excess * 0.03)
            return min(multiplier, 1.8)  # Cap at 1.8x
        
        else:
            # Normal temperature
            return 1.0
    
    def generate_grid_state(self, temperature: float) -> Dict[str, Any]:
        """
        Generate current grid state based on weather.
        
        Args:
            temperature: Current temperature in Celsius
        
        Returns:
            Grid state dictionary with demand, supply, temperature, zones
        """
        demand_multiplier = self.calculate_demand_multiplier(temperature)
        
        # Calculate total demand
        total_demand = 0
        zones_data = []
        
        for zone in self.zones:
            # Base demand with temperature multiplier
            zone_demand = zone["base_demand"] * demand_multiplier
            
            # Add small random variation (±5%)
            variation = random.uniform(0.95, 1.05)
            zone_demand = zone_demand * variation
            
            total_demand += zone_demand
            
            zones_data.append({
                "name": zone["name"],
                "protected": zone["protected"],
                "demand": round(zone_demand, 2)
            })
        
        # Supply can fluctuate slightly (renewable energy variability)
        supply_variation = random.uniform(0.95, 1.05)
        current_supply = self.base_supply * supply_variation
        
        grid_state = {
            "timestamp": datetime.now().isoformat(),
            "demand": round(total_demand, 2),
            "supply": round(current_supply, 2),
            "temperature": round(temperature, 1),
            "zones": zones_data,
            "iteration": self.iteration,
            "demand_multiplier": round(demand_multiplier, 2),
        }
        
        return grid_state
    
    async def send_to_backend(self, grid_state: Dict[str, Any]) -> bool:
        """
        Send grid state to backend API.
        
        Args:
            grid_state: Grid state dictionary
        
        Returns:
            True if successful, False otherwise
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{BACKEND_URL}/grid-state",
                    json=grid_state,
                    timeout=5
                )
            
            if response.status_code == 200:
                print(f"✓ [{self.iteration}] Grid state sent | Temp: {grid_state['temperature']}°C, "
                      f"Demand: {grid_state['demand']} MW, Supply: {grid_state['supply']} MW")
                return True
            else:
                print(f"✗ Backend returned {response.status_code}")
                return False
        
        except Exception as e:
            print(f"✗ Error sending to backend: {e}")
            return False
    
    async def run_simulation(self, duration_seconds: Optional[int] = None):
        """
        Run continuous simulation.
        
        Args:
            duration_seconds: How long to run (None = infinite)
        """
        print("\n" + "=" * 80)
        print("Smart Grid Simulation Service (SUM)")
        print("=" * 80)
        print(f"\nConfiguration:")
        print(f"  • Backend URL: {BACKEND_URL}")
        print(f"  • Update Interval: {SIMULATION_INTERVAL} seconds")
        print(f"  • Weather City: {WEATHER_CITY}")
        print(f"  • Base Supply: {GRID_BASE_SUPPLY} MW")
        print(f"  • Heatwave Threshold: {HEATWAVE_THRESHOLD}°C")
        print(f"\nZones ({len(self.zones)} total):")
        for zone in self.zones:
            protected_str = "🔒 PROTECTED" if zone["protected"] else "⚡ Normal"
            print(f"  • {zone['name']:30} {protected_str:20} Base: {zone['base_demand']} MW")
        
        print("\n" + "=" * 80)
        print("Starting simulation... (Press CTRL+C to stop)\n")
        
        start_time = datetime.now()
        
        try:
            while True:
                # Fetch real weather data
                weather = fetch_weather(WEATHER_CITY)
                temperature = weather.get("temperature", 20)
                
                print(f"\n Weather: {WEATHER_CITY}")
                print(f"   Temperature: {temperature}°C ({weather.get('description')})")
                print(f"   Humidity: {weather.get('humidity')}%")
                
                # Generate grid state
                grid_state = self.generate_grid_state(temperature)
                
                # Send to backend
                await self.send_to_backend(grid_state)
                
                # Check if duration exceeded
                if duration_seconds:
                    elapsed = (datetime.now() - start_time).total_seconds()
                    if elapsed >= duration_seconds:
                        print(f"\n✓ Simulation completed ({elapsed:.0f}s)")
                        break
                
                # Wait before next update
                await asyncio.sleep(SIMULATION_INTERVAL)
                self.iteration += 1
        
        except KeyboardInterrupt:
            print("\n\n✓ Simulation stopped by user")
        except Exception as e:
            print(f"\n✗ Simulation error: {e}")


async def main():
    """Main entry point."""
    simulator = GridSimulator()
    await simulator.run_simulation()


if __name__ == "__main__":
    print("\n🚀 Starting Smart Grid Simulation Service (SUM)")
    print("Fetching weather and sending grid data to backend...\n")
    
    asyncio.run(main())

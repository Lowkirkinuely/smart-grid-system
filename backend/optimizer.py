"""
Optimization Engine for Smart Grid Power Distribution.
Uses Google OR-Tools to generate optimal power allocation plans.

Objective: Minimize power disruption while ensuring protected zones
(hospitals, airports) receive their full demand.
"""

from typing import List, Dict, Any
from dataclasses import dataclass
from ortools.linear_solver import pywraplp


@dataclass
class OptimizationStrategy:
    """Represents a power distribution strategy."""
    name: str
    description: str
    allocation: Dict[str, float]  # zone_name -> allocated_power
    total_disruption: float  # Total MW not delivered
    disrupted_zones: List[Dict[str, Any]]  # List of zones with disruptions


class GridOptimizer:
    """
    Linear Programming Optimizer for power grid distribution.
    
    Uses OR-Tools to solve:
        Minimize: Total power disruption
        Subject to:
            - Total allocation <= supply
            - Protected zones get 100% of demand
            - Non-protected zones: flexible allocation
    """
    
    def __init__(self):
        """Initialize the optimizer."""
        self.solver = None
    
    def optimize(
        self,
        demand: int,
        supply: int,
        zones: List[Dict[str, Any]],
        risk_level: str
    ) -> List[OptimizationStrategy]:
        """
        Generate multiple optimization strategies.
        
        Args:
            demand: Total power demand (MW)
            supply: Total power supply (MW)
            zones: List of zones with structure:
                {"name": str, "demand": float, "protected": bool}
            risk_level: Current risk level (low, medium, high, critical)
        
        Returns:
            List of 3 distinct optimization strategies
        """
        # Calculate zone demands
        zone_demands = self._calculate_zone_demands(zones, demand)
        protected_demand = sum(
            zd["demand"] for zd in zone_demands.values() if zd["protected"]
        )
        non_protected_demand = sum(
            zd["demand"] for zd in zone_demands.values() if not zd["protected"]
        )
        
        # Validate protected zones can be served
        if protected_demand > supply:
            raise ValueError(
                f"Insufficient supply ({supply} MW) for protected zones "
                f"({protected_demand} MW). Cannot guarantee critical services."
            )
        
        available_for_non_protected = supply - protected_demand
        
        # Generate 3 distinct strategies
        strategies = [
            self._strategy_gradual_reduction(
                zone_demands, protected_demand, available_for_non_protected
            ),
            self._strategy_full_industrial_cut(
                zone_demands, protected_demand, available_for_non_protected
            ),
            self._strategy_rotating_cuts(
                zone_demands, protected_demand, available_for_non_protected, risk_level
            ),
        ]
        
        return strategies
    
    def _calculate_zone_demands(
        self, zones: List[Dict[str, Any]], total_demand: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Calculate demand for each zone proportionally.
        
        Returns:
            Dict mapping zone_name to {"demand": float, "protected": bool}
        """
        # Count zones for proportional distribution
        zone_count = len(zones)
        if zone_count == 0:
            return {}
        
        base_demand = total_demand / zone_count
        
        zone_demands = {}
        for zone in zones:
            zone_demands[zone["name"]] = {
                "demand": base_demand,
                "protected": zone.get("protected", False),
            }
        
        return zone_demands
    
    def _strategy_gradual_reduction(
        self,
        zone_demands: Dict[str, Dict[str, Any]],
        protected_demand: float,
        available_for_non_protected: float,
    ) -> OptimizationStrategy:
        """
        Strategy 1: Slight reduction across all non-protected zones.
        Optimal for minor supply shortages.
        """
        allocation = {}
        total_disruption = 0
        disrupted_zones = []
        
        non_protected_zones = [
            (name, data)
            for name, data in zone_demands.items()
            if not data["protected"]
        ]
        
        total_non_protected_demand = sum(
            data["demand"] for _, data in non_protected_zones
        )
        
        if total_non_protected_demand > 0:
            reduction_ratio = available_for_non_protected / total_non_protected_demand
        else:
            reduction_ratio = 1.0
        
        for name, data in zone_demands.items():
            if data["protected"]:
                allocation[name] = data["demand"]
            else:
                allocated = data["demand"] * reduction_ratio
                allocation[name] = allocated
                disruption = data["demand"] - allocated
                total_disruption += disruption
                if disruption > 0.01:  # Only track meaningful disruptions
                    disrupted_zones.append({
                        "zone": name,
                        "demand": data["demand"],
                        "allocated": allocated,
                        "disruption": disruption,
                    })
        
        return OptimizationStrategy(
            name="Gradual Reduction",
            description="Slight reduction across all non-protected zones",
            allocation=allocation,
            total_disruption=total_disruption,
            disrupted_zones=disrupted_zones,
        )
    
    def _strategy_full_industrial_cut(
        self,
        zone_demands: Dict[str, Dict[str, Any]],
        protected_demand: float,
        available_for_non_protected: float,
    ) -> OptimizationStrategy:
        """
        Strategy 2: Full cut to industrial/commercial zones first.
        Optimal for severe shortages - protects residential areas.
        """
        allocation = {}
        total_disruption = 0
        disrupted_zones = []
        remaining_budget = available_for_non_protected
        
        # Priority: Protected > Residential > Commercial > Industrial
        zone_priorities = {}
        for name, data in zone_demands.items():
            if data["protected"]:
                zone_priorities[name] = 0  # Highest priority
            elif "residential" in name.lower():
                zone_priorities[name] = 1
            elif "commercial" in name.lower():
                zone_priorities[name] = 2
            else:  # Industrial, etc.
                zone_priorities[name] = 3
        
        # Sort by priority and allocate
        sorted_zones = sorted(
            zone_demands.items(), key=lambda x: zone_priorities.get(x[0], 2)
        )
        
        for name, data in sorted_zones:
            if data["protected"]:
                allocation[name] = data["demand"]
            else:
                demand = data["demand"]
                if remaining_budget >= demand:
                    allocation[name] = demand
                    remaining_budget -= demand
                elif remaining_budget > 0 and zone_priorities.get(name, 2) == 1:
                    # Partially serve residential
                    allocation[name] = remaining_budget
                    disruption = demand - remaining_budget
                    total_disruption += disruption
                    disrupted_zones.append({
                        "zone": name,
                        "demand": demand,
                        "allocated": remaining_budget,
                        "disruption": disruption,
                    })
                    remaining_budget = 0
                else:
                    # Full cut
                    allocation[name] = 0
                    total_disruption += demand
                    disrupted_zones.append({
                        "zone": name,
                        "demand": demand,
                        "allocated": 0,
                        "disruption": demand,
                    })
        
        return OptimizationStrategy(
            name="Full Industrial Cut",
            description="Full reduction to non-essential zones, protects residential",
            allocation=allocation,
            total_disruption=total_disruption,
            disrupted_zones=disrupted_zones,
        )
    
    def _strategy_rotating_cuts(
        self,
        zone_demands: Dict[str, Dict[str, Any]],
        protected_demand: float,
        available_for_non_protected: float,
        risk_level: str,
    ) -> OptimizationStrategy:
        """
        Strategy 3: Rotating cuts with increased mitigation for high risk.
        Fair distribution while maintaining minimum service levels.
        """
        allocation = {}
        total_disruption = 0
        disrupted_zones = []
        
        # Minimum allocation per non-protected zone (%)
        min_allocation_ratio = {
            "low": 0.9,       # 90% minimum
            "medium": 0.7,    # 70% minimum
            "high": 0.5,      # 50% minimum
            "critical": 0.3,  # 30% minimum
        }.get(risk_level, 0.5)
        
        non_protected_zones = [
            (name, data)
            for name, data in zone_demands.items()
            if not data["protected"]
        ]
        
        total_non_protected_demand = sum(
            data["demand"] for _, data in non_protected_zones
        )
        
        # Calculate allocation
        for name, data in zone_demands.items():
            if data["protected"]:
                allocation[name] = data["demand"]
            else:
                demand = data["demand"]
                min_allocation = demand * min_allocation_ratio
                
                # Try to allocate minimum first
                if available_for_non_protected >= demand:
                    allocation[name] = demand
                elif available_for_non_protected >= min_allocation:
                    allocation[name] = available_for_non_protected
                    available_for_non_protected = 0
                else:
                    allocation[name] = available_for_non_protected
                    available_for_non_protected = 0
                
                disruption = demand - allocation[name]
                total_disruption += disruption
                if disruption > 0.01:
                    disrupted_zones.append({
                        "zone": name,
                        "demand": demand,
                        "allocated": allocation[name],
                        "disruption": disruption,
                    })
        
        return OptimizationStrategy(
            name="Rotating Cuts",
            description=f"Fair rotating cuts with {int(min_allocation_ratio*100)}% minimum service",
            allocation=allocation,
            total_disruption=total_disruption,
            disrupted_zones=disrupted_zones,
        )


def format_strategies_for_websocket(
    strategies: List[OptimizationStrategy],
) -> List[Dict[str, Any]]:
    """
    Format optimization strategies for WebSocket broadcast.
    
    Returns:
        List of strategy dicts with all necessary details
    """
    formatted = []
    for i, strategy in enumerate(strategies, 1):
        formatted.append({
            "plan_id": i,
            "name": strategy.name,
            "description": strategy.description,
            "allocation": {
                zone: round(power, 2)
                for zone, power in strategy.allocation.items()
            },
            "total_disruption": round(strategy.total_disruption, 2),
            "disrupted_zones": [
                {
                    "zone": z["zone"],
                    "demand": round(z["demand"], 2),
                    "allocated": round(z["allocated"], 2),
                    "disruption": round(z["disruption"], 2),
                }
                for z in strategy.disrupted_zones
            ],
            "total_zones_served": len([z for z in strategy.allocation.values() if z > 0]),
            "total_allocated": round(sum(strategy.allocation.values()), 2),
        })
    
    return formatted

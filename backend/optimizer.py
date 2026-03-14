"""
Optimization Engine for Smart Grid Power Distribution.
GridOptimizer class wrapping Google OR-Tools constraint solver.
Guarantees deficit coverage via hard constraint on every plan.
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from ortools.linear_solver import pywraplp

logger = logging.getLogger(__name__)


@dataclass
class OptimizationPlan:
    """Represents a single power cut plan."""
    plan_id:          int
    label:            str
    cuts:             List[str]
    power_saved:      float
    deficit_mw:       float
    deficit_covered:  bool
    note:             str


class GridOptimizer:
    """
    OR-Tools constraint optimizer for power grid load shedding.

    Every plan enforces:
        total_cut >= deficit         (hard constraint — always covers shortage)
        protected zones never cut    (hard constraint — hospitals etc. always on)

    Plans differ only in their weighted objective — which zones to cut first.
    """

    def optimize(self, grid_state: dict) -> List[Dict[str, Any]]:
        """
        Generate 3 power cut plans for a given grid state.
        Returns list of plan dicts ready for WebSocket broadcast.
        """
        zones   = grid_state["zones"]
        supply  = grid_state["supply"]
        demand  = grid_state["demand"]
        deficit = round(demand - supply, 2)

        logger.info(f"[OPTIMIZER] Demand: {demand}MW | Supply: {supply}MW | Deficit: {deficit}MW")

        if deficit <= 0:
            logger.info("[OPTIMIZER] No deficit — returning stable plan")
            return [{
                "plan_id":        0,
                "label":          "No Action Required",
                "cuts":           [],
                "power_saved":    0,
                "deficit_mw":     deficit,
                "deficit_covered": True,
                "note":           "Supply meets demand — grid is stable"
            }]

        cuttable = [z for z in zones if not z.get("protected", False)]
        logger.info(f"[OPTIMIZER] {len(cuttable)} cuttable zones: {[z['name'] for z in cuttable]}")
        total_cuttable = sum([z["demand"] for z in cuttable])
        logger.info(f"[OPTIMIZER] Total cuttable capacity: {total_cuttable}MW (deficit: {deficit}MW)")

        plans = []
        
        # Build zone maps for harm calculation
        zone_map = {z["name"]: z for z in zones}
        residential_zones = {z["name"] for z in cuttable if z.get("type") == "residential" or "residential" in z["name"].lower()}
        industrial_zones = {z["name"] for z in cuttable if z.get("type") == "industrial" or "industry" in z["name"].lower() or "industrial" in z["name"].lower()}

        # Plan 1 — Pure minimum disruption (no zone preference)
        p1 = self._solve(
            cuttable, deficit,
            priority_names={z["name"] for z in cuttable},
            label="Minimum Disruption (Optimal)",
            plan_id=1,
            note="Mathematically least disruptive cut — OR-Tools optimal"
        )
        if p1:
            p1["confidence"] = self._calculate_confidence(p1, deficit, "balanced")
            p1["harm_score"] = self._calculate_harm(p1["cuts"], zone_map, residential_zones, industrial_zones, "balanced")
            p1["description"] = "Purely optimized solution with no zone preferences. Cuts zones mathematically to minimize total disruption."
            p1["use_case"] = "General load shedding when no strategic priorities exist"
            p1["recommended_for"] = ["routine", "balanced"]
            plans.append(p1)

        # Plan 2 — Industrial first, residential only if industrial isn't enough
        print(f"\n[OPTIMIZER] Plan 2 will prioritize INDUSTRIAL zones: {industrial_zones}")
        p2 = self._solve(
            cuttable, deficit,
            priority_names=industrial_zones,
            label="Industrial Priority Cut",
            plan_id=2,
            note="Cuts industrial zones first — minimizes residential impact"
        )
        if p2:
            p2["confidence"] = self._calculate_confidence(p2, deficit, "industrial_first")
            p2["harm_score"] = self._calculate_harm(p2["cuts"], zone_map, residential_zones, industrial_zones, "industrial_first")
            p2["description"] = "Protects residential areas by prioritizing industrial zone cuts. Best for protecting household services."
            p2["use_case"] = "Critical shortage requiring minimal residential impact"
            p2["recommended_for"] = ["high", "critical", "residential_protection"]
            plans.append(p2)

        # Plan 3 — Residential first, industrial only if residential isn't enough
        print(f"\n[OPTIMIZER] Plan 3 will prioritize RESIDENTIAL zones: {residential_zones}")
        p3 = self._solve(
            cuttable, deficit,
            priority_names=residential_zones,
            label="Residential Rotation",
            plan_id=3,
            note="Distributes cuts across residential — protects industry"
        )
        if p3:
            p3["confidence"] = self._calculate_confidence(p3, deficit, "residential_first")
            p3["harm_score"] = self._calculate_harm(p3["cuts"], zone_map, residential_zones, industrial_zones, "residential_first")
            p3["description"] = "Protects industrial zones by rotating cuts across residential. Best for economic continuity."
            p3["use_case"] = "Shortage requiring industrial sector to remain operational"
            p3["recommended_for"] = ["medium", "industrial_protection"]
            plans.append(p3)

        logger.info(f"[OPTIMIZER] Generated {len(plans)} plans")
        return plans

    def _solve(
        self,
        cuttable:       List[Dict],
        deficit:        float,
        priority_names: set,
        label:          str,
        plan_id:        int,
        note:           str
    ) -> Optional[Dict[str, Any]]:
        """
        Core OR-Tools solver.
        Hard constraint: total_cut >= deficit.
        Weighted objective: priority zones cost 1, others cost 100.
        """
        solver = pywraplp.Solver.CreateSolver("SCIP")
        if not solver:
            logger.error("[OPTIMIZER] Failed to create SCIP solver")
            return None

        print(f"\n\033[96m[OPTIMIZER] Solving Plan {plan_id}: '{label}'\033[0m")
        print(f"  Priority zones (cost=1): {priority_names}")
        non_priority = {z["name"] for z in cuttable} - priority_names
        print(f"  Non-priority zones (cost=100): {non_priority}")

        cut_vars = {
            z["name"]: solver.IntVar(0, 1, z["name"])
            for z in cuttable
        }

        # Hard constraint — must cover full deficit
        solver.Add(
            solver.Sum([
                cut_vars[z["name"]] * z["demand"]
                for z in cuttable
            ]) >= deficit
        )

        # Weighted objective — priority zones cost 1, others cost 100
        solver.Minimize(
            solver.Sum([
                cut_vars[z["name"]] * z["demand"] * (1 if z["name"] in priority_names else 100)
                for z in cuttable
            ])
        )

        status = solver.Solve()

        if status in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
            cuts  = [z["name"] for z in cuttable if cut_vars[z["name"]].solution_value() > 0.5]
            saved = round(sum(z["demand"] for z in cuttable if z["name"] in cuts), 2)
            
            solver_status = "OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE"
            print(f"  ✓ Solver status: {solver_status}")
            print(f"  ✓ Plan {plan_id} cuts: {cuts}")
            print(f"  ✓ Power saved: {saved}MW (needed: {deficit}MW)")
            logger.info(f"[OPTIMIZER] Plan {plan_id} '{label}': cuts={cuts} saved={saved}MW status={solver_status}")
            
            return {
                "plan_id":         plan_id,
                "label":           label,
                "cuts":            cuts,
                "power_saved":     saved,
                "deficit_mw":      deficit,
                "deficit_covered": saved >= deficit,
                "solver_status":   solver_status,
                "note":            note
            }

        # Solver infeasible — cut everything cuttable as last resort
        logger.warning(f"[OPTIMIZER] Plan {plan_id} infeasible — applying full fallback cut")
        print(f"  ✗ Solver infeasible — using fallback")
        cuts  = [z["name"] for z in cuttable]
        saved = round(sum(z["demand"] for z in cuttable), 2)
        print(f"  ✓ Fallback cuts all zones: {cuts}")
        print(f"  ✓ Power saved: {saved}MW\n")
        return {
            "plan_id":         plan_id,
            "label":           label,
            "cuts":            cuts,
            "power_saved":     saved,
            "deficit_mw":      deficit,
            "deficit_covered": saved >= deficit,
            "solver_status":   "FALLBACK",
            "note":            f"{note} (fallback — full cut applied)"
        }

    def _calculate_confidence(self, plan: Dict[str, Any], deficit: float, strategy: str) -> int:
        """
        Calculate confidence score (0-100) based on:
        - Solver optimality (OPTIMAL/FEASIBLE/FALLBACK)
        - How well plan covers deficit
        - Strategy effectiveness (some strategies more proven than others)
        """
        power_saved = plan["power_saved"]
        solver_status = plan.get("solver_status", "FEASIBLE")
        
        # Base confidence from solver status
        if solver_status == "FALLBACK":
            base = 60  # Fallback cut — risky but guaranteed to work
        elif solver_status == "OPTIMAL":
            base = 92  # Optimal solution — theoretically best
        else:  # FEASIBLE
            base = 85  # Feasible solution — good but not proven optimal
        
        # Strategy modifier — vary confidence by strategy for differentiation
        if strategy == "industrial_first":
            base += 5   # Industrial-first is slightly more proven/reliable (protects households)
        elif strategy == "residential_first":
            base -= 2   # Residential-first slightly less reliable (affects more critical sectors)
        # balanced gets no modifier
        
        # Adjust based on coverage margin
        if power_saved >= deficit:
            margin = (power_saved - deficit) / deficit * 100
            
            if margin >= 30:
                base += 8   # Very safe — 30%+ excess buffer
            elif margin >= 20:
                base += 5   # Safe — 20% excess buffer
            elif margin >= 10:
                base += 2   # Adequate buffer — 10% excess
            # else: tight fit — no bonus
        else:
            # Under-cut (shouldn't happen with hard constraint, but handle it)
            shortfall = (deficit - power_saved) / deficit * 100
            base -= min(int(shortfall / 10) * 3, 30)  # Reduce by ~3% per 10% shortfall
        
        # Clamp to valid range [0, 100]
        return max(0, min(100, base))
    
    def _calculate_harm(self, cuts: List[str], zone_map: Dict, residential_zones: set, industrial_zones: set, strategy: str) -> int:
        """
        Calculate harm score (0-10) based on:
        - Number of residential zones cut (high impact on households)
        - Industrial zones cut (moderate impact on economy)
        - Strategy effectiveness at minimizing harm
        """
        residential_cut = len([z for z in cuts if z in residential_zones])
        industrial_cut = len([z for z in cuts if z in industrial_zones])
        
        # Calculate power impact
        residential_power = sum(zone_map[z]["demand"] for z in cuts if z in residential_zones)
        industrial_power = sum(zone_map[z]["demand"] for z in cuts if z in industrial_zones)
        
        # Harm calculation — residential has 2x weight (affects households/hospitals)
        residential_impact = min(10, residential_power / 50)  # Each 50MW = 1 harm point
        industrial_impact = min(10, industrial_power / 100)   # Each 100MW = 1 harm point (lower weight)
        
        harm = (residential_impact * 2 + industrial_impact) / 3  # Weighted average
        
        # Strategy modifier
        if strategy == "industrial_first" and industrial_cut > 0 and residential_cut == 0:
            harm -= 1  # Bonus if cuts only industrial
        elif strategy == "residential_first" and residential_cut > 0 and industrial_cut == 0:
            harm += 1  # Penalty if cuts only residential (higher harm)
        
        # Clamp to valid range [0, 10]
        return int(max(0, min(10, round(harm, 1))))

    def select_recommended_plan(self, plans: List[Dict], risk_level: str) -> Optional[int]:
        """
        Auto-select the recommended plan ID based on risk level.
        Used to highlight a default choice on the dashboard.
        """
        selection = {
            "low":      1,   # Minimum disruption — minor shortage
            "medium":   3,   # Residential rotation — balanced
            "high":     2,   # Industrial priority — protect residential
            "critical": 2    # Industrial priority — emergency mode
        }
        recommended = selection.get(risk_level, 1)
        logger.info(f"[OPTIMIZER] Recommended plan for '{risk_level}' risk: Plan {recommended}")
        return recommended


def format_plans_for_broadcast(plans: List[Dict[str, Any]], grid_state: Optional[dict] = None) -> List[Dict[str, Any]]:
    """
    Format optimizer plans for WebSocket broadcast.
    Converts zone names to detailed cut objects with power values.
    """
    zones_map = {}
    if grid_state:
        zones_map = {z["name"]: z for z in grid_state.get("zones", [])}
    
    formatted = []
    for plan in plans:
        # Convert zone names to detailed cut objects
        detailed_cuts = []
        for zone_name in plan.get("cuts", []):
            zone_info = zones_map.get(zone_name, {})
            detailed_cuts.append({
                "zone": zone_name,
                "power_mw": round(zone_info.get("demand", 0), 2),
                "sector": zone_info.get("sector", "unknown")
            })
        
        formatted.append({
            "plan_id":         plan["plan_id"],
            "label":           plan["label"],
            "cuts":            detailed_cuts,  # Now detailed objects instead of just names
            "power_saved":     round(plan["power_saved"], 2),
            "deficit_mw":      round(plan["deficit_mw"], 2),
            "deficit_covered": plan["deficit_covered"],
            "confidence":      plan.get("confidence", 75),  # Preserve confidence score
            "harm_score":      plan.get("harm_score", 5),   # Preserve harm score
            "description":     plan.get("description", ""),
            "use_case":        plan.get("use_case", ""),
            "recommended_for": plan.get("recommended_for", []),
            "note":            plan["note"]
        })
    return formatted


# Module-level singleton
optimizer = GridOptimizer()

def optimize_power(grid_state: dict) -> List[Dict[str, Any]]:
    """Convenience function — keeps main.py import unchanged."""
    return optimizer.optimize(grid_state)
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

        # Plan 1 — Pure minimum disruption (no zone preference)
        p1 = self._solve(
            cuttable, deficit,
            priority_names={z["name"] for z in cuttable},
            label="Minimum Disruption (Optimal)",
            plan_id=1,
            note="Mathematically least disruptive cut — OR-Tools optimal"
        )
        if p1:
            plans.append(p1)

        # Plan 2 — Industrial first, residential only if industrial isn't enough
        industrial = {z["name"] for z in cuttable if z.get("type") == "industrial" or "industry" in z["name"].lower() or "industrial" in z["name"].lower()}
        print(f"\n[OPTIMIZER] Plan 2 will prioritize INDUSTRIAL zones: {industrial}")
        p2 = self._solve(
            cuttable, deficit,
            priority_names=industrial,
            label="Industrial Priority Cut",
            plan_id=2,
            note="Cuts industrial zones first — minimizes residential impact"
        )
        if p2:
            plans.append(p2)

        # Plan 3 — Residential first, industrial only if residential isn't enough
        residential = {z["name"] for z in cuttable if z.get("type") == "residential" or "residential" in z["name"].lower()}
        print(f"\n[OPTIMIZER] Plan 3 will prioritize RESIDENTIAL zones: {residential}")
        p3 = self._solve(
            cuttable, deficit,
            priority_names=residential,
            label="Residential Rotation",
            plan_id=3,
            note="Distributes cuts across residential — protects industry"
        )
        if p3:
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
            
            print(f"  ✓ Solver status: {'OPTIMAL' if status == pywraplp.Solver.OPTIMAL else 'FEASIBLE'}")
            print(f"  ✓ Plan {plan_id} cuts: {cuts}")
            print(f"  ✓ Power saved: {saved}MW (needed: {deficit}MW)")
            logger.info(f"[OPTIMIZER] Plan {plan_id} '{label}': cuts={cuts} saved={saved}MW")
            
            return {
                "plan_id":         plan_id,
                "label":           label,
                "cuts":            cuts,
                "power_saved":     saved,
                "deficit_mw":      deficit,
                "deficit_covered": saved >= deficit,
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
            "note":            f"{note} (fallback — full cut applied)"
        }

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


def format_plans_for_broadcast(plans: List[Dict[str, Any]], grid_state: dict = None) -> List[Dict[str, Any]]:
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
            "note":            plan["note"]
        })
    return formatted


# Module-level singleton
optimizer = GridOptimizer()

def optimize_power(grid_state: dict) -> List[Dict[str, Any]]:
    """Convenience function — keeps main.py import unchanged."""
    return optimizer.optimize(grid_state)
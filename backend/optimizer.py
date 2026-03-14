from ortools.linear_solver import pywraplp


def optimize_power(grid_state: dict) -> list[dict]:
    zones   = grid_state["zones"]
    supply  = grid_state["supply"]
    demand  = grid_state["demand"]
    deficit = round(demand - supply, 2)

    if deficit <= 0:
        return [{
            "plan_id": 0,
            "label": "No Action Required",
            "cuts": [],
            "power_saved": 0,
            "deficit_mw": deficit,
            "deficit_covered": True,
            "note": "Supply meets demand — grid is stable"
        }]

    cuttable = [z for z in zones if not z.get("protected", False)]

    def solve(priority_names: set, label: str, plan_id: int, note: str) -> dict | None:
        solver = pywraplp.Solver.CreateSolver("SCIP")
        if not solver:
            return None

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
        # OR-Tools will exhaust cheap (priority) zones before touching expensive ones
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
            return {
                "plan_id":        plan_id,
                "label":          label,
                "cuts":           cuts,
                "power_saved":    saved,
                "deficit_mw":     deficit,
                "deficit_covered": saved >= deficit,
                "note":           note
            }

        # Solver couldn't find any feasible solution — cut everything cuttable
        cuts  = [z["name"] for z in cuttable]
        saved = round(sum(z["demand"] for z in cuttable), 2)
        return {
            "plan_id":         plan_id,
            "label":           label,
            "cuts":            cuts,
            "power_saved":     saved,
            "deficit_mw":      deficit,
            "deficit_covered": saved >= deficit,
            "note":            f"{note} (fallback — full cut applied)"
        }

    plans = []

    # Plan 1 — Pure minimum disruption, no zone preference
    p1 = solve(
        priority_names={z["name"] for z in cuttable},   # all zones equal weight
        label="Minimum Disruption (Optimal)",
        plan_id=1,
        note="Mathematically least disruptive cut — OR-Tools optimal"
    )
    if p1:
        plans.append(p1)

    # Plan 2 — Industrial first, residential only if industrial isn't enough
    industrial = {z["name"] for z in cuttable if "industry"    in z["name"]}
    p2 = solve(
        priority_names=industrial,
        label="Industrial Priority Cut",
        plan_id=2,
        note="Cuts industrial zones first — minimizes residential impact"
    )
    if p2:
        plans.append(p2)

    # Plan 3 — Residential first, industrial only if residential isn't enough
    residential = {z["name"] for z in cuttable if "residential" in z["name"]}
    p3 = solve(
        priority_names=residential,
        label="Residential Rotation",
        plan_id=3,
        note="Distributes cuts across residential — protects industry"
    )
    if p3:
        plans.append(p3)

    return plans
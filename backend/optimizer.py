from ortools.linear_solver import pywraplp

def optimize_power(grid_state: dict) -> list[dict]:
    zones = grid_state["zones"]
    supply = grid_state["supply"]
    demand = grid_state["demand"]

    deficit = demand - supply
    if deficit <= 0:
        return [{"plan": "No cuts needed", "cuts": [], "saved": 0}]

    solver = pywraplp.Solver.CreateSolver("SCIP")

    # Binary variable: 1 = cut this zone, 0 = keep it
    cut_vars = {}
    for z in zones:
        if not z.get("protected", False):
            cut_vars[z["name"]] = solver.IntVar(0, 1, z["name"])

    # Constraint: total cut >= deficit (must cover the shortfall)
    solver.Add(
        solver.Sum([
            cut_vars[z["name"]] * z["demand"]
            for z in zones if z["name"] in cut_vars
        ]) >= deficit
    )

    # Objective: minimize total load cut (minimize disruption)
    solver.Minimize(
        solver.Sum([
            cut_vars[z["name"]] * z["demand"]
            for z in zones if z["name"] in cut_vars
        ])
    )

    plans = []

    # Generate Plan 1: Optimal minimum cut
    status = solver.Solve()
    if status == pywraplp.Solver.OPTIMAL:
        cuts = [z["name"] for z in zones if z["name"] in cut_vars and cut_vars[z["name"]].solution_value() > 0.5]
        saved = sum(z["demand"] for z in zones if z["name"] in cuts)
        plans.append({
            "plan_id": 1,
            "label": "Minimum Cut (Optimal)",
            "cuts": cuts,
            "power_saved": saved,
            "deficit_covered": saved >= deficit
        })

    # Plan 2: Cut all industrial zones first
    industrial_cuts = [z["name"] for z in zones if "industry" in z["name"] and not z.get("protected")]
    industrial_saved = sum(z["demand"] for z in zones if z["name"] in industrial_cuts)
    plans.append({
        "plan_id": 2,
        "label": "Industrial Priority Cut",
        "cuts": industrial_cuts,
        "power_saved": industrial_saved,
        "deficit_covered": industrial_saved >= deficit
    })

    # Plan 3: Rotate residential zones
    residential_cuts = [z["name"] for z in zones if "residential" in z["name"] and not z.get("protected")]
    residential_saved = sum(z["demand"] for z in zones if z["name"] in residential_cuts)
    plans.append({
        "plan_id": 3,
        "label": "Residential Rotation",
        "cuts": residential_cuts,
        "power_saved": residential_saved,
        "deficit_covered": residential_saved >= deficit
    })

    return plans
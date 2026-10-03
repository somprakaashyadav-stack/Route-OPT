"""
core/emissions/calculator.py
=============================
CO₂ and fuel consumption calculator for vehicle routes.

Emission factors source: DEFRA (UK) Greenhouse Gas Conversion Factors 2023.
"""

from __future__ import annotations

from typing import Dict, List, Optional

import networkx as nx


# ---------------------------------------------------------------------------
# DEFRA 2023 emission factors (kg CO₂ per km)
# ---------------------------------------------------------------------------
EMISSION_FACTORS: Dict[str, float] = {
    "petrol_car":  0.170,
    "diesel_van":  0.210,
    "electric":    0.053,
    "truck":       0.330,
    "motorcycle":  0.114,
    "hybrid":      0.105,
    "default":     0.210,
}

# Average fuel efficiency (km per litre)
FUEL_EFFICIENCY: Dict[str, float] = {
    "petrol_car":  14.0,
    "diesel_van":  12.0,
    "electric":    0.0,   # electric — no fuel, handled separately
    "truck":       5.0,
    "motorcycle":  20.0,
    "hybrid":      18.0,
    "default":     12.0,
}


class EmissionsCalculator:
    """
    Calculates CO₂ emissions and fuel consumption for route solutions.

    Parameters
    ----------
    vehicle_type : key into EMISSION_FACTORS / FUEL_EFFICIENCY
    """

    def __init__(self, vehicle_type: str = "diesel_van") -> None:
        self.vehicle_type = vehicle_type
        self.factor       = EMISSION_FACTORS.get(vehicle_type,
                              EMISSION_FACTORS["default"])
        self.efficiency   = FUEL_EFFICIENCY.get(vehicle_type,
                              FUEL_EFFICIENCY["default"])

    # ------------------------------------------------------------------

    def co2_kg(self, distance_km: float) -> float:
        """Return kg CO₂ for a given distance."""
        return distance_km * self.factor

    def fuel_litres(self, distance_km: float) -> float:
        """Return fuel consumption in litres (0 for electric)."""
        if self.efficiency == 0:
            return 0.0
        return distance_km / self.efficiency

    def fuel_cost(self, distance_km: float, price_per_litre: float = 1.60) -> float:
        """Return fuel cost in GBP (default UK diesel price)."""
        return self.fuel_litres(distance_km) * price_per_litre

    # ------------------------------------------------------------------

    def route_distance(
        self,
        route: List[int],
        graph: nx.DiGraph,
        depot: int = 0,
    ) -> float:
        """Total distance (km) for a single route including depot return."""
        seq   = [depot] + route + [depot]
        total = 0.0
        for i in range(len(seq) - 1):
            u, v = seq[i], seq[i + 1]
            try:
                import networkx as _nx
                path = _nx.shortest_path(graph, u, v, weight="weight")
                for a, b in zip(path, path[1:]):
                    total += graph[a][b].get("distance", 0)
            except Exception:
                total += 1e6
        return total

    def route_summary(
        self,
        routes: List[List[int]],
        graph:  nx.DiGraph,
        depot:  int = 0,
    ) -> Dict:
        """
        Compute emissions & fuel summary for all routes.

        Returns
        -------
        dict with keys: total_distance_km, total_co2_kg,
                        total_fuel_litres, total_fuel_cost_gbp
        """
        total_dist = sum(self.route_distance(r, graph, depot) for r in routes)
        return {
            "vehicle_type":       self.vehicle_type,
            "total_distance_km":  round(total_dist, 3),
            "total_co2_kg":       round(self.co2_kg(total_dist), 3),
            "total_fuel_litres":  round(self.fuel_litres(total_dist), 3),
            "total_fuel_cost_gbp": round(self.fuel_cost(total_dist), 2),
        }

    def savings_vs_baseline(
        self,
        baseline_routes: List[List[int]],
        optimized_routes: List[List[int]],
        graph:  nx.DiGraph,
        depot:  int = 0,
    ) -> Dict:
        """Compare optimised vs. baseline solution emissions."""
        base = self.route_summary(baseline_routes, graph, depot)
        opt  = self.route_summary(optimized_routes, graph, depot)

        saved_dist = base["total_distance_km"] - opt["total_distance_km"]
        saved_co2  = base["total_co2_kg"]      - opt["total_co2_kg"]
        pct_co2    = (saved_co2 / max(base["total_co2_kg"], 1e-9)) * 100

        return {
            "baseline":          base,
            "optimized":         opt,
            "saved_distance_km": round(saved_dist, 3),
            "saved_co2_kg":      round(saved_co2,  3),
            "co2_reduction_pct": round(pct_co2,    2),
        }

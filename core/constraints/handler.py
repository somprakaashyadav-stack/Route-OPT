"""
core/constraints/handler.py
============================
Constraint checking and enforcement for VRP solutions.

  - Capacity constraints
  - Time-window constraints
  - Emergency priority (weight reduction on approach edges)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import networkx as nx


class ConstraintHandler:
    """
    Validates and enforces VRP constraints.

    Parameters
    ----------
    capacity : default vehicle capacity (can be overridden per call)
    """

    def __init__(self, capacity: float = 100.0) -> None:
        self.capacity = capacity

    # ------------------------------------------------------------------
    # Capacity
    # ------------------------------------------------------------------

    def check_capacity(
        self,
        route:    List[int],
        demands:  Dict[int, float],
        capacity: Optional[float] = None,
    ) -> bool:
        """Return True if total demand on route ≤ capacity."""
        cap = capacity if capacity is not None else self.capacity
        return sum(demands.get(c, 0) for c in route) <= cap

    def capacity_violation(
        self,
        route:    List[int],
        demands:  Dict[int, float],
        capacity: Optional[float] = None,
    ) -> float:
        """Return amount by which capacity is exceeded (0 if feasible)."""
        cap   = capacity if capacity is not None else self.capacity
        total = sum(demands.get(c, 0) for c in route)
        return max(0.0, total - cap)

    # ------------------------------------------------------------------
    # Time windows
    # ------------------------------------------------------------------

    def check_time_window(
        self,
        route:         List[int],
        graph:         nx.DiGraph,
        time_windows:  Dict[int, Tuple[float, float]],
        service_times: Dict[int, float],
        depot_open:    float = 0.0,
        depot:         int   = 0,
    ) -> bool:
        """
        Return True if the route respects all time windows.

        Parameters
        ----------
        time_windows  : {node: (earliest, latest)} in minutes
        service_times : {node: service duration} in minutes
        depot_open    : time depot becomes available (minutes)
        """
        current_time = depot_open
        seq = [depot] + route + [depot]

        for i in range(len(seq) - 1):
            u, v = seq[i], seq[i + 1]
            travel_time = graph[u][v].get("travel_time", 0) if graph.has_edge(u, v) else 1e6
            arrival     = current_time + travel_time

            if v in time_windows:
                early, late = time_windows[v]
                if arrival > late:
                    return False          # arrived too late
                current_time = max(arrival, early) + service_times.get(v, 0)
            else:
                current_time = arrival

        return True

    def time_window_violations(
        self,
        route:         List[int],
        graph:         nx.DiGraph,
        time_windows:  Dict[int, Tuple[float, float]],
        service_times: Dict[int, float],
        depot_open:    float = 0.0,
        depot:         int   = 0,
    ) -> int:
        """Return count of time-window violations on the route."""
        violations    = 0
        current_time  = depot_open
        seq           = [depot] + route + [depot]

        for i in range(len(seq) - 1):
            u, v = seq[i], seq[i + 1]
            travel_time = graph[u][v].get("travel_time", 0) if graph.has_edge(u, v) else 1e6
            arrival     = current_time + travel_time

            if v in time_windows:
                early, late = time_windows[v]
                if arrival > late:
                    violations += 1
                current_time = max(arrival, early) + service_times.get(v, 0)
            else:
                current_time = arrival

        return violations

    # ------------------------------------------------------------------
    # Emergency priority
    # ------------------------------------------------------------------

    def apply_emergency_priority(
        self,
        graph:            nx.DiGraph,
        emergency_nodes:  List[int],
        priority_boost:   float = 0.1,
    ) -> None:
        """
        Reduce edge weights on all edges leading toward emergency nodes.
        Lower weight → algorithm prefers these paths.

        Parameters
        ----------
        priority_boost : multiplier applied to approach-edge weights (< 1 speeds up)
        """
        for node in emergency_nodes:
            if node not in graph.nodes:
                continue
            for pred in graph.predecessors(node):
                if graph.has_edge(pred, node):
                    graph[pred][node]["weight"] *= priority_boost

    def reset_emergency_priority(
        self,
        graph:           nx.DiGraph,
        emergency_nodes: List[int],
        priority_boost:  float = 0.1,
    ) -> None:
        """Undo emergency weight reduction (restore original weights)."""
        for node in emergency_nodes:
            if node not in graph.nodes:
                continue
            for pred in graph.predecessors(node):
                if graph.has_edge(pred, node):
                    graph[pred][node]["weight"] /= priority_boost

    # ------------------------------------------------------------------
    # Full solution validator
    # ------------------------------------------------------------------

    def validate_solution(
        self,
        routes:        List[List[int]],
        demands:       Dict[int, float],
        capacity:      Optional[float] = None,
        time_windows:  Optional[Dict[int, Tuple[float, float]]] = None,
        service_times: Optional[Dict[int, float]] = None,
        graph:         Optional[nx.DiGraph] = None,
        depot:         int = 0,
    ) -> Dict:
        """
        Run all constraint checks on a complete solution.
        Returns a report dict with feasibility flags and violation counts.
        """
        cap       = capacity if capacity is not None else self.capacity
        all_custs = [c for r in routes for c in r]
        report    = {
            "n_routes":              len(routes),
            "all_customers_served":  len(set(all_custs)) == len(all_custs),
            "capacity_feasible":     all(self.check_capacity(r, demands, cap) for r in routes),
            "capacity_violations":   [self.capacity_violation(r, demands, cap) for r in routes],
            "tw_feasible":           True,
            "tw_violations":         0,
        }

        if time_windows and graph is not None:
            st = service_times or {}
            tw_viols = sum(
                self.time_window_violations(r, graph, time_windows, st, depot=depot)
                for r in routes
            )
            report["tw_feasible"]   = tw_viols == 0
            report["tw_violations"] = tw_viols

        return report

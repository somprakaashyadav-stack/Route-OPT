"""
core/algorithms/exact.py
========================
Exact / greedy baseline algorithms for VRP benchmarking.

  - Dijkstra  : single-source shortest path (networkx wrapper)
  - AStar     : heuristic shortest path
  - Savings   : Clarke-Wright savings heuristic for VRP
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np


# ---------------------------------------------------------------------------
# Shortest-path wrappers
# ---------------------------------------------------------------------------

def dijkstra(graph: nx.DiGraph, source: int, target: int) -> Tuple[List[int], float]:
    """Return (path, cost) using Dijkstra's algorithm."""
    path = nx.shortest_path(graph, source, target, weight="weight")
    cost = nx.shortest_path_length(graph, source, target, weight="weight")
    return path, cost


def astar(
    graph:  nx.DiGraph,
    source: int,
    target: int,
    heuristic=None,
) -> Tuple[List[int], float]:
    """
    Return (path, cost) using A* algorithm.
    Default heuristic: Euclidean distance between node coordinates.
    """
    if heuristic is None:
        def heuristic(u, v):
            xu = graph.nodes[u].get("x", 0)
            yu = graph.nodes[u].get("y", 0)
            xv = graph.nodes[v].get("x", 0)
            yv = graph.nodes[v].get("y", 0)
            return ((xu - xv) ** 2 + (yu - yv) ** 2) ** 0.5 / 1000  # rough km

    path = nx.astar_path(graph, source, target,
                         heuristic=heuristic, weight="weight")
    cost = sum(graph[path[i]][path[i+1]]["weight"]
               for i in range(len(path) - 1))
    return path, cost


# ---------------------------------------------------------------------------
# Clarke-Wright Savings Algorithm for VRP
# ---------------------------------------------------------------------------

class SavingsSolver:
    """
    Clarke-Wright Savings heuristic for CVRP.

    Greedy baseline: merge routes that give the greatest saving.
    Saving s(i,j) = d(depot,i) + d(depot,j) − d(i,j)
    """

    def __init__(self, capacity: float = 100.0) -> None:
        self.capacity = capacity

    def optimize(
        self,
        graph:     nx.DiGraph,
        customers: List[int],
        demands:   Dict[int, float],
        depot:     int = 0,
        verbose:   bool = False,
    ) -> Tuple[List[List[int]], float, List[float]]:
        # ── Compute savings ─────────────────────────────────────
        savings = []
        dist = {}
        for c in [depot] + customers:
            for c2 in customers:
                try:
                    dist[(c, c2)] = nx.shortest_path_length(
                        graph, c, c2, weight="weight")
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    dist[(c, c2)] = 1e6

        for i in customers:
            for j in customers:
                if i != j:
                    s = (dist[(depot, i)]
                         + dist[(depot, j)]
                         - dist[(i, j)])
                    savings.append((s, i, j))
        savings.sort(key=lambda x: -x[0])

        # ── Initialise: one route per customer ──────────────────
        routes:     Dict[int, List[int]] = {c: [c] for c in customers}
        route_load: Dict[int, float]     = {c: demands.get(c, 0) for c in customers}
        cust_route: Dict[int, int]       = {c: c for c in customers}  # cust → route key

        # ── Merge routes greedily ────────────────────────────────
        for s, i, j in savings:
            ri = cust_route.get(i)
            rj = cust_route.get(j)
            if ri is None or rj is None or ri == rj:
                continue
            route_i = routes[ri]
            route_j = routes[rj]

            # i must be last in route_i, j must be first in route_j
            if route_i[-1] != i or route_j[0] != j:
                continue
            if route_load[ri] + route_load[rj] > self.capacity:
                continue

            # Merge
            new_route = route_i + route_j
            new_load  = route_load[ri] + route_load[rj]
            routes[ri] = new_route
            route_load[ri] = new_load
            del routes[rj]
            del route_load[rj]
            for c in route_j:
                cust_route[c] = ri

        final_routes = list(routes.values())

        # ── Compute total cost ───────────────────────────────────
        total_cost = 0.0
        for route in final_routes:
            seq = [depot] + route + [depot]
            for k in range(len(seq) - 1):
                total_cost += dist.get((seq[k], seq[k+1]), 1e6)

        if verbose:
            print(f"  Savings: {len(final_routes)} routes, cost={total_cost:.4f}")

        return final_routes, total_cost, [total_cost]

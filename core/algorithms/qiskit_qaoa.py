"""
core/algorithms/qiskit_qaoa.py
==============================
Optional Qiskit QAOA stub for small-scale VRP sub-problems.
Requires: pip install qiskit qiskit-optimization

Falls back gracefully if Qiskit is not installed.
Intended as a research/comparison module, not production.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np

try:
    from qiskit_optimization import QuadraticProgram
    from qiskit_optimization.algorithms import MinimumEigenOptimizer
    from qiskit.algorithms.minimum_eigensolvers import QAOA, SamplingVQE
    from qiskit.primitives import Sampler
    QISKIT_AVAILABLE = True
except ImportError:
    QISKIT_AVAILABLE = False


MAX_CUSTOMERS = 15   # QAOA practical limit on current simulators


class QiskitQAOASolver:
    """
    QAOA-based solver for very small VRP instances (≤ 15 customers).

    Encodes customer-vehicle assignments as binary variables in a
    Quadratic Program, then solves with Qiskit's QAOA.

    Parameters
    ----------
    reps         : QAOA circuit depth (p-layers)
    n_vehicles   : number of available vehicles
    capacity     : vehicle capacity
    max_customers: hard limit on problem size for QAOA
    """

    def __init__(
        self,
        reps:          int   = 2,
        n_vehicles:    int   = 3,
        capacity:      float = 100.0,
        max_customers: int   = MAX_CUSTOMERS,
    ) -> None:
        self.reps          = reps
        self.n_vehicles    = n_vehicles
        self.capacity      = capacity
        self.max_customers = max_customers

    def optimize(
        self,
        graph:     nx.DiGraph,
        customers: List[int],
        demands:   Dict[int, float],
        depot:     int = 0,
        verbose:   bool = False,
    ) -> Tuple[List[List[int]], float, List[float]]:
        if not QISKIT_AVAILABLE:
            raise ImportError(
                "Qiskit not found. Install with:\n"
                "  pip install qiskit qiskit-optimization"
            )
        if len(customers) > self.max_customers:
            raise ValueError(
                f"QAOA limited to ≤{self.max_customers} customers. "
                f"Got {len(customers)}. Use QPSO/QIEA for larger instances."
            )

        n = len(customers)
        k = self.n_vehicles
        qp = QuadraticProgram(name="VRP_QAOA")

        # ── Decision variables: x_{i,v} = 1 if customer i served by vehicle v ──
        for i in range(n):
            for v in range(k):
                qp.binary_var(f"x_{i}_{v}")

        # ── Objective: minimise total route cost ──────────────────────────────
        # Approximation: cost ≈ demand-weighted assignment
        linear: Dict[str, float] = {}
        for i, cust in enumerate(customers):
            for v in range(k):
                # Use graph distance from depot as proxy cost
                try:
                    cost_iv = nx.shortest_path_length(
                        graph, depot, cust, weight="weight")
                except (nx.NetworkXNoPath, nx.NodeNotFound):
                    cost_iv = 1e3
                linear[f"x_{i}_{v}"] = cost_iv
        qp.minimize(linear=linear)

        # ── Constraints ───────────────────────────────────────────────────────
        # 1. Each customer assigned to exactly one vehicle
        for i in range(n):
            qp.linear_constraint(
                linear={f"x_{i}_{v}": 1 for v in range(k)},
                sense="==",
                rhs=1,
                name=f"assign_{i}",
            )

        # 2. Capacity constraints (relaxed to linear penalty in QP)
        for v in range(k):
            cap_lin = {
                f"x_{i}_{v}": float(demands.get(customers[i], 0))
                for i in range(n)
            }
            qp.linear_constraint(
                linear=cap_lin,
                sense="<=",
                rhs=float(self.capacity),
                name=f"cap_{v}",
            )

        if verbose:
            print(f"  QAOA: {n*k} binary variables, {n+k} constraints")

        # ── Solve with QAOA ───────────────────────────────────────────────────
        sampler  = Sampler()
        qaoa     = QAOA(sampler=sampler, reps=self.reps)
        optimizer = MinimumEigenOptimizer(qaoa)
        result   = optimizer.solve(qp)

        if verbose:
            print(f"  QAOA fval = {result.fval:.4f}")

        # ── Decode result to routes ───────────────────────────────────────────
        x = result.x
        routes: List[List[int]] = [[] for _ in range(k)]
        for i, cust in enumerate(customers):
            for v in range(k):
                var_idx = i * k + v
                if x[var_idx] > 0.5:
                    routes[v].append(cust)
                    break   # assigned — move to next customer

        routes = [r for r in routes if r]
        return routes, float(result.fval), []

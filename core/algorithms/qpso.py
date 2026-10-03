"""
core/algorithms/qpso.py
=======================
Quantum Particle Swarm Optimization (QPSO) for Vehicle Routing.

Key idea:
  - Replaces PSO velocity with a quantum delta-potential well.
  - Position update sampled from a Laplace distribution centred on the
    local attractor: x = attractor ± β·|mbest−x|·ln(1/u), u~U(0,1)
  - Encoding: continuous vector in [0,1)^n decoded via Smallest Position
    Value (SPV) rule → vehicle route permutation.
  - Fitness: weighted sum of travel time + distance + congestion + CO₂.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np


class QPSOSolver:
    """
    Quantum Particle Swarm Optimization solver for VRP.

    Parameters
    ----------
    n_particles    : swarm size
    max_iter       : maximum iterations
    beta_start     : contraction-expansion coefficient (start)
    beta_end       : contraction-expansion coefficient (end, linear decay)
    capacity       : vehicle capacity (units)
    w_time         : fitness weight — total travel time
    w_dist         : fitness weight — total distance
    w_co2          : fitness weight — CO₂ emissions
    emission_factor: kg CO₂ per km
    """

    def __init__(
        self,
        n_particles:      int   = 50,
        max_iter:         int   = 300,
        beta_start:       float = 1.0,
        beta_end:         float = 0.5,
        capacity:         float = 100.0,
        w_time:           float = 0.4,
        w_dist:           float = 0.3,
        w_co2:            float = 0.1,
        emission_factor:  float = 0.21,
    ) -> None:
        self.n_particles     = n_particles
        self.max_iter        = max_iter
        self.beta_start      = beta_start
        self.beta_end        = beta_end
        self.capacity        = capacity
        self.w_time          = w_time
        self.w_dist          = w_dist
        self.w_co2           = w_co2
        self.emission_factor = emission_factor

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_positions(self, n: int) -> np.ndarray:
        """Continuous positions in [0, 1)^n."""
        return np.random.rand(self.n_particles, n)

    # ------------------------------------------------------------------
    # SPV Decoder: continuous position → route list
    # ------------------------------------------------------------------

    def _decode(
        self,
        position: np.ndarray,
        customers: List[int],
        demands:   Dict[int, float],
    ) -> List[List[int]]:
        """
        Smallest-Position-Value (SPV) rule.
        Sort customers by their position value; split into routes
        respecting capacity constraints.
        """
        order  = np.argsort(position)
        routes: List[List[int]] = [[]]
        load   = 0.0
        for idx in order:
            cust = customers[int(idx)]
            d    = demands.get(cust, 0)
            if load + d > self.capacity:
                routes.append([])
                load = 0.0
            routes[-1].append(cust)
            load += d
        return [r for r in routes if r]

    # ------------------------------------------------------------------
    # Route metrics
    # ------------------------------------------------------------------

    def _route_metrics(
        self,
        route:  List[int],
        graph:  nx.DiGraph,
        depot:  int = 0,
    ) -> Tuple[float, float]:
        """Return (total_time_min, total_distance_km) for a single route."""
        seq = [depot] + route + [depot]
        total_time = total_dist = 0.0
        for i in range(len(seq) - 1):
            u, v = seq[i], seq[i + 1]
            try:
                path = nx.shortest_path(graph, u, v, weight="weight")
                for a, b in zip(path, path[1:]):
                    total_time += graph[a][b].get("travel_time", 0)
                    total_dist += graph[a][b].get("distance", 0)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                total_time += 1e6   # large infeasibility penalty
        return total_time, total_dist

    # ------------------------------------------------------------------
    # Fitness function
    # ------------------------------------------------------------------

    def _fitness(
        self,
        position:  np.ndarray,
        graph:     nx.DiGraph,
        customers: List[int],
        demands:   Dict[int, float],
    ) -> float:
        routes = self._decode(position, customers, demands)
        total_time = total_dist = total_co2 = 0.0
        for r in routes:
            t, d = self._route_metrics(r, graph)
            total_time += t
            total_dist += d
            total_co2  += d * self.emission_factor
        return (
            self.w_time * total_time
            + self.w_dist * total_dist
            + self.w_co2  * total_co2
        )

    # ------------------------------------------------------------------
    # Main QPSO loop
    # ------------------------------------------------------------------

    def optimize(
        self,
        graph:     nx.DiGraph,
        customers: List[int],
        demands:   Dict[int, float],
        depot:     int = 0,
        verbose:   bool = False,
    ) -> Tuple[List[List[int]], float, List[float]]:
        """
        Run QPSO optimisation.

        Returns
        -------
        best_routes : list of route lists
        best_cost   : scalar fitness value
        history     : best fitness per iteration
        """
        n   = len(customers)
        rng = np.random.default_rng()

        # Initialise swarm
        pos       = self._init_positions(n)
        pbest     = pos.copy()
        pbest_fit = np.array([
            self._fitness(p, graph, customers, demands) for p in pos
        ])
        gbest_idx = int(np.argmin(pbest_fit))
        gbest     = pbest[gbest_idx].copy()
        gbest_fit = float(pbest_fit[gbest_idx])
        history: List[float] = []

        for t in range(self.max_iter):
            # Linearly decay β
            beta  = (
                self.beta_start
                - (self.beta_start - self.beta_end) * t / self.max_iter
            )
            mbest = pbest.mean(axis=0)   # mean best position

            for i in range(self.n_particles):
                phi       = rng.random(n)
                attractor = phi * pbest[i] + (1 - phi) * gbest   # local attractor
                u         = rng.random(n)
                u         = np.clip(u, 1e-10, 1.0)               # avoid log(0)
                sign      = np.where(rng.random(n) < 0.5, 1.0, -1.0)

                # Quantum position update (Laplace sampling)
                pos[i] = (
                    attractor
                    + sign * beta * np.abs(mbest - pos[i]) * np.log(1.0 / u)
                )
                pos[i] = np.clip(pos[i], 0.0, 1.0)

                fit = self._fitness(pos[i], graph, customers, demands)
                if fit < pbest_fit[i]:
                    pbest[i]     = pos[i].copy()
                    pbest_fit[i] = fit
                if fit < gbest_fit:
                    gbest     = pos[i].copy()
                    gbest_fit = fit

            history.append(gbest_fit)
            if verbose and t % 50 == 0:
                print(f"  QPSO iter {t:4d} | best fitness = {gbest_fit:.4f}")

        best_routes = self._decode(gbest, customers, demands)
        return best_routes, gbest_fit, history

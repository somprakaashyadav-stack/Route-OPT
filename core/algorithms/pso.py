"""
core/algorithms/pso.py
======================
Classical Particle Swarm Optimization (PSO) benchmark.
Uses standard velocity-based update with inertia weight decay.
Same SPV decoder and fitness function as QPSO for fair comparison.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import networkx as nx
import numpy as np


class PSOSolver:
    """
    Classical PSO benchmark solver for VRP.

    Parameters
    ----------
    n_particles : swarm size
    max_iter    : maximum iterations
    w_start     : inertia weight (start)
    w_end       : inertia weight (end, linear decay)
    c1          : cognitive coefficient
    c2          : social coefficient
    capacity    : vehicle capacity
    emission_factor : kg CO₂ per km
    """

    def __init__(
        self,
        n_particles:     int   = 50,
        max_iter:        int   = 300,
        w_start:         float = 0.9,
        w_end:           float = 0.4,
        c1:              float = 2.0,
        c2:              float = 2.0,
        capacity:        float = 100.0,
        w_time:          float = 0.4,
        w_dist:          float = 0.3,
        w_co2:           float = 0.1,
        emission_factor: float = 0.21,
    ) -> None:
        self.n_particles     = n_particles
        self.max_iter        = max_iter
        self.w_start         = w_start
        self.w_end           = w_end
        self.c1              = c1
        self.c2              = c2
        self.capacity        = capacity
        self.w_time          = w_time
        self.w_dist          = w_dist
        self.w_co2           = w_co2
        self.emission_factor = emission_factor

    def _decode(self, position, customers, demands):
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

    def _route_metrics(self, route, graph, depot=0):
        seq = [depot] + route + [depot]
        tt = td = 0.0
        for i in range(len(seq) - 1):
            try:
                path = nx.shortest_path(graph, seq[i], seq[i+1], weight="weight")
                for a, b in zip(path, path[1:]):
                    tt += graph[a][b].get("travel_time", 0)
                    td += graph[a][b].get("distance", 0)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                tt += 1e6
        return tt, td

    def _fitness(self, position, graph, customers, demands):
        routes = self._decode(position, customers, demands)
        total_time = total_dist = total_co2 = 0.0
        for r in routes:
            t, d = self._route_metrics(r, graph)
            total_time += t
            total_dist += d
            total_co2  += d * self.emission_factor
        return self.w_time*total_time + self.w_dist*total_dist + self.w_co2*total_co2

    def optimize(self, graph, customers, demands, depot=0, verbose=False):
        n   = len(customers)
        rng = np.random.default_rng()

        pos = rng.random((self.n_particles, n))
        vel = rng.uniform(-0.5, 0.5, (self.n_particles, n))

        pbest     = pos.copy()
        pbest_fit = np.array([self._fitness(p, graph, customers, demands) for p in pos])
        gbest_idx = int(np.argmin(pbest_fit))
        gbest     = pbest[gbest_idx].copy()
        gbest_fit = float(pbest_fit[gbest_idx])
        history   = []

        for t in range(self.max_iter):
            w = self.w_start - (self.w_start - self.w_end) * t / self.max_iter
            r1, r2 = rng.random((self.n_particles, n)), rng.random((self.n_particles, n))

            vel = (
                w * vel
                + self.c1 * r1 * (pbest - pos)
                + self.c2 * r2 * (gbest - pos)
            )
            pos = np.clip(pos + vel, 0.0, 1.0)

            for i in range(self.n_particles):
                fit = self._fitness(pos[i], graph, customers, demands)
                if fit < pbest_fit[i]:
                    pbest[i], pbest_fit[i] = pos[i].copy(), fit
                if fit < gbest_fit:
                    gbest, gbest_fit = pos[i].copy(), fit

            history.append(gbest_fit)
            if verbose and t % 50 == 0:
                print(f"  PSO  iter {t:4d} | best fitness = {gbest_fit:.4f}")

        return self._decode(gbest, customers, demands), gbest_fit, history

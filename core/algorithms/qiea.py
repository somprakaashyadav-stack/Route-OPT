"""
core/algorithms/qiea.py
=======================
Quantum-Inspired Evolutionary Algorithm (QIEA) for Vehicle Routing.

Key idea:
  - Each solution is a Q-chromosome: n genes, each gene is a rotation
    angle θᵢ representing a qubit (cos θᵢ, sin θᵢ).
  - Measurement collapses qubit i to binary: b=1 if sin²θᵢ > U(0,1).
  - Rotation gate steers θ toward best-known solution using a lookup table.
  - Quantum mutation randomly flips θᵢ → π/2 − θᵢ with prob p_mut.
  - Binary chromosome decoded to vehicle routes via priority rule.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np


# ---------------------------------------------------------------------------
# Rotation gate look-up table
# key  : (b_i, b_best)
# value: rotation direction (+1 or -1 or 0)
# ---------------------------------------------------------------------------
_ROTATION_SIGN: Dict[Tuple[int, int], int] = {
    (0, 0): 0,
    (0, 1): +1,   # current=0, best=1 → rotate toward 1 (increase θ)
    (1, 0): -1,   # current=1, best=0 → rotate toward 0 (decrease θ)
    (1, 1): 0,
}


class QIEASolver:
    """
    Quantum-Inspired Evolutionary Algorithm solver for VRP.

    Parameters
    ----------
    pop_size        : population size
    max_gen         : maximum generations
    delta           : rotation gate step size (radians)
    p_mut           : quantum mutation probability per gene
    capacity        : vehicle capacity
    w_time          : fitness weight — travel time
    w_dist          : fitness weight — distance
    w_co2           : fitness weight — CO₂
    emission_factor : kg CO₂ per km
    """

    def __init__(
        self,
        pop_size:        int   = 50,
        max_gen:         int   = 300,
        delta:           float = 0.02 * np.pi,
        p_mut:           float = 0.01,
        capacity:        float = 100.0,
        w_time:          float = 0.4,
        w_dist:          float = 0.3,
        w_co2:           float = 0.1,
        emission_factor: float = 0.21,
    ) -> None:
        self.pop_size        = pop_size
        self.max_gen         = max_gen
        self.delta           = delta
        self.p_mut           = p_mut
        self.capacity        = capacity
        self.w_time          = w_time
        self.w_dist          = w_dist
        self.w_co2           = w_co2
        self.emission_factor = emission_factor

    # ------------------------------------------------------------------
    # Q-chromosome initialisation
    # ------------------------------------------------------------------

    def _init_population(self, n: int) -> np.ndarray:
        """
        All genes start at θ = π/4 → equal superposition:
        P(b=0) = cos²(π/4) = 0.5,  P(b=1) = sin²(π/4) = 0.5
        """
        return np.full((self.pop_size, n), np.pi / 4)

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------

    def _measure(self, theta: np.ndarray) -> np.ndarray:
        """Collapse each qubit to 0 or 1."""
        probs = np.sin(theta) ** 2          # P(bit=1) = sin²θ
        return (np.random.rand(*theta.shape) < probs).astype(np.int8)

    # ------------------------------------------------------------------
    # Decoder: binary chromosome → route list
    # ------------------------------------------------------------------

    def _decode(
        self,
        binary:    np.ndarray,
        customers: List[int],
        demands:   Dict[int, float],
    ) -> List[List[int]]:
        """
        Priority-based decoding: customers with bit=1 get higher priority
        (served first). Splits into routes respecting capacity.
        """
        # Sort: 1s first (high priority), ties broken by index
        order  = np.argsort(-binary.astype(float))
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
        route: List[int],
        graph: nx.DiGraph,
        depot: int = 0,
    ) -> Tuple[float, float]:
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
                total_time += 1e6
        return total_time, total_dist

    # ------------------------------------------------------------------
    # Fitness function
    # ------------------------------------------------------------------

    def _fitness(
        self,
        binary:    np.ndarray,
        graph:     nx.DiGraph,
        customers: List[int],
        demands:   Dict[int, float],
    ) -> float:
        routes = self._decode(binary, customers, demands)
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
    # Rotation gate
    # ------------------------------------------------------------------

    def _rotate(
        self,
        theta:   np.ndarray,
        b:       np.ndarray,
        b_best:  np.ndarray,
        current_better: bool,
    ) -> np.ndarray:
        """Apply rotation gate to each gene."""
        for j in range(len(theta)):
            key       = (int(b[j]), int(b_best[j]))
            direction = _ROTATION_SIGN.get(key, 0)
            if current_better:
                direction = -direction    # invert: current is better, move away from best
            theta[j] += direction * self.delta
        return theta

    # ------------------------------------------------------------------
    # Quantum mutation
    # ------------------------------------------------------------------

    def _mutate(self, theta: np.ndarray) -> np.ndarray:
        """Flip selected qubits: θ → π/2 − θ (swaps sin/cos)."""
        mask = np.random.rand(len(theta)) < self.p_mut
        theta[mask] = np.pi / 2 - theta[mask]
        return theta

    # ------------------------------------------------------------------
    # Main QIEA loop
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
        Run QIEA optimisation.

        Returns
        -------
        best_routes : list of route lists
        best_cost   : scalar fitness value
        history     : best fitness per generation
        """
        n         = len(customers)
        pop_theta = self._init_population(n)     # (pop_size, n)

        best_b:   Optional[np.ndarray] = None
        best_fit: float                = np.inf
        history:  List[float]          = []

        for gen in range(self.max_gen):
            # ── Measure all chromosomes ──────────────────────────
            pop_b = np.array([self._measure(pop_theta[i])
                              for i in range(self.pop_size)])

            # ── Evaluate fitness ─────────────────────────────────
            fits = np.array([
                self._fitness(pop_b[i], graph, customers, demands)
                for i in range(self.pop_size)
            ])
            gen_best_idx = int(np.argmin(fits))

            if fits[gen_best_idx] < best_fit:
                best_fit = float(fits[gen_best_idx])
                best_b   = pop_b[gen_best_idx].copy()

            # ── Update rotation angles ───────────────────────────
            for i in range(self.pop_size):
                current_better = bool(fits[i] < best_fit)
                pop_theta[i]   = self._rotate(
                    pop_theta[i],
                    pop_b[i],
                    best_b,           # type: ignore[arg-type]
                    current_better,
                )
                pop_theta[i] = self._mutate(pop_theta[i])

            history.append(best_fit)
            if verbose and gen % 50 == 0:
                print(f"  QIEA gen {gen:4d} | best fitness = {best_fit:.4f}")

        assert best_b is not None
        best_routes = self._decode(best_b, customers, demands)
        return best_routes, best_fit, history

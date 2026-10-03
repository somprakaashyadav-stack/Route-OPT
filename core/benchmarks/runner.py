"""
core/benchmarks/runner.py
==========================
Systematic benchmarking of all algorithms on the same problem instance.

Runs each algorithm N times, records fitness, runtime, routes, and
emissions, then produces a comparison table and convergence history.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np


class BenchmarkRunner:
    """
    Run multiple solvers on the same VRP instance and collect metrics.

    Parameters
    ----------
    n_runs : number of independent runs per algorithm (for statistics)
    """

    def __init__(self, n_runs: int = 5) -> None:
        self.n_runs  = n_runs
        self.results: Dict[str, Dict] = {}

    def register(self, name: str, solver_fn: Callable) -> None:
        """
        Register a solver function.

        Parameters
        ----------
        name      : display name (e.g. "QPSO", "GA")
        solver_fn : callable with signature
                    fn(graph, customers, demands) → (routes, cost, history)
        """
        self.results[name] = {"solver": solver_fn, "runs": []}

    def run(
        self,
        graph,
        customers: List[int],
        demands:   Dict[int, float],
        verbose:   bool = False,
    ) -> None:
        """Execute all registered solvers for n_runs each."""
        for name, entry in self.results.items():
            if verbose:
                print(f"\n-- {name} ({self.n_runs} runs) --------------")
            runs = []
            for r in range(self.n_runs):
                t0 = time.perf_counter()
                try:
                    routes, cost, history = entry["solver"](graph, customers, demands)
                except Exception as exc:
                    print(f"  [{name}] run {r+1} failed: {exc}")
                    continue
                elapsed = time.perf_counter() - t0
                runs.append({
                    "routes":   routes,
                    "cost":     cost,
                    "history":  history,
                    "runtime_s": elapsed,
                })
                if verbose:
                    print(f"  run {r+1:2d}: cost={cost:.4f}  time={elapsed:.3f}s")
            entry["runs"] = runs

    def summary(self) -> List[Dict]:
        """
        Return a list of summary dicts, one per algorithm.

        Each dict: name, best_cost, mean_cost, std_cost,
                   mean_runtime_s, n_routes (last run)
        """
        rows = []
        for name, entry in self.results.items():
            runs = entry["runs"]
            if not runs:
                continue
            costs    = [r["cost"]      for r in runs]
            runtimes = [r["runtime_s"] for r in runs]
            last     = runs[int(np.argmin(costs))]
            rows.append({
                "algorithm":     name,
                "best_cost":     round(float(np.min(costs)),  4),
                "mean_cost":     round(float(np.mean(costs)), 4),
                "std_cost":      round(float(np.std(costs)),  4),
                "mean_runtime_s": round(float(np.mean(runtimes)), 4),
                "n_routes":      len(last["routes"]),
                "n_runs":        len(runs),
            })
        return sorted(rows, key=lambda x: x["best_cost"])

    def convergence_histories(self) -> Dict[str, List[float]]:
        """Return best-run convergence history per algorithm."""
        out = {}
        for name, entry in self.results.items():
            runs = entry["runs"]
            if not runs:
                continue
            costs = [r["cost"] for r in runs]
            best_run = runs[int(np.argmin(costs))]
            out[name] = best_run["history"]
        return out

    def print_table(self) -> None:
        """Print a formatted comparison table to stdout."""
        rows = self.summary()
        if not rows:
            print("No results yet. Call .run() first.")
            return
        header = f"{'Algorithm':<12} {'Best':>10} {'Mean':>10} {'Std':>10} {'Time(s)':>10} {'Routes':>7}"
        print("\n" + "=" * len(header))
        print(header)
        print("=" * len(header))
        for r in rows:
            print(
                f"{r['algorithm']:<12} "
                f"{r['best_cost']:>10.4f} "
                f"{r['mean_cost']:>10.4f} "
                f"{r['std_cost']:>10.4f} "
                f"{r['mean_runtime_s']:>10.4f} "
                f"{r['n_routes']:>7}"
            )
        print("=" * len(header))

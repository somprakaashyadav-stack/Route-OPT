"""
run_demo.py
===========
Quick command-line demo — runs all algorithms on a synthetic network
and prints a comparison table. No server required.

Usage:
    python run_demo.py
    python run_demo.py --nodes 30 --customers 12 --runs 3
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from core.graph.network       import TrafficNetwork
from core.algorithms.qpso     import QPSOSolver
from core.algorithms.qiea     import QIEASolver
from core.algorithms.pso      import PSOSolver
from core.algorithms.exact    import SavingsSolver
from core.emissions.calculator import EmissionsCalculator
from core.benchmarks.runner   import BenchmarkRunner


def main():
    parser = argparse.ArgumentParser(description="Route-OPT Demo")
    parser.add_argument("--nodes",     type=int, default=20,  help="Graph nodes")
    parser.add_argument("--customers", type=int, default=10,  help="Number of customers")
    parser.add_argument("--capacity",  type=float, default=60, help="Vehicle capacity")
    parser.add_argument("--runs",      type=int, default=3,   help="Runs per algorithm")
    parser.add_argument("--iter",      type=int, default=100, help="Max iterations")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"  Route-OPT — Quantum-Inspired Traffic Optimization Demo")
    print(f"{'='*60}")
    print(f"  Nodes: {args.nodes}  |  Customers: {args.customers}  "
          f"|  Capacity: {args.capacity}  |  Runs: {args.runs}")

    # ── Build network ─────────────────────────────────────────────
    print("\n[1/4] Building synthetic traffic network...")
    net       = TrafficNetwork().from_synthetic(n_nodes=args.nodes, seed=42)
    customers = list(range(1, args.customers + 1))
    demands   = {i: float(5 + (i % 7)) for i in customers}
    print(f"      {net.summary()}")

    # ── Register solvers ──────────────────────────────────────────
    print("\n[2/4] Registering solvers...")
    runner = BenchmarkRunner(n_runs=args.runs)

    runner.register(
        "QPSO",
        QPSOSolver(n_particles=30, max_iter=args.iter,
                   capacity=args.capacity).optimize
    )
    runner.register(
        "QIEA",
        QIEASolver(pop_size=30, max_gen=args.iter,
                   capacity=args.capacity).optimize
    )
    runner.register(
        "PSO",
        PSOSolver(n_particles=30, max_iter=args.iter,
                  capacity=args.capacity).optimize
    )
    runner.register(
        "Savings",
        SavingsSolver(capacity=args.capacity).optimize
    )

    try:
        from core.algorithms.ga_deap import GADEAPSolver
        runner.register(
            "GA",
            GADEAPSolver(pop_size=50, n_gen=args.iter,
                         capacity=args.capacity).optimize
        )
    except Exception as e:
        print(f"      [GA skipped: {e}]")

    # ── Run benchmark ─────────────────────────────────────────────
    print("\n[3/4] Running benchmark (this may take a minute)...")
    runner.run(net.G, customers, demands, verbose=True)

    # ── Print comparison table ────────────────────────────────────
    print("\n[4/4] Results")
    runner.print_table()

    # ── Emissions for best QPSO run ───────────────────────────────
    best_qpso = runner.results.get("QPSO", {}).get("runs", [])
    if best_qpso:
        best_run = min(best_qpso, key=lambda r: r["cost"])
        calc     = EmissionsCalculator("diesel_van")
        ems      = calc.route_summary(best_run["routes"], net.G)
        print("\n  Emissions (best QPSO solution):")
        for k, v in ems.items():
            print(f"    {k}: {v}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()

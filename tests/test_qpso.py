"""
tests/test_qpso.py
==================
Unit tests for QPSO and QIEA solvers.
"""

import pytest
import numpy as np
from core.graph.network    import TrafficNetwork
from core.algorithms.qpso  import QPSOSolver
from core.algorithms.qiea  import QIEASolver
from core.algorithms.pso   import PSOSolver


# ── Shared fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def small_problem():
    net       = TrafficNetwork().from_synthetic(n_nodes=10, seed=42)
    customers = list(range(1, 6))
    demands   = {i: 10.0 for i in customers}
    return net.G, customers, demands


# ── QPSO ────────────────────────────────────────────────────────────────────

class TestQPSO:

    def test_returns_routes(self, small_problem):
        graph, customers, demands = small_problem
        solver = QPSOSolver(n_particles=10, max_iter=20, capacity=50)
        routes, cost, history = solver.optimize(graph, customers, demands)
        assert isinstance(routes, list)
        assert len(routes) > 0
        assert isinstance(cost, float)

    def test_history_length(self, small_problem):
        graph, customers, demands = small_problem
        solver = QPSOSolver(n_particles=10, max_iter=30, capacity=50)
        _, _, history = solver.optimize(graph, customers, demands)
        assert len(history) == 30

    def test_history_non_increasing(self, small_problem):
        graph, customers, demands = small_problem
        solver = QPSOSolver(n_particles=20, max_iter=50, capacity=50)
        _, _, history = solver.optimize(graph, customers, demands)
        # Best fitness should be non-increasing (monotone)
        for i in range(1, len(history)):
            assert history[i] <= history[i-1] + 1e-9

    def test_all_customers_served(self, small_problem):
        graph, customers, demands = small_problem
        solver = QPSOSolver(n_particles=15, max_iter=30, capacity=50)
        routes, _, _ = solver.optimize(graph, customers, demands)
        served = [c for r in routes for c in r]
        assert set(served) == set(customers)

    def test_capacity_respected(self, small_problem):
        graph, customers, demands = small_problem
        capacity = 25.0
        solver   = QPSOSolver(n_particles=10, max_iter=20, capacity=capacity)
        routes, _, _ = solver.optimize(graph, customers, demands)
        for route in routes:
            load = sum(demands[c] for c in route)
            assert load <= capacity + 1e-9


# ── QIEA ────────────────────────────────────────────────────────────────────

class TestQIEA:

    def test_returns_routes(self, small_problem):
        graph, customers, demands = small_problem
        solver = QIEASolver(pop_size=10, max_gen=20, capacity=50)
        routes, cost, history = solver.optimize(graph, customers, demands)
        assert isinstance(routes, list)
        assert len(routes) > 0

    def test_measurement_valid(self):
        from core.algorithms.qiea import QIEASolver
        solver = QIEASolver()
        theta  = np.full(8, np.pi / 4)
        bits   = solver._measure(theta)
        assert bits.shape == (8,)
        assert all(b in (0, 1) for b in bits)

    def test_superposition_init(self):
        solver = QIEASolver()
        pop    = solver._init_population(10)
        assert pop.shape == (solver.pop_size, 10)
        # All angles should be π/4
        assert np.allclose(pop, np.pi / 4)

    def test_mutation_changes_theta(self):
        solver    = QIEASolver(p_mut=1.0)  # always mutate
        theta     = np.full(10, np.pi / 4)
        mutated   = solver._mutate(theta.copy())
        expected  = np.full(10, np.pi / 2 - np.pi / 4)
        assert np.allclose(mutated, expected)


# ── PSO ─────────────────────────────────────────────────────────────────────

class TestPSO:

    def test_returns_routes(self, small_problem):
        graph, customers, demands = small_problem
        solver = PSOSolver(n_particles=10, max_iter=20, capacity=50)
        routes, cost, history = solver.optimize(graph, customers, demands)
        assert isinstance(routes, list)
        assert len(history) == 20

    def test_cost_positive(self, small_problem):
        graph, customers, demands = small_problem
        solver = PSOSolver(n_particles=10, max_iter=20, capacity=50)
        _, cost, _ = solver.optimize(graph, customers, demands)
        assert cost >= 0

"""
tests/test_constraints.py
=========================
Tests for ConstraintHandler and EmissionsCalculator.
"""

import pytest
from core.graph.network      import TrafficNetwork
from core.constraints.handler import ConstraintHandler
from core.emissions.calculator import EmissionsCalculator


@pytest.fixture
def net():
    return TrafficNetwork().from_synthetic(n_nodes=8, seed=10)


# ── Capacity ─────────────────────────────────────────────────────────────────

class TestCapacity:

    def test_feasible(self):
        h       = ConstraintHandler(capacity=100)
        demands = {1: 30, 2: 40, 3: 20}
        assert h.check_capacity([1, 2, 3], demands) is True

    def test_infeasible(self):
        h       = ConstraintHandler(capacity=50)
        demands = {1: 30, 2: 40}
        assert h.check_capacity([1, 2], demands) is False

    def test_violation_amount(self):
        h       = ConstraintHandler(capacity=50)
        demands = {1: 30, 2: 40}
        assert h.capacity_violation([1, 2], demands) == pytest.approx(20)

    def test_no_violation(self):
        h       = ConstraintHandler(capacity=100)
        demands = {1: 30}
        assert h.capacity_violation([1], demands) == pytest.approx(0)


# ── Emergency priority ────────────────────────────────────────────────────────

class TestEmergency:

    def test_priority_reduces_weight(self, net):
        h = ConstraintHandler()
        # Find an edge that exists
        edges = list(net.G.edges())
        if not edges:
            pytest.skip("No edges in graph")
        u, v = edges[0]
        # Find a node with a predecessor
        node = v
        preds = list(net.G.predecessors(node))
        if not preds:
            pytest.skip("No predecessor for test node")
        old_weight = net.G[preds[0]][node]["weight"]
        h.apply_emergency_priority(net.G, [node], priority_boost=0.1)
        assert net.G[preds[0]][node]["weight"] < old_weight


# ── Emissions ─────────────────────────────────────────────────────────────────

class TestEmissions:

    def test_co2_diesel(self):
        calc = EmissionsCalculator("diesel_van")
        assert calc.co2_kg(100) == pytest.approx(21.0)

    def test_co2_electric_lower(self):
        elec  = EmissionsCalculator("electric")
        diesel = EmissionsCalculator("diesel_van")
        assert elec.co2_kg(100) < diesel.co2_kg(100)

    def test_fuel_litres(self):
        calc = EmissionsCalculator("diesel_van")  # 12 km/L
        assert calc.fuel_litres(120) == pytest.approx(10.0)

    def test_electric_no_fuel(self):
        calc = EmissionsCalculator("electric")
        assert calc.fuel_litres(100) == pytest.approx(0.0)

    def test_route_summary_keys(self, net):
        calc   = EmissionsCalculator()
        routes = [[1, 2], [3, 4]]
        summary = calc.route_summary(routes, net.G)
        for key in ["total_distance_km", "total_co2_kg", "total_fuel_litres"]:
            assert key in summary

    def test_savings_comparison(self, net):
        calc     = EmissionsCalculator()
        baseline = [[1, 2, 3, 4]]
        optimized = [[1, 2], [3, 4]]
        savings  = calc.savings_vs_baseline(baseline, optimized, net.G)
        assert "co2_reduction_pct" in savings

"""
tests/test_graph.py
===================
Unit tests for TrafficNetwork graph builder.
"""

import pytest
import networkx as nx
from core.graph.network import TrafficNetwork


def test_add_road():
    net = TrafficNetwork()
    net.add_road(0, 1, distance_km=2.5, base_time_min=3.0, congestion=0.1)
    assert net.G.has_edge(0, 1)
    assert net.G[0][1]["distance"] == pytest.approx(2.5)
    assert net.G[0][1]["travel_time"] == pytest.approx(3.0)


def test_weight_computation():
    net = TrafficNetwork(alpha=0.4, beta=0.4, gamma=0.2)
    net.add_road(0, 1, distance_km=1.0, base_time_min=2.0, congestion=0.5)
    expected = 0.4 * 1.0 + 0.4 * 2.0 + 0.2 * 0.5
    assert net.G[0][1]["weight"] == pytest.approx(expected, rel=1e-5)


def test_update_congestion():
    net = TrafficNetwork()
    net.add_road(0, 1, distance_km=1.0, base_time_min=1.0, congestion=0.0)
    old_weight = net.G[0][1]["weight"]
    net.update_congestion(0, 1, 0.8)
    assert net.G[0][1]["congestion"] == pytest.approx(0.8)
    assert net.G[0][1]["weight"] > old_weight


def test_synthetic_generation():
    net = TrafficNetwork().from_synthetic(n_nodes=10, seed=1)
    assert net.G.number_of_nodes() == 10
    assert net.G.number_of_edges() > 0


def test_geojson_export():
    net = TrafficNetwork().from_synthetic(n_nodes=5, seed=2)
    gj = net.to_geojson()
    assert gj["type"] == "FeatureCollection"
    assert len(gj["features"]) > 0


def test_shortest_path():
    net = TrafficNetwork().from_synthetic(n_nodes=10, seed=3)
    try:
        path = net.shortest_path(0, 5)
        assert path[0] == 0
        assert path[-1] == 5
    except nx.NetworkXNoPath:
        pytest.skip("No path between 0 and 5 in this random graph")


def test_summary():
    net = TrafficNetwork().from_synthetic(n_nodes=8, seed=4)
    s = net.summary()
    assert "nodes" in s
    assert s["nodes"] == 8

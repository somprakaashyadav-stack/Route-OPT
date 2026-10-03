"""
core/graph/network.py
=====================
Weighted directed graph representing the urban road network.

Nodes  : intersections / depots / customer locations
Edges  : road segments with dynamic weights
Weight : w(t) = α·distance + β·travel_time + γ·congestion
"""

from __future__ import annotations

import json
import math
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np


# ---------------------------------------------------------------------------
# Emission factors (kg CO₂ / km)  — DEFRA 2023
# ---------------------------------------------------------------------------
EMISSION_FACTORS: Dict[str, float] = {
    "petrol_car":  0.170,
    "diesel_van":  0.210,
    "electric":    0.053,
    "truck":       0.330,
    "motorcycle":  0.114,
}


class TrafficNetwork:
    """
    Road network modelled as a weighted directed graph.

    Parameters
    ----------
    alpha : float
        Weight for physical distance in edge cost.
    beta  : float
        Weight for travel time in edge cost.
    gamma : float
        Weight for congestion penalty in edge cost.
    """

    def __init__(
        self,
        alpha: float = 0.4,
        beta:  float = 0.4,
        gamma: float = 0.2,
    ) -> None:
        self.G     = nx.DiGraph()
        self.alpha = alpha
        self.beta  = beta
        self.gamma = gamma

    # ------------------------------------------------------------------
    # Edge management
    # ------------------------------------------------------------------

    def _compute_weight(
        self,
        distance_km:   float,
        travel_time_min: float,
        congestion:    float,
    ) -> float:
        return (
            self.alpha * distance_km
            + self.beta  * travel_time_min
            + self.gamma * congestion
        )

    def add_road(
        self,
        u: int,
        v: int,
        distance_km:     float,
        base_time_min:   float,
        congestion:      float = 0.0,
        speed_limit_kmh: float = 50.0,
        **attrs,
    ) -> None:
        """Add a directed road segment (u → v)."""
        w = self._compute_weight(distance_km, base_time_min, congestion)
        self.G.add_edge(
            u, v,
            weight=w,
            distance=distance_km,
            travel_time=base_time_min,
            congestion=congestion,
            speed_limit=speed_limit_kmh,
            **attrs,
        )

    def update_congestion(self, u: int, v: int, new_congestion: float) -> None:
        """
        Dynamically update edge congestion (called by SUMO adapter).
        Recomputes the composite edge weight in-place.
        """
        if not self.G.has_edge(u, v):
            return
        self.G[u][v]["congestion"] = new_congestion
        self.G[u][v]["weight"] = self._compute_weight(
            self.G[u][v]["distance"],
            self.G[u][v]["travel_time"],
            new_congestion,
        )

    # ------------------------------------------------------------------
    # Node management
    # ------------------------------------------------------------------

    def add_node(
        self,
        node_id: int,
        x: float = 0.0,
        y: float = 0.0,
        node_type: str = "intersection",
        **attrs,
    ) -> None:
        """Add a graph node with geographic coordinates."""
        self.G.add_node(node_id, x=x, y=y, node_type=node_type, **attrs)

    # ------------------------------------------------------------------
    # Loaders
    # ------------------------------------------------------------------

    def from_csv(self, nodes_csv: str, edges_csv: str) -> "TrafficNetwork":
        """Load graph from CSV files (nodes.csv, edges.csv)."""
        import csv

        with open(nodes_csv, newline="") as f:
            for row in csv.DictReader(f):
                self.add_node(
                    int(row["id"]),
                    x=float(row.get("x", 0)),
                    y=float(row.get("y", 0)),
                    node_type=row.get("type", "intersection"),
                )

        with open(edges_csv, newline="") as f:
            for row in csv.DictReader(f):
                self.add_road(
                    int(row["source"]),
                    int(row["target"]),
                    distance_km=float(row["distance_km"]),
                    base_time_min=float(row["travel_time_min"]),
                    congestion=float(row.get("congestion", 0)),
                )
        return self

    def from_osm(self, place_name: str) -> "TrafficNetwork":
        """
        Load directly from OpenStreetMap via OSMnx.
        Requires: pip install osmnx
        """
        try:
            import osmnx as ox
        except ImportError:
            raise ImportError("Install osmnx: pip install osmnx")

        G_osm = ox.graph_from_place(place_name, network_type="drive")
        G_osm = ox.add_edge_speeds(G_osm)
        G_osm = ox.add_edge_travel_times(G_osm)

        for node, data in G_osm.nodes(data=True):
            self.add_node(node, x=data.get("x", 0), y=data.get("y", 0))

        for u, v, data in G_osm.edges(data=True):
            dist = data.get("length", 0) / 1000          # m → km
            tt   = data.get("travel_time", 0) / 60       # s → min
            spd  = data.get("speed_kph", 50)
            self.add_road(u, v, dist, tt, speed_limit_kmh=float(spd))

        return self

    def from_synthetic(self, n_nodes: int = 20, seed: int = 42) -> "TrafficNetwork":
        """
        Generate a random connected road network for testing.
        Uses a planar-like random geometric graph.
        """
        rng = np.random.default_rng(seed)

        # Place nodes on a grid-ish layout
        for i in range(n_nodes):
            x = float(rng.uniform(0, 100))
            y = float(rng.uniform(0, 100))
            ntype = "depot" if i == 0 else "customer" if i <= n_nodes // 3 else "intersection"
            self.add_node(i, x=x, y=y, node_type=ntype)

        # Add edges (connect each node to ~3 nearest neighbours)
        coords = np.array([
            [self.G.nodes[i]["x"], self.G.nodes[i]["y"]]
            for i in range(n_nodes)
        ])
        for i in range(n_nodes):
            dists = np.linalg.norm(coords - coords[i], axis=1)
            dists[i] = np.inf
            nearest = np.argsort(dists)[:3]
            for j in nearest:
                dist_km = float(dists[j]) / 10        # scale to km
                tt_min  = dist_km / (50 / 60)          # 50 km/h
                cong    = float(rng.uniform(0, 0.3))
                self.add_road(i, int(j), dist_km, tt_min, congestion=cong)
                self.add_road(int(j), i, dist_km, tt_min, congestion=cong)  # bidirectional

        # Ensure connectivity by adding a spanning backbone
        nodes = list(range(n_nodes))
        rng.shuffle(nodes)
        for k in range(len(nodes) - 1):
            u, v = nodes[k], nodes[k + 1]
            if not self.G.has_edge(u, v):
                dist_km = float(np.linalg.norm(coords[u] - coords[v])) / 10
                tt_min  = dist_km / (50 / 60)
                self.add_road(u, v, dist_km, tt_min)
                self.add_road(v, u, dist_km, tt_min)

        return self

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def shortest_path(self, source: int, target: int) -> List[int]:
        return nx.shortest_path(self.G, source, target, weight="weight")

    def shortest_path_length(self, source: int, target: int) -> float:
        return nx.shortest_path_length(self.G, source, target, weight="weight")

    def adjacency_matrix(self) -> np.ndarray:
        return nx.to_numpy_array(self.G, weight="weight")

    def to_geojson(self) -> dict:
        """Export graph as GeoJSON FeatureCollection."""
        features = []
        for u, v, data in self.G.edges(data=True):
            xu = self.G.nodes[u].get("x", 0)
            yu = self.G.nodes[u].get("y", 0)
            xv = self.G.nodes[v].get("x", 0)
            yv = self.G.nodes[v].get("y", 0)
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[xu, yu], [xv, yv]],
                },
                "properties": {
                    "source": u,
                    "target": v,
                    "weight": data.get("weight", 0),
                    "distance_km": data.get("distance", 0),
                    "travel_time_min": data.get("travel_time", 0),
                    "congestion": data.get("congestion", 0),
                },
            })
        for node, data in self.G.nodes(data=True):
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [data.get("x", 0), data.get("y", 0)],
                },
                "properties": {
                    "id": node,
                    "type": data.get("node_type", "intersection"),
                },
            })
        return {"type": "FeatureCollection", "features": features}

    def summary(self) -> Dict:
        return {
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges(),
            "is_strongly_connected": nx.is_strongly_connected(self.G),
            "avg_degree": (
                sum(d for _, d in self.G.degree()) / max(self.G.number_of_nodes(), 1)
            ),
        }

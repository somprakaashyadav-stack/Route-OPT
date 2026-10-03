"""
simulation/sumo/adapter.py
==========================
SUMO TraCI adapter for live traffic data injection.

Reads per-step edge occupancy from SUMO and pushes it into the
TrafficNetwork graph, triggering dynamic weight updates.

Requires SUMO to be installed and `traci` on PYTHONPATH.
Install SUMO: https://sumo.dlr.de/docs/Installing/index.html
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

try:
    import traci
    SUMO_AVAILABLE = True
except ImportError:
    SUMO_AVAILABLE = False


class SUMOAdapter:
    """
    Bridge between SUMO simulation and the TrafficNetwork graph.

    Parameters
    ----------
    sumo_cfg    : path to SUMO .sumocfg file
    network     : TrafficNetwork instance to update
    edge_map    : dict mapping SUMO edge IDs → graph (u, v) tuples
    use_gui     : launch SUMO-GUI instead of headless SUMO
    replan_every: number of simulation steps between re-optimizations
    """

    def __init__(
        self,
        sumo_cfg:     str,
        network,                          # TrafficNetwork
        edge_map:     Optional[Dict[str, Tuple[int, int]]] = None,
        use_gui:      bool  = False,
        replan_every: int   = 50,
    ) -> None:
        if not SUMO_AVAILABLE:
            raise ImportError(
                "SUMO TraCI not found.\n"
                "Install SUMO from https://sumo.dlr.de and add its tools/ "
                "directory to PYTHONPATH."
            )
        self.sumo_cfg     = sumo_cfg
        self.network      = network
        self.edge_map     = edge_map or {}
        self.use_gui      = use_gui
        self.replan_every = replan_every
        self._step_count  = 0

    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch SUMO and open TraCI connection."""
        binary = "sumo-gui" if self.use_gui else "sumo"
        traci.start([binary, "-c", self.sumo_cfg, "--no-step-log"])

    def step(self) -> bool:
        """
        Advance simulation by one step and update graph weights.
        Returns False when simulation is finished.
        """
        if traci.simulation.getMinExpectedNumber() <= 0:
            return False

        traci.simulationStep()
        self._step_count += 1

        # Update edge congestion on the graph
        for edge_id in traci.edge.getIDList():
            occupancy = traci.edge.getLastStepOccupancy(edge_id)
            if edge_id in self.edge_map:
                u, v = self.edge_map[edge_id]
                if self.network.G.has_edge(u, v):
                    self.network.update_congestion(u, v, float(occupancy))

        return True

    def run_until_done(
        self,
        optimizer_callback=None,
        max_steps: int = 3600,
    ) -> None:
        """
        Run simulation to completion, calling optimizer every N steps.

        Parameters
        ----------
        optimizer_callback : fn() called every replan_every steps
        max_steps          : hard step limit
        """
        step = 0
        while step < max_steps:
            alive = self.step()
            if not alive:
                break
            if (optimizer_callback is not None
                    and self._step_count % self.replan_every == 0):
                optimizer_callback()
            step += 1

    def get_traffic_snapshot(self) -> Dict[str, float]:
        """Return {edge_id: occupancy} for current step."""
        return {
            eid: traci.edge.getLastStepOccupancy(eid)
            for eid in traci.edge.getIDList()
        }

    def inject_vehicle(
        self,
        vehicle_id: str,
        route_id:   str,
        depart:     float = 0.0,
    ) -> None:
        """Add a vehicle to the SUMO simulation."""
        traci.vehicle.add(vehicle_id, route_id, depart=depart)

    def close(self) -> None:
        """Terminate SUMO simulation."""
        traci.close()

    # ------------------------------------------------------------------
    # Edge map builder utility
    # ------------------------------------------------------------------

    @staticmethod
    def build_edge_map_from_net(net_xml: str) -> Dict[str, Tuple[int, int]]:
        """
        Parse a SUMO .net.xml file and build {edge_id: (from_node, to_node)}.
        Requires the `sumolib` package (ships with SUMO).
        """
        try:
            import sumolib
        except ImportError:
            raise ImportError("sumolib not found. Install SUMO tools.")

        net      = sumolib.net.readNet(net_xml)
        edge_map = {}
        for edge in net.getEdges():
            from_id = int(edge.getFromNode().getID())
            to_id   = int(edge.getToNode().getID())
            edge_map[edge.getID()] = (from_id, to_id)
        return edge_map

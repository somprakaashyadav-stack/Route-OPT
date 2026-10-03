"""
api/main.py
===========
FastAPI backend for the Route-OPT platform.

Endpoints
---------
GET  /api/graph              → GeoJSON road network
POST /api/optimize           → run algorithm, return job_id
GET  /api/result/{job_id}    → poll optimization result
GET  /api/convergence/{job_id} → convergence history
GET  /api/emissions/{job_id} → CO₂ / fuel summary
GET  /api/benchmark          → run all algorithms and compare
WS   /ws/traffic             → live traffic stream (simulated)
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Route-OPT imports ────────────────────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.graph.network     import TrafficNetwork
from core.algorithms.qpso   import QPSOSolver
from core.algorithms.qiea   import QIEASolver
from core.algorithms.pso    import PSOSolver
from core.algorithms.ga_deap import GADEAPSolver
from core.algorithms.exact  import SavingsSolver
from core.constraints.handler import ConstraintHandler
from core.emissions.calculator import EmissionsCalculator
from core.benchmarks.runner   import BenchmarkRunner

# ── App ──────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Route-OPT API",
    description="Quantum-Inspired Traffic Route Optimization Platform",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory job store (replace with DB in production) ──────────────────────
JOB_STORE: Dict[str, Dict] = {}

# ── Default network (synthetic 25-node) ─────────────────────────────────────
DEFAULT_NETWORK = TrafficNetwork().from_synthetic(n_nodes=25, seed=99)
DEFAULT_CUSTOMERS = [i for i in range(1, 16)]
DEFAULT_DEMANDS   = {i: float(5 + (i % 7)) for i in DEFAULT_CUSTOMERS}


# ── Pydantic models ───────────────────────────────────────────────────────────

class OptimizeRequest(BaseModel):
    algorithm:    str   = "qpso"       # qpso | qiea | pso | ga | savings
    n_customers:  int   = 15
    capacity:     float = 100.0
    n_particles:  int   = 30
    max_iter:     int   = 100
    vehicle_type: str   = "diesel_van"
    seed:         int   = 42


class EmergencyRequest(BaseModel):
    nodes:          List[int]
    priority_boost: float = 0.1


# ── Algorithm factory ─────────────────────────────────────────────────────────

def _make_solver(req: OptimizeRequest):
    algo = req.algorithm.lower()
    kwargs = dict(capacity=req.capacity)
    if algo == "qpso":
        return QPSOSolver(n_particles=req.n_particles,
                          max_iter=req.max_iter, **kwargs)
    elif algo == "qiea":
        return QIEASolver(pop_size=req.n_particles,
                          max_gen=req.max_iter, **kwargs)
    elif algo == "pso":
        return PSOSolver(n_particles=req.n_particles,
                         max_iter=req.max_iter, **kwargs)
    elif algo == "ga":
        return GADEAPSolver(pop_size=req.n_particles,
                            n_gen=req.max_iter, **kwargs)
    elif algo == "savings":
        return SavingsSolver(**kwargs)
    else:
        raise ValueError(f"Unknown algorithm: {req.algorithm}")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/graph")
def get_graph():
    """Return the road network as GeoJSON."""
    return DEFAULT_NETWORK.to_geojson()


@app.get("/api/graph/summary")
def get_graph_summary():
    """Return graph statistics."""
    return DEFAULT_NETWORK.summary()


@app.post("/api/optimize")
def start_optimize(req: OptimizeRequest):
    """
    Start an optimization job and return a job_id.
    For the prototype this runs synchronously; production would use
    a background task queue (Celery / RQ).
    """
    net       = TrafficNetwork().from_synthetic(n_nodes=25, seed=req.seed)
    customers = list(range(1, req.n_customers + 1))
    demands   = {i: float(5 + (i % 7)) for i in customers}

    try:
        solver = _make_solver(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    t0 = time.perf_counter()
    routes, cost, history = solver.optimize(net.G, customers, demands)
    elapsed = time.perf_counter() - t0

    calc     = EmissionsCalculator(vehicle_type=req.vehicle_type)
    emissions = calc.route_summary(routes, net.G)

    job_id = str(uuid.uuid4())
    JOB_STORE[job_id] = {
        "status":     "done",
        "algorithm":  req.algorithm,
        "routes":     routes,
        "cost":       cost,
        "history":    history,
        "runtime_s":  round(elapsed, 4),
        "emissions":  emissions,
        "geojson":    net.to_geojson(),
    }
    return {"job_id": job_id, "status": "done", "cost": cost,
            "runtime_s": round(elapsed, 4)}


@app.get("/api/result/{job_id}")
def get_result(job_id: str):
    """Return full result for a completed job."""
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "job_id":    job_id,
        "status":    job["status"],
        "algorithm": job["algorithm"],
        "routes":    job["routes"],
        "cost":      job["cost"],
        "runtime_s": job["runtime_s"],
    }


@app.get("/api/convergence/{job_id}")
def get_convergence(job_id: str):
    """Return fitness-vs-iteration history."""
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, "history": job["history"]}


@app.get("/api/emissions/{job_id}")
def get_emissions(job_id: str):
    """Return CO₂ and fuel summary for a job."""
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"job_id": job_id, **job["emissions"]}


@app.post("/api/emergency")
def apply_emergency(req: EmergencyRequest):
    """Apply emergency priority weight reduction to specified nodes."""
    handler = ConstraintHandler()
    handler.apply_emergency_priority(
        DEFAULT_NETWORK.G,
        req.nodes,
        req.priority_boost,
    )
    return {"message": f"Emergency priority applied to nodes {req.nodes}"}


@app.get("/api/benchmark")
def run_benchmark():
    """
    Run all algorithms on the default scenario and return comparison table.
    Uses reduced iterations for speed; increase for research runs.
    """
    net       = TrafficNetwork().from_synthetic(n_nodes=20, seed=7)
    customers = list(range(1, 11))
    demands   = {i: float(5 + (i % 5)) for i in customers}

    runner = BenchmarkRunner(n_runs=2)
    runner.register("QPSO",    QPSOSolver(n_particles=20, max_iter=50).optimize)
    runner.register("QIEA",    QIEASolver(pop_size=20,    max_gen=50).optimize)
    runner.register("PSO",     PSOSolver(n_particles=20,  max_iter=50).optimize)
    runner.register("Savings", SavingsSolver().optimize)

    try:
        runner.register("GA",  GADEAPSolver(pop_size=30, n_gen=50).optimize)
    except ImportError:
        pass   # DEAP not installed

    runner.run(net.G, customers, demands, verbose=False)
    return {
        "summary":    runner.summary(),
        "convergence": runner.convergence_histories(),
    }


# ── WebSocket: simulated live traffic stream ──────────────────────────────────

@app.websocket("/ws/traffic")
async def traffic_websocket(ws: WebSocket):
    """
    Send simulated traffic updates (congestion per edge) every second.
    In production this would relay real SUMO TraCI data.
    """
    await ws.accept()
    import random
    try:
        while True:
            edges = list(DEFAULT_NETWORK.G.edges())
            updates = []
            for u, v in random.sample(edges, min(5, len(edges))):
                cong = round(random.uniform(0, 1), 3)
                DEFAULT_NETWORK.update_congestion(u, v, cong)
                updates.append({"u": u, "v": v, "congestion": cong})
            await ws.send_json({"type": "traffic_update", "updates": updates})
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}

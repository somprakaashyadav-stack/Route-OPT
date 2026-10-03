# 🚦 Route-OPT — Quantum-Inspired Traffic Route Optimization

A complete software platform implementing **QPSO** and **QIEA** algorithms for intelligent vehicle routing, benchmarked against classical methods (PSO, GA, Savings), with real-time SUMO simulation, CO₂ tracking, and a React dashboard.

---

## 📁 Project Structure

```
Route-OPT/
├── core/
│   ├── graph/              # TrafficNetwork (NetworkX + OSMnx)
│   ├── algorithms/
│   │   ├── qpso.py         # Quantum PSO solver
│   │   ├── qiea.py         # Quantum-Inspired EA (qubit encoding)
│   │   ├── pso.py          # Classical PSO benchmark
│   │   ├── ga_deap.py      # GA via DEAP
│   │   ├── exact.py        # Dijkstra, A*, Clarke-Wright Savings
│   │   └── qiskit_qaoa.py  # Optional Qiskit QAOA stub
│   ├── constraints/        # Capacity, time-window, emergency priority
│   ├── emissions/          # CO₂ / fuel calculator (DEFRA 2023)
│   └── benchmarks/         # BenchmarkRunner (multi-run statistics)
├── simulation/sumo/        # SUMO TraCI adapter
├── api/main.py             # FastAPI backend (REST + WebSocket)
├── dashboard/              # React + Recharts dashboard
├── tests/                  # pytest test suite
├── docker/                 # Dockerfiles + DB init SQL
├── docker-compose.yml
├── run_demo.py             # Quick CLI demo
└── requirements.txt
```

---

## ⚡ Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run CLI demo (no server needed)
```bash
python run_demo.py
# Options:
python run_demo.py --nodes 30 --customers 12 --runs 3 --iter 150
```

### 3. Run tests
```bash
pytest tests/ -v
```

### 4. Start the API server
```bash
uvicorn api.main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### 5. Start the React dashboard
```bash
cd dashboard
npm install
npm start
```
Dashboard: http://localhost:3000

### 6. Full Docker stack
```bash
docker compose up --build
```

---

## 🔬 Algorithms

| Algorithm | Type | Key Idea |
|-----------|------|----------|
| **QPSO** | Quantum-Inspired | Delta-potential Laplace sampling; no velocity needed |
| **QIEA** | Quantum-Inspired | Qubit chromosomes + rotation gate update |
| **PSO**  | Classical | Velocity-based inertia + cognitive/social |
| **GA (DEAP)** | Classical | Order crossover + swap mutation |
| **Savings** | Greedy | Clarke-Wright savings heuristic |
| **QAOA** | Quantum (optional) | Qiskit circuit for small sub-problems |

---

## 📊 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET  | `/api/graph` | GeoJSON road network |
| POST | `/api/optimize` | Run optimization job |
| GET  | `/api/result/{id}` | Fetch result |
| GET  | `/api/convergence/{id}` | Fitness history |
| GET  | `/api/emissions/{id}` | CO₂ / fuel summary |
| POST | `/api/emergency` | Apply emergency node priority |
| GET  | `/api/benchmark` | All-algorithm comparison |
| WS   | `/ws/traffic` | Live traffic stream |

---

## 🌿 Emission Factors (DEFRA 2023)

| Vehicle | kg CO₂/km |
|---------|----------|
| Diesel Van | 0.210 |
| Petrol Car | 0.170 |
| Electric | 0.053 |
| Truck | 0.330 |
| Motorcycle | 0.114 |

---

## 🔧 Configuration

Edit `core/algorithms/qpso.py` constructor defaults or pass via API:

```json
{
  "algorithm": "qpso",
  "n_customers": 15,
  "capacity": 100,
  "n_particles": 50,
  "max_iter": 300,
  "vehicle_type": "diesel_van"
}
```

---

## 📈 Benchmarking

```python
from core.benchmarks.runner import BenchmarkRunner
from core.algorithms.qpso   import QPSOSolver
from core.algorithms.qiea   import QIEASolver

runner = BenchmarkRunner(n_runs=30)
runner.register("QPSO", QPSOSolver(n_particles=50, max_iter=300).optimize)
runner.register("QIEA", QIEASolver(pop_size=50,    max_gen=300).optimize)
runner.run(graph, customers, demands)
runner.print_table()
```

---

## 🚗 SUMO Integration

```python
from simulation.sumo.adapter import SUMOAdapter
adapter = SUMOAdapter("data/sumo/city.sumocfg", network)
adapter.start()
adapter.run_until_done(optimizer_callback=lambda: solver.optimize(...))
adapter.close()
```

---

## 📦 Requirements

- Python 3.11+
- networkx, numpy, scipy, matplotlib
- deap (GA benchmark)
- fastapi, uvicorn (API server)
- react, leaflet, recharts (dashboard)
- SUMO *(optional, for live simulation)*
- qiskit *(optional, for QAOA)*

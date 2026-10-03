/**
 * dashboard/src/App.js
 * =====================
 * Route-OPT — Quantum-Inspired Traffic Optimization Dashboard
 *
 * Features:
 *  - Full Dark / Light mode toggle (CSS custom properties via data-theme)
 *  - Live SVG network map with congestion heat colouring
 *  - Control panel: algorithm, population, iterations, vehicle type, capacity
 *  - KPI cards: cost, routes, runtime, CO₂, fuel, distance
 *  - Convergence chart (Recharts) per algorithm
 *  - Benchmark comparison table + multi-algo convergence chart
 *  - Emergency priority override
 *  - Live traffic WebSocket feed
 */

import React, {
  useState, useEffect, useRef, useCallback, createContext, useContext
} from 'react';
import axios from 'axios';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, Legend,
  ResponsiveContainer, CartesianGrid, AreaChart, Area
} from 'recharts';

// ── Theme Context ─────────────────────────────────────────────────────────────
const ThemeCtx = createContext({ theme: 'dark', toggle: () => {} });

function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    const saved = localStorage.getItem('routeopt-theme');
    return saved || 'dark';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('routeopt-theme', theme);
  }, [theme]);

  const toggle = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'));
  return <ThemeCtx.Provider value={{ theme, toggle }}>{children}</ThemeCtx.Provider>;
}

// ── Design tokens (mirrors CSS vars for JS use) ───────────────────────────────
function useTokens() {
  const { theme } = useContext(ThemeCtx);
  const dark = theme === 'dark';
  return {
    bgBase:       dark ? '#0d1117'  : '#f6f8fa',
    bgSurface:    dark ? '#161b22'  : '#ffffff',
    bgElevated:   dark ? '#21262d'  : '#f0f3f6',
    border:       dark ? '#30363d'  : '#d0d7de',
    textPrimary:  dark ? '#e6edf3'  : '#1f2328',
    textMuted:    dark ? '#8b949e'  : '#656d76',
    textFaint:    dark ? '#484f58'  : '#9a9fa8',
    accentBlue:   dark ? '#58a6ff'  : '#0969da',
    accentGreen:  dark ? '#3fb950'  : '#1a7f37',
    accentOrange: dark ? '#ffa657'  : '#bf8700',
    accentRed:    dark ? '#f78166'  : '#cf222e',
    accentPurple: dark ? '#d2a8ff'  : '#8250df',
    btnPrimary:   dark ? '#1f6feb'  : '#0969da',
    btnDanger:    dark ? '#b91c1c'  : '#cf222e',
    chartGrid:    dark ? '#21262d'  : '#e5e9ed',
    tooltipBg:    dark ? '#161b22'  : '#ffffff',
    svgBg:        dark ? '#0d1117'  : '#f0f3f6',
  };
}

// ── Colour maps ───────────────────────────────────────────────────────────────
const ALGO_COLORS = {
  QPSO: '#58a6ff', QIEA: '#3fb950', PSO: '#f78166',
  GA: '#d2a8ff', Savings: '#ffa657'
};

const ROUTE_COLORS = [
  '#58a6ff', '#3fb950', '#ffa657', '#f78166',
  '#d2a8ff', '#79c0ff', '#56d364', '#ff9f1c'
];

const API = ''; // proxied to http://localhost:8000

// ── Reusable UI primitives ────────────────────────────────────────────────────

function Card({ children, style = {} }) {
  const t = useTokens();
  return (
    <div style={{
      background: t.bgSurface,
      border: `1px solid ${t.border}`,
      borderRadius: 12,
      padding: 20,
      ...style,
    }}>
      {children}
    </div>
  );
}

function Label({ children }) {
  const t = useTokens();
  return (
    <span style={{ fontSize: 11, color: t.textMuted, fontWeight: 600,
                   letterSpacing: '0.5px', textTransform: 'uppercase' }}>
      {children}
    </span>
  );
}

function Select({ value, onChange, children }) {
  const t = useTokens();
  return (
    <select
      value={value}
      onChange={onChange}
      style={{
        display: 'block', marginTop: 6,
        background: t.bgElevated, color: t.textPrimary,
        border: `1px solid ${t.border}`, borderRadius: 8,
        padding: '7px 11px', fontSize: 13, cursor: 'pointer',
        outline: 'none', width: '100%',
      }}
    >
      {children}
    </select>
  );
}

function RangeField({ label, value, min, max, step = 1, onChange }) {
  const t = useTokens();
  return (
    <div>
      <Label>{label}: <span style={{ color: t.accentBlue }}>{value}</span></Label>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(+e.target.value)}
        style={{ display: 'block', marginTop: 8, width: '100%', accentColor: t.accentBlue }}
      />
    </div>
  );
}

function Btn({ onClick, disabled, variant = 'primary', children, style = {} }) {
  const t = useTokens();
  const base = {
    primary: { bg: t.btnPrimary, color: '#fff', border: 'none' },
    outline:  { bg: 'transparent', color: t.accentBlue, border: `1px solid ${t.accentBlue}` },
    danger:   { bg: t.btnDanger,   color: '#fff', border: 'none' },
  }[variant];
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: disabled ? t.bgElevated : base.bg,
        color: disabled ? t.textMuted : base.color,
        border: disabled ? `1px solid ${t.border}` : base.border,
        borderRadius: 8, padding: '8px 20px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontWeight: 600, fontSize: 13,
        transition: 'background 0.15s, opacity 0.15s',
        ...style,
      }}
    >
      {children}
    </button>
  );
}

// ── KPI Card ──────────────────────────────────────────────────────────────────
function KPICard({ label, value, unit, color }) {
  const t = useTokens();
  return (
    <div style={{
      background: t.bgSurface,
      border: `1px solid ${t.border}`,
      borderLeft: `3px solid ${color}`,
      borderRadius: 10,
      padding: '14px 18px',
      flex: 1, minWidth: 120,
    }}>
      <div style={{ fontSize: 11, color: t.textMuted, marginBottom: 6,
                    fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.4px' }}>
        {label}
      </div>
      <div style={{ fontSize: 22, fontWeight: 700, color }}>
        {value ?? '—'}
        <span style={{ fontSize: 11, color: t.textMuted, marginLeft: 4 }}>{unit}</span>
      </div>
    </div>
  );
}

// ── Theme Toggle Button ───────────────────────────────────────────────────────
function ThemeToggle() {
  const { theme, toggle } = useContext(ThemeCtx);
  const t = useTokens();
  return (
    <button
      onClick={toggle}
      title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
      style={{
        background: t.bgElevated,
        border: `1px solid ${t.border}`,
        borderRadius: 8,
        padding: '7px 14px',
        cursor: 'pointer',
        fontSize: 16,
        color: t.textPrimary,
        transition: 'background 0.2s',
      }}
    >
      {theme === 'dark' ? '☀️' : '🌙'}
    </button>
  );
}

// ── Network SVG Canvas ────────────────────────────────────────────────────────
const NetworkSVG = React.memo(function NetworkSVG({ graphData, result, trafficMap }) {
  const t = useTokens();
  if (!graphData) {
    return (
      <div style={{ color: t.textMuted, padding: 40, textAlign: 'center' }}>
        ⌛ Loading network graph…
      </div>
    );
  }

  const nodes = graphData.features.filter(f => f.geometry.type === 'Point');
  const edges = graphData.features.filter(f => f.geometry.type === 'LineString');

  const xs = nodes.map(n => n.geometry.coordinates[0]);
  const ys = nodes.map(n => n.geometry.coordinates[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);

  const W = 700, H = 420, pad = 40;
  const sx = x => pad + ((x - minX) / (maxX - minX + 0.001)) * (W - 2 * pad);
  const sy = y => H - pad - ((y - minY) / (maxY - minY + 0.001)) * (H - 2 * pad);

  const routeNodes = new Set((result?.routes || []).flat());

  // Edge congestion from live traffic map
  const getCong = (u, v) => {
    const key = `${u}-${v}`;
    if (trafficMap[key] !== undefined) return trafficMap[key];
    return edges.find(e => e.properties.source === u && e.properties.target === v)
      ?.properties.congestion || 0;
  };

  const edgeColor = (cong) => {
    if (cong > 0.65) return '#f78166';
    if (cong > 0.35) return '#ffa657';
    return t.border;
  };

  const nodeColor = (n) => {
    if (n.properties.type === 'depot')    return '#ffa657';
    if (routeNodes.has(n.properties.id))  return '#58a6ff';
    return t.bgElevated;
  };

  const nodeStroke = (n) => {
    if (n.properties.type === 'depot')    return '#f0883e';
    if (routeNodes.has(n.properties.id))  return '#1f6feb';
    return t.border;
  };

  return (
    <svg
      width="100%"
      viewBox={`0 0 ${W} ${H}`}
      style={{ background: t.svgBg, borderRadius: 10, display: 'block' }}
    >
      {/* Edges */}
      {edges.map((e, i) => {
        const [x1, y1] = e.geometry.coordinates[0];
        const [x2, y2] = e.geometry.coordinates[1];
        const cong = getCong(e.properties.source, e.properties.target);
        return (
          <line
            key={i}
            x1={sx(x1)} y1={sy(y1)} x2={sx(x2)} y2={sy(y2)}
            stroke={edgeColor(cong)}
            strokeWidth={cong > 0.6 ? 2 : 1}
            opacity={0.75}
          />
        );
      })}

      {/* Optimized Route Paths */}
      {(result?.routes || []).map((route, ri) => {
        const color = ROUTE_COLORS[ri % ROUTE_COLORS.length];
        return route.map((cust, ci) => {
          if (ci === 0) return null;
          const prev = route[ci - 1];
          const nA = nodes.find(n => n.properties.id === prev);
          const nB = nodes.find(n => n.properties.id === cust);
          if (!nA || !nB) return null;
          return (
            <line
              key={`r${ri}-${ci}`}
              x1={sx(nA.geometry.coordinates[0])} y1={sy(nA.geometry.coordinates[1])}
              x2={sx(nB.geometry.coordinates[0])} y2={sy(nB.geometry.coordinates[1])}
              stroke={color} strokeWidth={2.8} strokeDasharray="7 3"
              opacity={0.9}
            />
          );
        });
      })}

      {/* Nodes */}
      {nodes.map((n, i) => {
        const [x, y] = n.geometry.coordinates;
        const isDepot = n.properties.type === 'depot';
        return (
          <g key={i}>
            <circle
              cx={sx(x)} cy={sy(y)}
              r={isDepot ? 9 : 5}
              fill={nodeColor(n)}
              stroke={nodeStroke(n)}
              strokeWidth={isDepot ? 2.5 : 1.5}
            />
            {isDepot && (
              <text
                x={sx(x) + 13} y={sy(y) + 4}
                fill="#ffa657" fontSize={10} fontWeight={700}
              >
                Depot
              </text>
            )}
          </g>
        );
      })}

      {/* Legend */}
      <g transform={`translate(${W - 160}, 14)`}>
        {[
          { col: '#f78166', label: 'High congestion' },
          { col: '#ffa657', label: 'Med congestion' },
          { col: '#58a6ff', label: 'Optimized route' },
          { col: '#ffa657', label: 'Depot', dot: true, r: 7 },
        ].map(({ col, label, dot, r = 4 }, i) => (
          <g key={i} transform={`translate(0, ${i * 18})`}>
            {dot
              ? <circle cx={r} cy={r - 1} r={r - 1} fill={col} stroke={col} />
              : <line x1={0} y1={r} x2={14} y2={r} stroke={col} strokeWidth={dot ? 1 : 2.5} strokeDasharray={dot ? 'none' : '5 2'} />}
            <text x={18} y={r + 4} fill={t.textMuted} fontSize={9.5}>{label}</text>
          </g>
        ))}
      </g>
    </svg>
  );
});

// ── Convergence Chart ─────────────────────────────────────────────────────────
function ConvergenceChart({ data, algoKey }) {
  const t = useTokens();
  if (!data.length) {
    return <div style={{ color: t.textMuted, padding: 30, textAlign: 'center' }}>
      Run an optimization first to see the convergence curve.
    </div>;
  }
  const color = ALGO_COLORS[algoKey?.toUpperCase()] || t.accentBlue;
  return (
    <ResponsiveContainer width="100%" height={310}>
      <AreaChart data={data} margin={{ top: 8, right: 20, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="convGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%"  stopColor={color} stopOpacity={0.25} />
            <stop offset="95%" stopColor={color} stopOpacity={0.03} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={t.chartGrid} />
        <XAxis dataKey="iter" stroke={t.textMuted} tick={{ fontSize: 11 }}
               label={{ value: 'Iteration', position: 'insideBottom', offset: -2,
                        fill: t.textMuted, fontSize: 11 }} />
        <YAxis stroke={t.textMuted} tick={{ fontSize: 11 }}
               label={{ value: 'Fitness', angle: -90, position: 'insideLeft',
                        fill: t.textMuted, fontSize: 11 }} />
        <Tooltip
          contentStyle={{ background: t.tooltipBg, border: `1px solid ${t.border}`,
                          borderRadius: 8, fontSize: 12 }}
        />
        <Area type="monotone" dataKey="fitness" stroke={color} strokeWidth={2.5}
              fill="url(#convGrad)" dot={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ── Benchmark Convergence Chart ───────────────────────────────────────────────
function BenchmarkConvergenceChart({ benchmark }) {
  const t = useTokens();
  if (!benchmark) return null;
  const algos  = Object.keys(benchmark.convergence);
  const maxLen = Math.max(...algos.map(a => benchmark.convergence[a].length));
  const chartData = Array.from({ length: maxLen }, (_, i) => {
    const row = { iter: i + 1 };
    algos.forEach(a => {
      if (i < benchmark.convergence[a].length)
        row[a] = +benchmark.convergence[a][i].toFixed(4);
    });
    return row;
  });
  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 8, right: 20, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={t.chartGrid} />
        <XAxis dataKey="iter" stroke={t.textMuted} tick={{ fontSize: 11 }} />
        <YAxis stroke={t.textMuted} tick={{ fontSize: 11 }} />
        <Tooltip contentStyle={{ background: t.tooltipBg, border: `1px solid ${t.border}`,
                                  borderRadius: 8, fontSize: 12 }} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {algos.map(a => (
          <Line key={a} type="monotone" dataKey={a}
            stroke={ALGO_COLORS[a] || '#ccc'} dot={false} strokeWidth={2.2} />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

// ── Tab Bar ────────────────────────────────────────────────────────────────────
function TabBar({ tabs, active, onSelect }) {
  const t = useTokens();
  return (
    <div style={{ display: 'flex', gap: 4, marginBottom: 18 }}>
      {tabs.map(tab => (
        <button
          key={tab.id}
          onClick={() => onSelect(tab.id)}
          style={{
            background: active === tab.id ? t.btnPrimary : t.bgElevated,
            color: active === tab.id ? '#fff' : t.textMuted,
            border: `1px solid ${active === tab.id ? t.btnPrimary : t.border}`,
            borderRadius: 8,
            padding: '7px 20px',
            cursor: 'pointer',
            fontWeight: active === tab.id ? 700 : 400,
            fontSize: 13,
            transition: 'all 0.15s',
          }}
        >
          {tab.icon} {tab.label}
        </button>
      ))}
    </div>
  );
}

// ── Badge ────────────────────────────────────────────────────────────────────
function Badge({ color, children }) {
  return (
    <span style={{
      background: color + '22', color, border: `1px solid ${color}55`,
      borderRadius: 6, padding: '2px 8px', fontSize: 11, fontWeight: 600,
    }}>
      {children}
    </span>
  );
}

// ── Section Header ────────────────────────────────────────────────────────────
function SectionHeader({ children }) {
  const t = useTokens();
  return (
    <h3 style={{ fontSize: 13, color: t.textMuted, marginBottom: 14,
                 fontWeight: 600, display: 'flex', alignItems: 'center', gap: 8 }}>
      {children}
    </h3>
  );
}

// ── Main App ─────────────────────────────────────────────────────────────────
function Dashboard() {
  const t = useTokens();

  // Controls
  const [algorithm,    setAlgorithm]   = useState('qpso');
  const [nCustomers,   setNCustomers]  = useState(12);
  const [nParticles,   setNParticles]  = useState(30);
  const [maxIter,      setMaxIter]     = useState(100);
  const [vehicleType,  setVehicleType] = useState('diesel_van');
  const [capacity,     setCapacity]    = useState(100);

  // Results
  const [result,       setResult]      = useState(null);
  const [emissions,    setEmissions]   = useState(null);
  const [convergence,  setConvergence] = useState([]);
  const [benchmark,    setBenchmark]   = useState(null);

  // UI state
  const [loading,      setLoading]     = useState(false);
  const [benchLoading, setBenchLoad]   = useState(false);
  const [tab,          setTab]         = useState('map');
  const [emergency,    setEmergency]   = useState('');
  const [emergencyMsg, setEmergencyMsg]= useState('');

  // Data
  const [graphData,    setGraphData]   = useState(null);
  const [trafficFeed,  setTrafficFeed] = useState([]);
  const [trafficMap,   setTrafficMap]  = useState({});  // edge congestion map

  const wsRef = useRef(null);

  // ── Fetch graph on mount ──────────────────────────────────────────────────
  useEffect(() => {
    axios.get(`${API}/api/graph`).then(r => setGraphData(r.data)).catch(() => {});
  }, []);

  // ── Live traffic WebSocket ────────────────────────────────────────────────
  useEffect(() => {
    const connect = () => {
      const ws = new WebSocket('ws://localhost:8000/ws/traffic');
      ws.onmessage = e => {
        const msg = JSON.parse(e.data);
        if (msg.type === 'traffic_update') {
          setTrafficFeed(prev => [...msg.updates, ...prev].slice(0, 20));
          setTrafficMap(prev => {
            const next = { ...prev };
            msg.updates.forEach(u => { next[`${u.u}-${u.v}`] = u.congestion; });
            return next;
          });
        }
      };
      ws.onerror = () => {};
      wsRef.current = ws;
    };
    connect();
    return () => wsRef.current?.close();
  }, []);

  // ── Optimize ──────────────────────────────────────────────────────────────
  const handleOptimize = async () => {
    setLoading(true);
    setResult(null); setEmissions(null); setConvergence([]);
    try {
      const res = await axios.post(`${API}/api/optimize`, {
        algorithm, n_customers: nCustomers, capacity,
        n_particles: nParticles, max_iter: maxIter,
        vehicle_type: vehicleType, seed: 42,
      });
      const { job_id } = res.data;
      const [resultRes, convRes, emitRes] = await Promise.all([
        axios.get(`${API}/api/result/${job_id}`),
        axios.get(`${API}/api/convergence/${job_id}`),
        axios.get(`${API}/api/emissions/${job_id}`),
      ]);
      setResult(resultRes.data);
      setConvergence(convRes.data.history.map((v, i) => ({ iter: i + 1, fitness: +v.toFixed(4) })));
      setEmissions(emitRes.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  // ── Benchmark ─────────────────────────────────────────────────────────────
  const handleBenchmark = async () => {
    setBenchLoad(true);
    try {
      const res = await axios.get(`${API}/api/benchmark`);
      setBenchmark(res.data);
    } catch (err) { console.error(err); }
    setBenchLoad(false);
  };

  // ── Emergency ─────────────────────────────────────────────────────────────
  const handleEmergency = async () => {
    const nodes = emergency.split(',').map(s => parseInt(s.trim())).filter(Boolean);
    if (!nodes.length) return;
    try {
      await axios.post(`${API}/api/emergency`, { nodes, priority_boost: 0.1 });
      setEmergencyMsg(`✅ Emergency priority applied to nodes: ${nodes.join(', ')}`);
      setTimeout(() => setEmergencyMsg(''), 4000);
    } catch {
      setEmergencyMsg('❌ Failed to apply emergency priority');
      setTimeout(() => setEmergencyMsg(''), 4000);
    }
  };

  // ── Tabs definition ───────────────────────────────────────────────────────
  const TABS = [
    { id: 'map',         icon: '🗺️',  label: 'Network Map'   },
    { id: 'convergence', icon: '📈',  label: 'Convergence'   },
    { id: 'benchmark',   icon: '🏆',  label: 'Benchmark'     },
    { id: 'traffic',     icon: '📡',  label: 'Live Traffic'  },
  ];

  return (
    <div style={{
      minHeight: '100vh',
      background: t.bgBase,
      color: t.textPrimary,
      transition: 'background 0.25s, color 0.25s',
    }}>
      {/* ── Top Bar ──────────────────────────────────────────────────────── */}
      <header style={{
        background: t.bgSurface,
        borderBottom: `1px solid ${t.border}`,
        padding: '14px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky', top: 0, zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ fontSize: 26 }}>🚦</span>
          <div>
            <div style={{ fontSize: 17, fontWeight: 700, color: t.accentBlue }}>
              Route-OPT
            </div>
            <div style={{ fontSize: 11, color: t.textMuted }}>
              Quantum-Inspired Traffic Optimization
            </div>
          </div>
          <div style={{ display: 'flex', gap: 6, marginLeft: 12 }}>
            {['QPSO', 'QIEA', 'PSO', 'GA'].map(a => (
              <Badge key={a} color={ALGO_COLORS[a]}>{a}</Badge>
            ))}
          </div>
        </div>
        <ThemeToggle />
      </header>

      <div style={{ padding: '24px 28px', maxWidth: 1180, margin: '0 auto' }}>

        {/* ── Control Panel ─────────────────────────────────────────────── */}
        <Card style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 16,
                        color: t.textPrimary, display: 'flex', gap: 8, alignItems: 'center' }}>
            ⚙️ Simulation Controls
          </div>
          <div style={{ display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                        gap: 20, alignItems: 'end' }}>

            {/* Algorithm */}
            <div>
              <Label>Algorithm</Label>
              <Select value={algorithm} onChange={e => setAlgorithm(e.target.value)}>
                <option value="qpso">🔬 QPSO</option>
                <option value="qiea">⚡ QIEA</option>
                <option value="pso">🔵 PSO (Classical)</option>
                <option value="ga">🧬 GA (DEAP)</option>
                <option value="savings">📦 Clarke-Wright Savings</option>
              </Select>
            </div>

            {/* Vehicle */}
            <div>
              <Label>Vehicle Type</Label>
              <Select value={vehicleType} onChange={e => setVehicleType(e.target.value)}>
                <option value="diesel_van">🚐 Diesel Van</option>
                <option value="petrol_car">🚗 Petrol Car</option>
                <option value="electric">⚡ Electric</option>
                <option value="truck">🚚 Truck</option>
                <option value="motorcycle">🏍️ Motorcycle</option>
              </Select>
            </div>

            {/* Sliders */}
            <RangeField label="Customers" value={nCustomers} min={5} max={20}
                        onChange={setNCustomers} />
            <RangeField label="Population" value={nParticles} min={10} max={100} step={5}
                        onChange={setNParticles} />
            <RangeField label="Iterations" value={maxIter} min={20} max={500} step={10}
                        onChange={setMaxIter} />
            <RangeField label="Capacity" value={capacity} min={50} max={300} step={10}
                        onChange={setCapacity} />

            {/* Buttons */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <Btn onClick={handleOptimize} disabled={loading}>
                {loading ? '⏳ Running…' : '▶ Optimize'}
              </Btn>
              <Btn onClick={handleBenchmark} disabled={benchLoading} variant="outline">
                {benchLoading ? '⏳ Comparing…' : '🏆 Benchmark'}
              </Btn>
            </div>
          </div>
        </Card>

        {/* ── KPI Row ───────────────────────────────────────────────────── */}
        {result && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
            <KPICard label="Best Cost"    value={result.cost?.toFixed(3)}   unit=""          color={t.accentBlue}   />
            <KPICard label="Vehicles"     value={result.routes?.length}      unit="routes"    color={t.accentGreen}  />
            <KPICard label="Runtime"      value={result.runtime_s}           unit="s"         color={t.accentOrange} />
            {emissions && <>
              <KPICard label="CO₂ Emitted" value={emissions.total_co2_kg}      unit="kg"       color={t.accentRed}    />
              <KPICard label="Fuel Used"    value={emissions.total_fuel_litres} unit="L"        color={t.accentPurple} />
              <KPICard label="Distance"     value={emissions.total_distance_km} unit="km"       color="#79c0ff"        />
            </>}
          </div>
        )}

        {/* ── Emergency Override ────────────────────────────────────────── */}
        <Card style={{ marginBottom: 20 }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, color: t.textMuted }}>🚨 Emergency Priority</span>
            <input
              value={emergency}
              onChange={e => setEmergency(e.target.value)}
              placeholder="Node IDs, e.g. 3, 7, 12"
              style={{
                background: t.bgElevated, color: t.textPrimary,
                border: `1px solid ${t.border}`, borderRadius: 8,
                padding: '7px 12px', fontSize: 13, width: 200, outline: 'none',
              }}
            />
            <Btn onClick={handleEmergency} variant="danger">Apply Priority</Btn>
            {emergencyMsg && (
              <span style={{ fontSize: 12, color: emergencyMsg.startsWith('✅')
                              ? t.accentGreen : t.accentRed }}>
                {emergencyMsg}
              </span>
            )}
          </div>
        </Card>

        {/* ── Tabs ──────────────────────────────────────────────────────── */}
        <TabBar tabs={TABS} active={tab} onSelect={setTab} />

        {/* ── MAP TAB ───────────────────────────────────────────────────── */}
        {tab === 'map' && (
          <Card>
            <SectionHeader>
              🗺️ Network Map
              <span style={{ fontSize: 11, color: t.textMuted, fontWeight: 400 }}>
                — red edge = high congestion · dashed = optimised route · orange = depot
              </span>
            </SectionHeader>
            <NetworkSVG graphData={graphData} result={result} trafficMap={trafficMap} />

            {result?.routes && (
              <div style={{ marginTop: 18 }}>
                <SectionHeader>Route Details</SectionHeader>
                <div style={{ display: 'grid', gap: 6 }}>
                  {result.routes.map((r, i) => (
                    <div key={i} style={{
                      background: t.bgElevated, border: `1px solid ${t.border}`,
                      borderLeft: `3px solid ${ROUTE_COLORS[i % ROUTE_COLORS.length]}`,
                      borderRadius: 8, padding: '8px 14px',
                      fontSize: 12, color: ROUTE_COLORS[i % ROUTE_COLORS.length],
                      fontWeight: 600,
                    }}>
                      Vehicle {i + 1}: Depot → {r.join(' → ')} → Depot
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>
        )}

        {/* ── CONVERGENCE TAB ───────────────────────────────────────────── */}
        {tab === 'convergence' && (
          <Card>
            <SectionHeader>
              📈 Fitness vs. Iteration —&nbsp;
              <Badge color={ALGO_COLORS[algorithm?.toUpperCase()] || t.accentBlue}>
                {algorithm?.toUpperCase()}
              </Badge>
            </SectionHeader>
            <ConvergenceChart data={convergence} algoKey={algorithm} />
            {convergence.length > 0 && (
              <div style={{ marginTop: 12, fontSize: 12, color: t.textMuted, display: 'flex', gap: 20 }}>
                <span>📉 Initial: <strong style={{ color: t.textPrimary }}>{convergence[0]?.fitness}</strong></span>
                <span>🎯 Final:   <strong style={{ color: t.accentGreen }}>{convergence[convergence.length - 1]?.fitness}</strong></span>
                <span>📊 Iterations: <strong style={{ color: t.textPrimary }}>{convergence.length}</strong></span>
              </div>
            )}
          </Card>
        )}

        {/* ── BENCHMARK TAB ─────────────────────────────────────────────── */}
        {tab === 'benchmark' && (
          <Card>
            <SectionHeader>🏆 Algorithm Comparison</SectionHeader>
            {!benchmark ? (
              <div style={{ color: t.textMuted, padding: 30, textAlign: 'center' }}>
                Click <strong style={{ color: t.accentBlue }}>🏆 Benchmark</strong> in the
                control panel to compare all algorithms on the same scenario.
              </div>
            ) : (
              <>
                {/* Table */}
                <div style={{ overflowX: 'auto', marginBottom: 28 }}>
                  <table style={{
                    width: '100%', borderCollapse: 'collapse', fontSize: 13,
                  }}>
                    <thead>
                      <tr style={{ borderBottom: `2px solid ${t.border}` }}>
                        {['Algorithm', 'Best Cost', 'Mean Cost', 'Std Dev',
                          'Runtime (s)', 'Vehicles', 'Runs'].map(h => (
                          <th key={h} style={{
                            textAlign: 'left', padding: '10px 14px',
                            color: t.textMuted, fontWeight: 600, fontSize: 11,
                            textTransform: 'uppercase', letterSpacing: '0.4px',
                          }}>
                            {h}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {benchmark.summary.map((row, i) => (
                        <tr key={i} style={{
                          borderBottom: `1px solid ${t.border}`,
                          background: i === 0 ? t.accentBlue + '11' : 'transparent',
                        }}>
                          <td style={{ padding: '10px 14px' }}>
                            <span style={{
                              color: ALGO_COLORS[row.algorithm] || t.textPrimary,
                              fontWeight: 700, display: 'flex', alignItems: 'center', gap: 6,
                            }}>
                              {i === 0 && '🥇 '}{row.algorithm}
                            </span>
                          </td>
                          <td style={{ padding: '10px 14px', fontWeight: 600, color: t.textPrimary }}>
                            {row.best_cost}
                          </td>
                          <td style={{ padding: '10px 14px', color: t.textMuted }}>{row.mean_cost}</td>
                          <td style={{ padding: '10px 14px', color: t.textMuted }}>{row.std_cost}</td>
                          <td style={{ padding: '10px 14px', color: t.textMuted }}>{row.mean_runtime_s}s</td>
                          <td style={{ padding: '10px 14px', color: t.textMuted }}>{row.n_routes}</td>
                          <td style={{ padding: '10px 14px', color: t.textFaint }}>{row.n_runs}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Convergence multi-chart */}
                <SectionHeader>📈 Convergence Comparison</SectionHeader>
                <BenchmarkConvergenceChart benchmark={benchmark} />
              </>
            )}
          </Card>
        )}

        {/* ── LIVE TRAFFIC TAB ──────────────────────────────────────────── */}
        {tab === 'traffic' && (
          <Card>
            <SectionHeader>📡 Live Traffic Stream (WebSocket)</SectionHeader>
            <div style={{
              fontFamily: 'monospace', fontSize: 12, lineHeight: 1.8,
              maxHeight: 440, overflowY: 'auto',
            }}>
              {trafficFeed.length === 0 ? (
                <div style={{ color: t.textMuted, padding: 20, textAlign: 'center' }}>
                  Connecting to WebSocket… (backend must be running)
                </div>
              ) : (
                trafficFeed.map((item, i) => {
                  const cong = item.congestion;
                  const bar = '█'.repeat(Math.round(cong * 15)) +
                              '░'.repeat(15 - Math.round(cong * 15));
                  const col = cong > 0.65 ? t.accentRed
                            : cong > 0.35 ? t.accentOrange
                            : t.accentGreen;
                  return (
                    <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'center',
                                          padding: '3px 0', borderBottom: `1px solid ${t.border}` }}>
                      <span style={{ color: t.textFaint, minWidth: 50 }}>
                        Edge {item.u}→{item.v}
                      </span>
                      <span style={{ color: col, fontFamily: 'monospace', letterSpacing: '-1px' }}>
                        {bar}
                      </span>
                      <span style={{ color: col, minWidth: 40 }}>
                        {(cong * 100).toFixed(1)}%
                      </span>
                      <Badge color={col}>
                        {cong > 0.65 ? 'HIGH' : cong > 0.35 ? 'MED' : 'LOW'}
                      </Badge>
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        )}

        {/* ── Footer ────────────────────────────────────────────────────── */}
        <footer style={{
          marginTop: 36, paddingTop: 20,
          borderTop: `1px solid ${t.border}`,
          textAlign: 'center',
          fontSize: 11,
          color: t.textFaint,
        }}>
          Route-OPT v1.0.0 · QPSO · QIEA · PSO (Classical) · GA (DEAP) · Clarke-Wright Savings
          <br />
          FastAPI Backend · React Frontend · CO₂ Tracking · SUMO-Ready
          <br />
          © 2026 — Quantum-Inspired Intelligent Traffic Optimization Platform
        </footer>
      </div>
    </div>
  );
}

// ── Root export (wraps in ThemeProvider) ──────────────────────────────────────
export default function App() {
  return (
    <ThemeProvider>
      <Dashboard />
    </ThemeProvider>
  );
}

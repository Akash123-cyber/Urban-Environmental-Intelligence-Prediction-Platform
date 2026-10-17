import { useCallback, useEffect, useMemo, useState } from 'react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { api, getToken, setToken } from './api';
import Login from './Login';

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler);

const getAqiDetails = (v) => {
  if (v == null) return { label: 'N/A', color: '#6b7280', bg: 'rgba(107, 114, 128, 0.1)' };
  if (v <= 50) return { label: 'Good', color: '#10b981', bg: 'rgba(16, 185, 129, 0.1)' };
  if (v <= 100) return { label: 'Moderate', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.1)' };
  if (v <= 200) return { label: 'Poor', color: '#f97316', bg: 'rgba(249, 115, 22, 0.1)' };
  if (v <= 300) return { label: 'Very Poor', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.1)' };
  if (v <= 400) return { label: 'Severe', color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.1)' };
  return { label: 'Hazardous', color: '#b91c1c', bg: 'rgba(185, 28, 28, 0.15)' };
};

const PM25_BREAKPOINTS = [
  [0, 30, 0, 50],
  [31, 60, 51, 100],
  [61, 90, 101, 200],
  [91, 120, 201, 300],
  [121, 250, 301, 400],
  [251, 500, 401, 500],
];

const PM10_BREAKPOINTS = [
  [0, 50, 0, 50],
  [51, 100, 51, 100],
  [101, 250, 101, 200],
  [251, 350, 201, 300],
  [351, 430, 301, 400],
  [431, 600, 401, 500],
];

function calcSubIndex(val, breakpoints) {
  if (val == null || isNaN(val) || val < 0) return null;
  for (const [bpLow, bpHigh, iLow, iHigh] of breakpoints) {
    if (val >= bpLow && val <= bpHigh) {
      return Math.round(((iHigh - iLow) / (bpHigh - bpLow)) * (val - bpLow) + iLow);
    }
  }
  const last = breakpoints[breakpoints.length - 1];
  return Math.min(500, Math.round(((500 - last[2]) / (last[1] - last[0])) * (val - last[0]) + last[2]));
}

function calcCompositeAqi(pm25, pm10) {
  const i25 = calcSubIndex(pm25, PM25_BREAKPOINTS);
  const i10 = calcSubIndex(pm10, PM10_BREAKPOINTS);
  if (i25 == null && i10 == null) return null;
  return Math.max(i25 || 0, i10 || 0);
}

const formatTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
};

const num = (v, dec = 1) => (v == null ? '—' : Number(v).toFixed(dec));

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const [cities, setCities] = useState([]);
  const [cityId, setCityId] = useState(null);
  const [selectedMetric, setSelectedMetric] = useState('pm25');
  const [current, setCurrent] = useState(null);
  const [history, setHistory] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const handleUnauthorized = () => setAuthed(false);
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  useEffect(() => {
    if (!authed) return;
    api.cities()
      .then((c) => {
        setCities(c);
        if (c.length && !cityId) setCityId(c[0].id);
      })
      .catch((e) => setError(e.message));
  }, [authed]);

  const loadData = useCallback(async () => {
    if (!cityId) return;
    setLoading(true);
    try {
      const [cur, hist, fc, al] = await Promise.all([
        api.current(cityId).catch(() => null),
        api.history(cityId, 48).catch(() => []),
        api.forecast(cityId).catch(() => []),
        api.alerts().catch(() => []),
      ]);
      setCurrent(cur);
      setHistory(hist);
      setForecast(Array.isArray(fc) ? fc : (fc?.forecast || fc?.predictions || []));
      setAlerts(al);
      setError('');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [cityId]);

  const handleForceRefresh = async () => {
    if (!cityId || refreshing) return;
    setRefreshing(true);
    try {
      // 1. Force data-collector to poll live sensor data and force analytics ML inference
      await api.refreshCity(cityId).catch((err) => console.warn('Force refresh notice:', err));
      // 2. Fetch the newly updated observation readings, 48h history, and new 24h predictions
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleResolveAlert = async (id) => {
    try {
      await api.resolveAlert(id);
      setAlerts((prev) => prev.filter((a) => a.id !== id));
    } catch (e) {
      setError(e.message);
    }
  };

  const selectedCity = cities.find((c) => c.id === cityId);

  // Group cities by state for the dropdown
  const citiesByState = useMemo(() => {
    const grouped = {};
    for (const c of cities) {
      const state = c.state || 'Other';
      if (!grouped[state]) grouped[state] = [];
      grouped[state].push(c);
    }
    return grouped;
  }, [cities]);

  // Metric configuration for titles, colors, and units
  const metricMeta = useMemo(() => {
    switch (selectedMetric) {
      case 'pm10':
        return {
          title: 'PM10 Telemetry & 24-Hour Predictive Forecast',
          subtitle: 'Solid line = 48h verified actuals | Dashed line = 24h LightGBM predictive horizon',
          actualLabel: 'Historical PM10 (Actual)',
          forecastLabel: '24h ML Forecast (Predicted)',
          unit: 'µg/m³',
          unitTitle: 'Concentration (µg/m³)',
          actualColor: '#06b6d4',
          actualBg: 'rgba(6, 182, 212, 0.1)',
          forecastColor: '#f59e0b',
        };
      case 'aqi':
        return {
          title: 'Air Quality Index (AQI) & 24-Hour Predictive Trajectory',
          subtitle: 'Solid line = 48h verified AQI | Dashed line = 24h CPCB composite predicted trajectory',
          actualLabel: 'Historical AQI (Actual)',
          forecastLabel: '24h Composite Forecast (Predicted)',
          unit: 'AQI',
          unitTitle: 'Index Value (0–500)',
          actualColor: '#a855f7',
          actualBg: 'rgba(168, 85, 247, 0.1)',
          forecastColor: '#ec4899',
        };
      default:
        return {
          title: 'PM2.5 Telemetry & 24-Hour Predictive Forecast',
          subtitle: 'Solid line = 48h verified actuals | Dashed line = 24h LightGBM predictive horizon',
          actualLabel: 'Historical PM2.5 (Actual)',
          forecastLabel: '24h ML Forecast (Predicted)',
          unit: 'µg/m³',
          unitTitle: 'Concentration (µg/m³)',
          actualColor: '#3b82f6',
          actualBg: 'rgba(59, 130, 246, 0.1)',
          forecastColor: '#f97316',
        };
    }
  }, [selectedMetric]);

  // Chart configuration: 48h Actuals + Seamless Anchor + 24h Forecast
  const chartData = useMemo(() => {
    const histLabels = history.map((r) => formatTime(r.observed_at));
    const fcLabels = forecast.map((r) => formatTime(r.target_time));
    const allLabels = [...histLabels, ...fcLabels];

    let histValues, fcValues, anomalies;

    if (selectedMetric === 'pm10') {
      histValues = history.map((r) => r.pm10);
      fcValues = forecast.map((r) => r.predicted_pm10);
      anomalies = history.map((r) => (r.is_anomaly ? r.pm10 : null));
    } else if (selectedMetric === 'aqi') {
      histValues = history.map((r) => r.aqi);
      fcValues = forecast.map((r) => calcCompositeAqi(r.predicted_pm25, r.predicted_pm10));
      anomalies = history.map((r) => (r.is_anomaly ? r.aqi : null));
    } else {
      histValues = history.map((r) => r.pm25);
      fcValues = forecast.map((r) => r.predicted_pm25);
      anomalies = history.map((r) => (r.is_anomaly ? r.pm25 : null));
    }

    const lastHistVal = histValues.length > 0 ? histValues[histValues.length - 1] : null;
    const padHist = Array(Math.max(0, history.length - 1)).fill(null);
    const forecastWithAnchor = lastHistVal != null ? [lastHistVal, ...fcValues] : fcValues;
    const padFc = Array(forecast.length).fill(null);

    return {
      labels: allLabels,
      datasets: [
        {
          label: metricMeta.actualLabel,
          data: [...histValues, ...padFc],
          borderColor: metricMeta.actualColor,
          backgroundColor: metricMeta.actualBg,
          borderWidth: 2.5,
          fill: true,
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.2,
        },
        {
          label: metricMeta.forecastLabel,
          data: [...padHist, ...forecastWithAnchor],
          borderColor: metricMeta.forecastColor,
          borderWidth: 2.5,
          borderDash: [6, 4],
          fill: false,
          pointRadius: 2,
          pointHoverRadius: 5,
          tension: 0.2,
        },
        {
          label: 'Sensor Anomalies',
          data: [...anomalies, ...padFc],
          showLine: false,
          pointRadius: 6,
          pointHoverRadius: 8,
          pointBackgroundColor: '#ef4444',
          borderColor: '#ffffff',
          borderWidth: 1.5,
        },
      ],
    };
  }, [history, forecast, selectedMetric, metricMeta]);

  if (!authed) {
    return <Login onLogin={() => setAuthed(true)} />;
  }

  const aqiInfo = getAqiDetails(current?.aqi);

  return (
    <div className="dashboard-container">
      <header className="navbar">
        <div className="brand">
          <span className="brand-logo">🌿</span>
          <span className="brand-text">Urban Environmental Intelligence</span>
        </div>

        <div className="nav-controls">
          <div className="select-container">
            <label htmlFor="city-select" className="sr-only">Select City</label>
            <select
              id="city-select"
              value={cityId ?? ''}
              onChange={(e) => setCityId(Number(e.target.value))}
              className="city-select"
            >
              {Object.entries(citiesByState).map(([state, cityList]) => (
                <optgroup key={state} label={state}>
                  {cityList.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name} ({c.state})
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          <button
            onClick={() => {
              setToken(null);
              setAuthed(false);
            }}
            className="btn-secondary"
          >
            Sign Out
          </button>
        </div>
      </header>

      <main className="content">
        {error && <div className="alert-banner error">{error}</div>}

        <div className="page-header">
          <div>
            <h1>{selectedCity ? `${selectedCity.name}, ${selectedCity.state}` : 'City Overview'}</h1>
            <p className="subtitle">
              Last observation: {current?.observed_at ? formatTime(current.observed_at) : 'Awaiting data...'}
            </p>
          </div>
          <button onClick={handleForceRefresh} disabled={refreshing || loading} className="btn-refresh">
            {refreshing ? '🔄 Syncing Sensors & ML...' : loading ? 'Refreshing...' : '🔄 Refresh'}
          </button>
        </div>

        {/* Current Environmental Metrics */}
        {current && (
          <div className="kpi-grid">
            <div className="kpi-card aqi-card" style={{ borderColor: aqiInfo.color, background: aqiInfo.bg }}>
              <div className="kpi-title">Air Quality Index</div>
              <div className="kpi-value" style={{ color: aqiInfo.color }}>{current.aqi ?? '—'}</div>
              <div className="kpi-sub" style={{ color: aqiInfo.color }}>{aqiInfo.label}</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">PM2.5</div>
              <div className="kpi-value">{num(current.pm25)}</div>
              <div className="kpi-sub">µg/m³</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">PM10</div>
              <div className="kpi-value">{num(current.pm10)}</div>
              <div className="kpi-sub">µg/m³</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">NO₂</div>
              <div className="kpi-value">{num(current.no2)}</div>
              <div className="kpi-sub">µg/m³</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Temperature</div>
              <div className="kpi-value">{num(current.temperature)}°C</div>
              <div className="kpi-sub">Ambient</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Humidity</div>
              <div className="kpi-value">{num(current.humidity, 0)}%</div>
              <div className="kpi-sub">Relative</div>
            </div>

            <div className="kpi-card">
              <div className="kpi-title">Wind Speed</div>
              <div className="kpi-value">{num(current.wind_speed)}</div>
              <div className="kpi-sub">km/h</div>
            </div>
          </div>
        )}

        {/* Forecast & Timeseries Chart */}
        <div className="card panel-card">
          <div className="panel-header">
            <div>
              <h2>{metricMeta.title}</h2>
              <p className="panel-sub">{metricMeta.subtitle}</p>
            </div>

            <div className="metric-toggle-group">
              <button
                className={`metric-pill ${selectedMetric === 'pm25' ? 'active' : ''}`}
                onClick={() => setSelectedMetric('pm25')}
              >
                <span className="pill-dot" style={{ background: '#3b82f6' }}></span>
                PM2.5 (Fine Dust)
              </button>
              <button
                className={`metric-pill ${selectedMetric === 'pm10' ? 'active' : ''}`}
                onClick={() => setSelectedMetric('pm10')}
              >
                <span className="pill-dot" style={{ background: '#06b6d4' }}></span>
                PM10 (Coarse Dust)
              </button>
              <button
                className={`metric-pill ${selectedMetric === 'aqi' ? 'active' : ''}`}
                onClick={() => setSelectedMetric('aqi')}
              >
                <span className="pill-dot" style={{ background: '#a855f7' }}></span>
                Composite AQI (0–500)
              </button>
            </div>

            {forecast.length === 0 && (
              <span className="badge-warning">Model inference pending validation gate</span>
            )}
          </div>

          <div className="chart-wrapper">
            <Line
              data={chartData}
              options={{
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                  legend: {
                    position: 'top',
                    align: 'center',
                    labels: {
                      usePointStyle: true,
                      pointStyle: 'circle',
                      boxWidth: 22,
                      boxHeight: 12,
                      padding: 36,
                      color: '#cbd5e1',
                      font: {
                        size: 13,
                        weight: '500',
                      },
                    },
                  },
                  tooltip: {
                    callbacks: {
                      label: (ctx) => `${ctx.dataset.label}: ${ctx.raw != null ? num(ctx.raw) + ' ' + metricMeta.unit : '—'}`,
                    },
                  },
                },
                scales: {
                  x: { ticks: { maxTicksLimit: 12, color: '#9ca3af' }, grid: { color: 'rgba(243, 244, 246, 0.6)' } },
                  y: {
                    title: { display: true, text: metricMeta.unitTitle },
                    ticks: { color: '#9ca3af' },
                    grid: { color: 'rgba(243, 244, 246, 0.6)' },
                  },
                },
              }}
            />
          </div>
        </div>

        {/* Active Alerts Panel */}
        <div className="card panel-card">
          <div className="panel-header">
            <h2>Active Environmental Alerts ({alerts.length})</h2>
          </div>
          {alerts.length === 0 ? (
            <p className="empty-message">No active anomalies or air quality alerts. Atmospheric telemetry is nominal.</p>
          ) : (
            <div className="alerts-list">
              {alerts.map((alert) => (
                <div key={alert.id} className={`alert-item severity-${alert.severity}`}>
                  <div className="alert-meta">
                    <span className="alert-badge">{alert.severity.toUpperCase()}</span>
                    <strong>{alert.city}</strong>
                    <span className="alert-time">{formatTime(alert.created_at)}</span>
                  </div>
                  <div className="alert-msg">{alert.message}</div>
                  <button onClick={() => handleResolveAlert(alert.id)} className="btn-resolve">
                    Acknowledge
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

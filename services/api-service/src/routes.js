const express = require('express');
const db = require('./db');
const { requireRole } = require('./auth');

const router = express.Router();
const ANALYTICS_URL = process.env.ANALYTICS_URL || 'http://analytics-service:5001';
const COLLECTOR_URL = process.env.COLLECTOR_URL || 'http://data-collector:8080';

const cityId = (req, res, next) => {
  const id = Number(req.params.id);
  if (!Number.isInteger(id) || id <= 0) {
    return res.status(400).json({ error: 'invalid city id' });
  }
  req.cityId = id;
  next();
};

const clamp = (v, lo, hi, d) => Math.min(hi, Math.max(lo, Number.parseInt(v, 10) || d));
const wrap = (fn) => (req, res, next) => fn(req, res, next).catch(next);

router.post('/cities/:id/refresh', cityId, wrap(async (req, res) => {
  const { rows: cityRows } = await db.query('SELECT id, slug, name FROM cities WHERE id = $1', [req.cityId]);
  if (!cityRows[0]) return res.status(404).json({ error: 'city not found' });
  const { slug } = cityRows[0];

  let collectorResult = null;
  let analyticsResult = null;

  // 1. Force data collector to pull live sensor telemetry for this city and ingest into DB
  try {
    const colResp = await fetch(`${COLLECTOR_URL}/poll?city=${slug}&force=true&sync=true`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (colResp.ok) {
      collectorResult = await colResp.json();
    }
  } catch (err) {
    console.warn(`Collector force poll failed for ${slug}:`, err.message);
  }

  // 2. Force analytics service to run fresh ML inference based on newest telemetry
  try {
    const anaResp = await fetch(`${ANALYTICS_URL}/forecast/${slug}?hours=24&force=true`);
    if (anaResp.ok) {
      analyticsResult = await anaResp.json();
    }
  } catch (err) {
    console.warn(`Analytics force forecast failed for ${slug}:`, err.message);
  }

  res.json({
    ok: true,
    city: slug,
    collector: collectorResult,
    forecastUpdated: !!analyticsResult,
  });
}));

router.get('/cities', wrap(async (_req, res) => {
  const { rows } = await db.query(
    'SELECT id, slug, name, state, country, latitude, longitude FROM cities ORDER BY name'
  );
  res.json(rows);
}));

router.get('/cities/:id/current', cityId, wrap(async (req, res) => {
  const { rows } = await db.query(
    `SELECT c.id AS city_id, c.slug, c.name, c.state, a.observed_at,
            a.pm25, a.pm10, a.no2, a.o3, a.co, a.so2, a.aqi, a.is_anomaly,
            w.temperature, w.humidity, w.wind_speed
     FROM cities c
     JOIN air_quality_data a ON a.city_id = c.id
     LEFT JOIN weather_data w ON w.city_id = c.id AND w.observed_at = a.observed_at
     WHERE c.id = $1
     ORDER BY a.observed_at DESC LIMIT 1`,
    [req.cityId]
  );
  if (!rows[0]) return res.status(404).json({ error: 'no data for city' });
  res.json(rows[0]);
}));

router.get('/cities/:id/history', cityId, wrap(async (req, res) => {
  const hours = clamp(req.query.hours, 1, 720, 48);
  const { rows } = await db.query(
    `SELECT a.observed_at, a.pm25, a.pm10, a.no2, a.o3, a.aqi, a.is_anomaly,
            w.temperature, w.humidity, w.wind_speed
     FROM air_quality_data a
     LEFT JOIN weather_data w ON w.city_id = a.city_id AND w.observed_at = a.observed_at
     WHERE a.city_id = $1 AND a.observed_at >= now() - make_interval(hours => $2)
     ORDER BY a.observed_at`,
    [req.cityId, hours]
  );
  res.json(rows);
}));

router.get('/cities/:id/forecast', cityId, wrap(async (req, res) => {
  const force = req.query.force === 'true';
  const { rows: cityRows } = await db.query('SELECT id, slug FROM cities WHERE id = $1', [req.cityId]);
  if (!cityRows[0] || !cityRows[0].slug) {
    return res.status(404).json({ error: 'city not found' });
  }
  const slug = cityRows[0].slug;

  let cachedRows = [];
  if (!force) {
    const { rows } = await db.query(
      `SELECT target_time, predicted_pm25, predicted_pm10, model_version
       FROM predictions
       WHERE city_id = $1 AND target_time > now()
       ORDER BY target_time`,
      [req.cityId]
    );
    cachedRows = rows;
    if (cachedRows.length >= 18) return res.json(cachedRows);
  }

  // If forced or fewer than 18 hours remaining in cache, query analytics service directly
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    const r = await fetch(`${ANALYTICS_URL}/forecast/${slug}?hours=24${force ? '&force=true' : ''}`, { signal: controller.signal });
    clearTimeout(timeout);

    if (r.ok) {
      const data = await r.json();
      return res.json(data.forecast || data);
    }
  } catch (err) {
    console.warn(`Analytics fetch failed for ${slug}:`, err.message);
  }

  // Graceful fallback to existing future predictions if available
  if (cachedRows.length > 0) {
    return res.json(cachedRows);
  }

  return res.status(502).json({ error: 'analytics service unreachable or timed out' });
}));

router.get('/cities/:id/anomalies', cityId, wrap(async (req, res) => {
  const { rows } = await db.query(
    `SELECT observed_at, pm25, pm10, no2, aqi
     FROM air_quality_data
     WHERE city_id = $1 AND is_anomaly
     ORDER BY observed_at DESC LIMIT 100`,
    [req.cityId]
  );
  res.json(rows);
}));

router.get('/alerts', wrap(async (_req, res) => {
  const { rows } = await db.query(
    `SELECT al.id, c.name AS city, c.slug, al.type, al.severity, al.message, al.created_at
     FROM alerts al
     JOIN cities c ON c.id = al.city_id
     WHERE al.resolved_at IS NULL
     ORDER BY al.created_at DESC LIMIT 50`
  );
  res.json(rows);
}));

router.patch('/alerts/:id/resolve', wrap(async (req, res) => {
  const alertId = Number(req.params.id);
  const { rowCount } = await db.query(
    `UPDATE alerts SET resolved_at = now() WHERE id = $1 AND resolved_at IS NULL`,
    [alertId]
  );
  if (rowCount === 0) return res.status(404).json({ error: 'alert not found or already resolved' });
  res.json({ message: 'alert resolved', id: alertId });
}));

router.get('/admin/system', requireRole('admin'), wrap(async (_req, res) => {
  const { rows } = await db.query(
    `SELECT (SELECT count(*) FROM cities)::int AS cities,
            (SELECT count(*) FROM air_quality_data)::int AS air_rows,
            (SELECT max(observed_at) FROM air_quality_data) AS last_observation,
            (SELECT count(*) FROM alerts WHERE resolved_at IS NULL)::int AS open_alerts,
            (SELECT max(generated_at) FROM predictions) AS last_forecast`
  );
  res.json(rows[0]);
}));

router.get('/models', wrap(async (_req, res) => {
  try {
    const r = await fetch(`${ANALYTICS_URL}/models`);
    const data = await r.json();
    res.status(r.status).json(data);
  } catch (err) {
    res.status(502).json({ error: 'analytics service unreachable', details: err.message });
  }
}));

router.post('/models/reload', wrap(async (_req, res) => {
  try {
    const r = await fetch(`${ANALYTICS_URL}/models/reload`, { method: 'POST' });
    const data = await r.json();
    res.status(r.status).json(data);
  } catch (err) {
    res.status(502).json({ error: 'analytics service unreachable', details: err.message });
  }
}));

module.exports = router;

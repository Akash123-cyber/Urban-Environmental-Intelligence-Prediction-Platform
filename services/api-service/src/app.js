const express = require('express');
const helmet = require('helmet');
const cors = require('cors');
const morgan = require('morgan');
const db = require('./db');
const { client, middleware: metrics } = require('./metrics');
const { login, requireAuth } = require('./auth');
const routes = require('./routes');

const app = express();
app.disable('x-powered-by');

app.use(helmet());
app.use(cors({ origin: process.env.CORS_ORIGIN || true }));
app.use(express.json({ limit: '100kb' }));
app.use(metrics);
app.use(morgan('tiny', {
  skip: (req) => ['/health', '/ready', '/metrics', '/api/health'].includes(req.path),
}));

// Public Health & Probe Endpoints
const health = (_req, res) => res.json({ status: 'healthy', service: 'api-service', timestamp: new Date().toISOString() });
app.get('/health', health);
app.get('/api/health', health);

app.get('/ready', async (_req, res) => {
  try {
    await db.query('SELECT 1');
    res.json({ status: 'ready', database: 'connected' });
  } catch (err) {
    res.status(503).json({ status: 'db unavailable', error: err.message });
  }
});

app.get('/metrics', async (_req, res) => {
  res.set('Content-Type', client.register.contentType);
  res.end(await client.register.metrics());
});

// Authentication Routes
app.post('/api/auth/login', (req, res, next) => login(req, res).catch(next));

// Public Model Registry & Hot-Reload Webhooks (for Colab / Offline ML triggers)
const ANALYTICS_URL = process.env.ANALYTICS_URL || 'http://analytics-service:5001';
app.get(['/models', '/api/models'], async (_req, res) => {
  try {
    const r = await fetch(`${ANALYTICS_URL}/models`);
    const data = await r.json();
    res.status(r.status).json(data);
  } catch (err) {
    res.status(502).json({ error: 'analytics service unreachable', details: err.message });
  }
});
app.post(['/models/reload', '/api/models/reload'], async (_req, res) => {
  try {
    const r = await fetch(`${ANALYTICS_URL}/models/reload`, { method: 'POST' });
    const data = await r.json();
    res.status(r.status).json(data);
  } catch (err) {
    res.status(502).json({ error: 'analytics service unreachable', details: err.message });
  }
});

// Protected API Routes
app.use('/api', requireAuth, routes);

// Error Handling
app.use((_req, res) => res.status(404).json({ error: 'not found' }));
app.use((err, _req, res, _next) => {
  console.error(err);
  res.status(500).json({ error: 'internal server error' });
});

module.exports = app;

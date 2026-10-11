const client = require('prom-client');

client.collectDefaultMetrics();

const labelNames = ['method', 'route', 'status'];
const requests = new client.Counter({
  name: 'http_requests_total',
  help: 'HTTP requests total count',
  labelNames,
});
const duration = new client.Histogram({
  name: 'http_request_duration_seconds',
  help: 'HTTP request latency',
  labelNames,
  buckets: [0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5],
});

function middleware(req, res, next) {
  const stop = duration.startTimer();
  res.on('finish', () => {
    const route = req.route ? (req.baseUrl || '') + req.route.path : 'unmatched';
    const labels = {
      method: req.method,
      route,
      status: `${Math.floor(res.statusCode / 100)}xx`,
    };
    requests.inc(labels);
    stop(labels);
  });
  next();
}

module.exports = { client, middleware };

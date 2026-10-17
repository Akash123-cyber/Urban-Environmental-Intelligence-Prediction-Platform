const assert = require('assert');
const { describe, it, before, after } = require('node:test');
const app = require('../src/app');

describe('API Service Basic Smoke Tests', () => {
  let server;
  let port;

  before((_, done) => {
    server = app.listen(0, () => {
      port = server.address().port;
      done();
    });
  });

  after((_, done) => {
    server.close(done);
  });

  it('GET /api/health should return 200', async () => {
    const res = await fetch(`http://127.0.0.1:${port}/api/health`);
    assert.strictEqual(res.status, 200);
    const body = await res.json();
    assert.strictEqual(body.status, 'healthy');
  });

  it('GET /api/cities without token should return 401', async () => {
    const res = await fetch(`http://127.0.0.1:${port}/api/cities`);
    assert.strictEqual(res.status, 401);
  });

  it('GET /unknown-route should return 404', async () => {
    const res = await fetch(`http://127.0.0.1:${port}/random-404-route`);
    assert.strictEqual(res.status, 404);
  });

  it('POST /api/auth/register with missing fields should return 400', async () => {
    const res = await fetch(`http://127.0.0.1:${port}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'test@example.com' }),
    });
    assert.strictEqual(res.status, 400);
    const body = await res.json();
    assert.strictEqual(body.error, 'email and password required');
  });

  it('POST /api/auth/register with short password should return 400', async () => {
    const res = await fetch(`http://127.0.0.1:${port}/api/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: 'test@example.com', password: '123' }),
    });
    assert.strictEqual(res.status, 400);
    const body = await res.json();
    assert.strictEqual(body.error, 'password must be at least 6 characters');
  });
});

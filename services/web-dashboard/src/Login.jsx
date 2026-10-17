import { useState } from 'react';
import { api, setToken } from './api';

export default function Login({ onLogin }) {
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('TLX5oxHjvMniTHfe2P2wBNMv');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { token } = await api.login(email, password);
      setToken(token);
      onLogin();
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrapper">
      <div className="login-card">
        <div className="login-header">
          <div className="logo-badge">🌿 Urban EIPP</div>
          <h2>Environmental Intelligence</h2>
          <p>Real-time telemetry, anomaly detection & ML forecasts</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="alert-banner error">{error}</div>}

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
            />
          </div>

          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Authenticating...' : 'Sign In to Dashboard'}
          </button>
        </form>

        <div className="login-footer">
          <small>Default seeded admin: <code>admin@example.com</code></small>
        </div>
      </div>
    </div>
  );
}

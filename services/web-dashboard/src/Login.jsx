import { useState } from 'react';
import { api, setToken } from './api';

export default function Login({ onLogin }) {
  const [mode, setMode] = useState('login'); // 'login' or 'signup'
  const [email, setEmail] = useState('admin@example.com');
  const [password, setPassword] = useState('TLX5oxHjvMniTHfe2P2wBNMv');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const switchMode = (newMode) => {
    setMode(newMode);
    setError('');
    if (newMode === 'signup') {
      setEmail('');
      setPassword('');
      setConfirmPassword('');
    } else {
      setEmail('admin@example.com');
      setPassword('TLX5oxHjvMniTHfe2P2wBNMv');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (mode === 'signup') {
      if (password.length < 6) {
        setError('Password must be at least 6 characters');
        return;
      }
      if (password !== confirmPassword) {
        setError('Passwords do not match');
        return;
      }
    }

    setLoading(true);
    try {
      let res;
      if (mode === 'signup') {
        res = await api.register(email, password);
      } else {
        res = await api.login(email, password);
      }
      if (res && res.token) {
        setToken(res.token);
        onLogin();
      } else {
        throw new Error('Authentication response did not return a session token');
      }
    } catch (err) {
      setError(err.message || (mode === 'signup' ? 'Registration failed' : 'Authentication failed'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-wrapper">
      <div className="login-card">
        <div className="login-header">
          <div className="logo-badge">🌿 Urban EIPP</div>
          <h2>{mode === 'signup' ? 'Create an Account' : 'Environmental Intelligence'}</h2>
          <p>{mode === 'signup' ? 'Sign up to access live urban air quality intelligence' : 'Real-time telemetry, anomaly detection & ML forecasts'}</p>
        </div>

        <div className="auth-tabs" style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '0.5rem' }}>
          <button
            type="button"
            onClick={() => switchMode('login')}
            style={{
              flex: 1,
              padding: '0.6rem',
              background: mode === 'login' ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
              color: mode === 'login' ? '#60a5fa' : '#94a3b8',
              border: mode === 'login' ? '1px solid rgba(59, 130, 246, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.9rem',
              transition: 'all 0.2s',
            }}
          >
            Sign In
          </button>
          <button
            type="button"
            onClick={() => switchMode('signup')}
            style={{
              flex: 1,
              padding: '0.6rem',
              background: mode === 'signup' ? 'rgba(59, 130, 246, 0.2)' : 'transparent',
              color: mode === 'signup' ? '#60a5fa' : '#94a3b8',
              border: mode === 'signup' ? '1px solid rgba(59, 130, 246, 0.4)' : '1px solid transparent',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '0.9rem',
              transition: 'all 0.2s',
            }}
          >
            Sign Up
          </button>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          {error && <div className="alert-banner error">{error}</div>}

          <div className="form-group">
            <label htmlFor="email">Email Address</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="user@example.com"
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password {mode === 'signup' && <small style={{ color: '#94a3b8' }}>(min 6 chars)</small>}</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
            />
          </div>

          {mode === 'signup' && (
            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm Password</label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••••"
                required
              />
            </div>
          )}

          <button type="submit" disabled={loading} className="btn-primary" style={{ marginTop: '0.5rem' }}>
            {loading
              ? (mode === 'signup' ? 'Creating Account...' : 'Authenticating...')
              : (mode === 'signup' ? 'Create Account & Sign In' : 'Sign In to Dashboard')}
          </button>
        </form>

        <div className="login-footer">
          {mode === 'login' ? (
            <div>
              <p style={{ fontSize: '0.85rem', marginBottom: '0.5rem' }}>
                Don't have an account?{' '}
                <a
                  href="#signup"
                  onClick={(e) => { e.preventDefault(); switchMode('signup'); }}
                  style={{ color: '#60a5fa', textDecoration: 'none', fontWeight: 600 }}
                >
                  Create one now
                </a>
              </p>
              <small style={{ color: '#64748b' }}>Default admin: <code>admin@example.com</code></small>
            </div>
          ) : (
            <p style={{ fontSize: '0.85rem' }}>
              Already registered?{' '}
              <a
                href="#signin"
                onClick={(e) => { e.preventDefault(); switchMode('login'); }}
                style={{ color: '#60a5fa', textDecoration: 'none', fontWeight: 600 }}
              >
                Sign In
              </a>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

const BASE = import.meta.env.VITE_API_BASE || '/api';

export const getToken = () => sessionStorage.getItem('token');
export const setToken = (t) => (t ? sessionStorage.setItem('token', t) : sessionStorage.removeItem('token'));

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    setToken(null);
    window.dispatchEvent(new Event('auth:unauthorized'));
  }

  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.error || `HTTP error ${res.status}`);
  }

  return res.json();
}

export const api = {
  login: (email, password) =>
    request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  cities: () => request('/cities'),
  current: (id) => request(`/cities/${id}/current`),
  history: (id, hours = 48) => request(`/cities/${id}/history?hours=${hours}`),
  forecast: (id) => request(`/cities/${id}/forecast`),
  anomalies: (id) => request(`/cities/${id}/anomalies`),
  alerts: () => request('/alerts'),
  resolveAlert: (id) => request(`/alerts/${id}/resolve`, { method: 'PATCH' }),
  systemMetrics: () => request('/admin/system'),
};

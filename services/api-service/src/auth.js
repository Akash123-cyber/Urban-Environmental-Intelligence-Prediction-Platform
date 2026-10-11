const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');
const db = require('./db');

const secret = () => process.env.JWT_SECRET || 'dev-only-secret-key-32-chars-minimum';

async function seedAdmin() {
  const { ADMIN_EMAIL, ADMIN_PASSWORD } = process.env;
  if (!ADMIN_EMAIL || !ADMIN_PASSWORD) return;
  const hash = await bcrypt.hash(ADMIN_PASSWORD, 10);
  await db.query(
    `INSERT INTO users (email, password_hash, role) VALUES ($1, $2, 'admin')
     ON CONFLICT (email) DO NOTHING`,
    [ADMIN_EMAIL.toLowerCase(), hash]
  );
}

async function login(req, res) {
  const { email, password } = req.body || {};
  if (!email || !password) {
    return res.status(400).json({ error: 'email and password required' });
  }
  const { rows } = await db.query(
    'SELECT id, email, password_hash, role FROM users WHERE email = $1',
    [email.toLowerCase()]
  );
  const user = rows[0];
  if (!user || !(await bcrypt.compare(password, user.password_hash))) {
    return res.status(401).json({ error: 'invalid credentials' });
  }
  const token = jwt.sign(
    { sub: user.id, email: user.email, role: user.role },
    secret(),
    { expiresIn: '8h' }
  );
  res.json({ token, user: { email: user.email, role: user.role } });
}

function requireAuth(req, res, next) {
  const h = req.headers.authorization || '';
  const token = h.startsWith('Bearer ') ? h.slice(7) : null;
  if (!token) return res.status(401).json({ error: 'missing token' });
  try {
    req.user = jwt.verify(token, secret());
    next();
  } catch {
    res.status(401).json({ error: 'invalid or expired token' });
  }
}

const requireRole = (role) => (req, res, next) => {
  if (req.user && req.user.role === role) {
    next();
  } else {
    res.status(403).json({ error: 'forbidden' });
  }
};

module.exports = { seedAdmin, login, requireAuth, requireRole };

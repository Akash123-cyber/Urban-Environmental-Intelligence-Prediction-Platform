const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL || 'postgresql://urban:urban_dev_password@localhost:5432/urban',
  max: 10,
  idleTimeoutMillis: 30000,
});

pool.on('error', (err) => console.error('pg pool error:', err.message));

module.exports = {
  query: (text, params) => pool.query(text, params),
  pool,
};

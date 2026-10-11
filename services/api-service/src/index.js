const app = require('./app');
const db = require('./db');
const { seedAdmin } = require('./auth');

const port = Number(process.env.PORT || 3000);

(async () => {
  try {
    await seedAdmin();
    console.log('Initial admin user check/seed completed.');
  } catch (err) {
    console.error('Admin seed skipped or failed:', err.message);
  }

  const server = app.listen(port, () => {
    console.log(`api-service listening on port ${port}`);
  });

  const shutdown = () => {
    console.log('Received termination signal. Closing HTTP server and DB pool...');
    server.close(() => {
      db.pool.end().then(() => {
        console.log('Database pool drained. Exiting cleanly.');
        process.exit(0);
      });
    });
    setTimeout(() => {
      console.error('Forcefully exiting after timeout.');
      process.exit(1);
    }, 10000).unref();
  };

  process.on('SIGTERM', shutdown);
  process.on('SIGINT', shutdown);
})();

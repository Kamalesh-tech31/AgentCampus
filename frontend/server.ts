import express from 'express';
import path from 'path';
import { createServer as createViteServer } from 'vite';
import { runOrchestrationPipeline } from './server/orchestrator';
import { dbInstance } from './src/data/mockCampusDb';

async function startServer() {
  const app = express();
  const PORT = 3000;

  app.use(express.json());

  // API Routes
  app.get('/api/health', (req, res) => {
    res.json({ status: 'ok', service: 'AgentCampus Multi-Agent Engine' });
  });

  // Get current student dataset
  app.get('/api/students', (req, res) => {
    const students = dbInstance.getAllStudents();
    res.json({
      count: students.length,
      students
    });
  });

  // Reset database back to seed
  app.post('/api/students/reset', (req, res) => {
    dbInstance.reset();
    res.json({
      success: true,
      message: 'Campus student database reset to default initial state',
      count: dbInstance.getAllStudents().length
    });
  });

  // Main SSE Orchestration Pipeline
  app.post('/api/orchestrate/stream', async (req, res) => {
    const { prompt } = req.body;

    if (!prompt || typeof prompt !== 'string' || !prompt.trim()) {
      res.status(400).json({ error: 'Missing or invalid "prompt" string' });
      return;
    }

    // Set headers for Server-Sent Events (SSE)
    res.setHeader('Content-Type', 'text/event-stream');
    res.setHeader('Cache-Control', 'no-cache, no-transform');
    res.setHeader('Connection', 'keep-alive');
    res.setHeader('X-Accel-Buffering', 'no');

    await runOrchestrationPipeline(prompt.trim(), res);
  });

  // Vite middleware in development or static serve in production
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa'
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`AgentCampus server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();

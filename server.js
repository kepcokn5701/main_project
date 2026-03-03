const express = require('express');
const path = require('path');
const fs = require('fs');
const dotenv = require('dotenv');

// load environment variables from .env
dotenv.config();

const app = express();
app.use(express.json());

// serve frontend static files
app.use(express.static(path.join(__dirname, 'frontend', 'public')));

// serve modules (simulation scripts)
app.use('/modules', express.static(path.join(__dirname, 'modules')));

// simple in-memory store for API keys provided by user
const userKeys = {};

// example API: returns project metadata by module
app.get('/api/projects', (req, res) => {
  // the metadata could be aggregated from package folders, but for now
  // we return a static list or load from JSON files in packages.
  // to keep it simple, read from packages/*/index.js if present.
  const packagesDir = path.join(__dirname, 'packages');
  let list = [];
  if (fs.existsSync(packagesDir)) {
    fs.readdirSync(packagesDir).forEach(dir => {
      const pkgPath = path.join(packagesDir, dir, 'index.js');
      if (fs.existsSync(pkgPath)) {
        try {
          const mod = require(pkgPath);
          list.push(mod.metadata || mod);
        } catch (e) {
          console.error('failed to load package', pkgPath, e);
        }
      }
    });
  }
  // fallback: if list empty, send sample
  if (list.length === 0) {
    list = [{ id: 1, sim: 'cs', title: '고객경험관리(CS) 분석', subtitle: 'AI 기반 설문 자동 분석 시스템', problem:'…', solution:'…', stack: [] }];
  }

  res.json(list);
});

// endpoint to store API keys/config
app.post('/api/keys', (req, res) => {
  const { service, key } = req.body;
  if (!service || !key) return res.status(400).json({ error: 'service and key required' });
  userKeys[service] = key;
  res.json({ status: 'ok' });
});

// CS analysis routes
const csRoutes = require('./routes/cs-analysis');
app.use('/api/cs', csRoutes);

// simple HuggingFace LLM test route
app.get('/api/test-hf', async (req, res) => {
  const prompt = req.query.prompt || 'Hello from HuggingFace';
  const hfKey = process.env.HUGGINGFACE_API_KEY || userKeys['huggingface'];
  if (!hfKey) return res.status(400).json({ error: 'HuggingFace API key not set' });
  try {
    const r = await fetch('https://router.huggingface.co/v1/chat/completions', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${hfKey}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        model: 'Qwen/Qwen3.5-35B-A3B',
        messages: [{ role: 'user', content: prompt }],
        max_tokens: 512
      })
    });
    const text = await r.text();
    let json;
    try {
      json = JSON.parse(text);
    } catch {
      return res.status(502).json({ error: 'Invalid response from HuggingFace', details: text });
    }
    res.json(json);
  } catch (e) {
    console.error('HF test failed', e);
    res.status(500).json({ error: 'request failed', details: e.message });
  }
});

// serve root for SPA
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'frontend', 'public', 'index.html'));
});

const port = process.env.PORT || 3000;
app.listen(port, () => console.log(`Server listening on ${port}`));

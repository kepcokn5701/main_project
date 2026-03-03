const express = require('express');
const router = express.Router();
const multer = require('multer');
const { parse } = require('csv-parse/sync');
const { runPipeline } = require('../utils/analysis-pipeline');

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024 } });

// In-memory store
const store = {};

function genId() {
  return Math.random().toString(36).slice(2, 10);
}

// POST /api/cs/upload — Upload CSV and start analysis
router.post('/upload', upload.single('csvFile'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'CSV 파일이 필요합니다' });

  let rows;
  try {
    const csvContent = req.file.buffer.toString('utf-8');
    rows = parse(csvContent, {
      columns: true,
      skip_empty_lines: true,
      trim: true,
      bom: true
    });
  } catch (e) {
    return res.status(400).json({ error: 'CSV 파싱 실패', details: e.message });
  }

  const required = ['customer_id', 'customer_name', 'region', 'inquiry_type', 'survey_date', 'rating', 'comment'];
  const columns = Object.keys(rows[0] || {});
  const missing = required.filter(c => !columns.includes(c));
  if (missing.length > 0) {
    return res.status(400).json({ error: `필수 컬럼 누락: ${missing.join(', ')}` });
  }

  if (rows.length === 0) {
    return res.status(400).json({ error: '데이터가 없습니다' });
  }

  const analysisId = genId();
  store[analysisId] = {
    status: 'processing',
    rawData: rows,
    results: null,
    progress: { phase: 'queued', percent: 0, message: '분석 대기 중...' },
    sseClients: [],
    createdAt: Date.now()
  };

  // Start analysis in background
  runPipeline(rows, (progress) => {
    store[analysisId].progress = progress;
    // Broadcast to SSE clients
    store[analysisId].sseClients.forEach(client => {
      const event = progress.phase === 'complete' ? 'complete' : 'progress';
      client.write(`event: ${event}\ndata: ${JSON.stringify(progress)}\n\n`);
    });
  }).then(results => {
    store[analysisId].status = 'complete';
    store[analysisId].results = results;
    // Close SSE connections
    store[analysisId].sseClients.forEach(client => {
      try { client.end(); } catch {}
    });
    store[analysisId].sseClients = [];
  }).catch(err => {
    console.error('Pipeline error:', err);
    store[analysisId].status = 'error';
    store[analysisId].progress = { phase: 'error', percent: 0, message: `분석 실패: ${err.message}` };
    store[analysisId].sseClients.forEach(client => {
      client.write(`event: error\ndata: ${JSON.stringify({ error: err.message })}\n\n`);
      try { client.end(); } catch {}
    });
    store[analysisId].sseClients = [];
  });

  res.json({
    analysisId,
    totalRows: rows.length,
    status: 'processing',
    message: '분석이 시작되었습니다'
  });
});

// GET /api/cs/progress/:id — SSE progress stream
router.get('/progress/:id', (req, res) => {
  const entry = store[req.params.id];
  if (!entry) return res.status(404).json({ error: '분석을 찾을 수 없습니다' });

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');
  res.flushHeaders();

  // Send current progress immediately
  const event = entry.progress.phase === 'complete' ? 'complete' : 'progress';
  res.write(`event: ${event}\ndata: ${JSON.stringify(entry.progress)}\n\n`);

  if (entry.status === 'complete') {
    res.write(`event: complete\ndata: ${JSON.stringify({ phase: 'complete', percent: 100, message: '분석 완료!' })}\n\n`);
    return res.end();
  }

  if (entry.status === 'error') {
    res.write(`event: error\ndata: ${JSON.stringify({ error: entry.progress.message })}\n\n`);
    return res.end();
  }

  entry.sseClients.push(res);

  req.on('close', () => {
    entry.sseClients = entry.sseClients.filter(c => c !== res);
  });
});

// GET /api/cs/results/:id — Get analysis results
router.get('/results/:id', (req, res) => {
  const entry = store[req.params.id];
  if (!entry) return res.status(404).json({ error: '분석을 찾을 수 없습니다' });
  if (entry.status === 'processing') return res.json({ status: 'processing', progress: entry.progress });
  if (entry.status === 'error') return res.status(500).json({ status: 'error', message: entry.progress.message });

  res.json({
    analysisId: req.params.id,
    status: 'complete',
    ...entry.results
  });
});

// GET /api/cs/export/:id — Export as CSV download
router.get('/export/:id', (req, res) => {
  const entry = store[req.params.id];
  if (!entry || !entry.results) return res.status(404).json({ error: '분석 결과가 없습니다' });

  const customers = entry.results.customers;
  const header = '고객ID,이름,지역,감성점수,위험등급,문의유형,설문일자,감성분류';
  const csvRows = customers.map(c =>
    `${c.id},${c.name},${c.region},${c.score},${c.risk},${c.inquiry},${c.date},${c.sentiment}`
  );
  const csv = '\uFEFF' + header + '\n' + csvRows.join('\n');

  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename=CS_분석_리포트.csv');
  res.send(csv);
});

module.exports = router;

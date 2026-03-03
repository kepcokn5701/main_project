const express = require('express');
const router = express.Router();
const multer = require('multer');
const { parse } = require('csv-parse/sync');
const XLSX = require('xlsx');
const { runPipeline } = require('../utils/analysis-pipeline');

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 50 * 1024 * 1024 } });

// In-memory store
const store = {};

function genId() {
  return Math.random().toString(36).slice(2, 10);
}

// POST /api/cs/upload — Upload CSV/Excel and start analysis
router.post('/upload', upload.single('csvFile'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: '파일이 필요합니다 (CSV, XLSX, XLS)' });

  const ext = (req.file.originalname || '').split('.').pop().toLowerCase();
  let rows;

  try {
    if (ext === 'xlsx' || ext === 'xls') {
      // Excel parsing
      const workbook = XLSX.read(req.file.buffer, { type: 'buffer' });
      const sheetName = workbook.SheetNames[0];
      const sheet = workbook.Sheets[sheetName];
      rows = XLSX.utils.sheet_to_json(sheet, { defval: '' });
      // Trim all string values and normalize column names (fix non-breaking spaces)
      rows = rows.map(row => {
        const cleaned = {};
        Object.entries(row).forEach(([key, val]) => {
          const k = String(key).replace(/[\u00A0\u3000\uFEFF\u200B]/g, ' ').replace(/\s+/g, ' ').trim();
          cleaned[k] = typeof val === 'string' ? val.trim() : String(val);
        });
        return cleaned;
      });
    } else {
      // CSV parsing (default)
      const csvContent = req.file.buffer.toString('utf-8');
      rows = parse(csvContent, {
        columns: true,
        skip_empty_lines: true,
        trim: true,
        bom: true
      });
    }
  } catch (e) {
    return res.status(400).json({ error: '파일 파싱 실패', details: e.message });
  }

  if (!rows || rows.length === 0) {
    return res.status(400).json({ error: '데이터가 없습니다' });
  }

  // Korean → English column name mapping (supports various header variants)
  const KO_TO_EN = {
    '지사': 'branch',
    '계약종별': 'contract_type', '게약종별': 'contract_type',
    '접수종류': 'receipt_type',
    '업무구분': 'task_type', '업무 구분': 'task_type',
    '신청방법': 'apply_method', '신청 방법': 'apply_method',
    '접수자구분': 'receiver_type', '접수자 구분': 'receiver_type',
    // convenience
    '이용편리성': 'convenience', '이용 편리성': 'convenience',
    '이용편리': 'convenience', '이용 편리': 'convenience',
    // kindness
    '직원친절도': 'kindness', '직원 친절도': 'kindness',
    '직원친절성': 'kindness', '직원 친절성': 'kindness',
    '직원친절': 'kindness', '직원 친절': 'kindness',
    // overall_satisfaction
    '전반적만족': 'overall_satisfaction', '전반적 만족': 'overall_satisfaction',
    '전반적만족도': 'overall_satisfaction', '전반적 만족도': 'overall_satisfaction',
    '전반만족': 'overall_satisfaction', '전반 만족': 'overall_satisfaction',
    // social_responsibility
    '사회적책임': 'social_responsibility', '사회적 책임': 'social_responsibility',
    '사회책임': 'social_responsibility', '사회 책임': 'social_responsibility',
    // speed
    '처리신속도': 'speed', '처리 신속도': 'speed',
    '처리신속': 'speed', '처리 신속': 'speed',
    // accuracy
    '처리정확도': 'accuracy', '처리 정확도': 'accuracy',
    '처리정확': 'accuracy', '처리 정확': 'accuracy',
    '업무정확도': 'accuracy', '업무 정확도': 'accuracy',
    '업무정확': 'accuracy', '업무 정확': 'accuracy',
    // improvement
    '업무개선도': 'improvement', '업무 개선도': 'improvement',
    '업무개선': 'improvement', '업무 개선': 'improvement',
    '사후추적': 'improvement', '사후 추적': 'improvement',
    // recommendation
    '사용추천도': 'recommendation', '사용 추천도': 'recommendation',
    '사용추천': 'recommendation', '사용 추천': 'recommendation',
    // total_score
    '종합점수': 'total_score', '종합 점수': 'total_score',
    '종합': 'total_score',
    // opinion
    '서술의견': 'opinion', '서술 의견': 'opinion',
    '의견': 'opinion',
    // survey_date
    '설문일자': 'survey_date', '조사일자': 'survey_date', '조사일': 'survey_date', '날짜': 'survey_date', '일자': 'survey_date',
    // ignored columns (mapped but not required)
    '순번': '_id', '번호': '_id', 'No': '_id', 'no': '_id',
  };

  // Auto-map Korean column names to English if needed
  const firstRowKeys = Object.keys(rows[0] || {});
  const needsMapping = firstRowKeys.some(k => KO_TO_EN[k]);
  if (needsMapping) {
    rows = rows.map(row => {
      const mapped = {};
      Object.entries(row).forEach(([key, val]) => {
        const engKey = KO_TO_EN[key] || key;
        mapped[engKey] = val;
      });
      return mapped;
    });
  }

  const required = ['branch', 'contract_type', 'receipt_type', 'task_type', 'apply_method', 'receiver_type', 'convenience', 'kindness', 'overall_satisfaction', 'social_responsibility', 'speed', 'accuracy', 'improvement', 'recommendation', 'total_score', 'opinion'];
  const columns = Object.keys(rows[0] || {});
  const missing = required.filter(c => !columns.includes(c));
  if (missing.length > 0) {
    // Build diagnostic info: show detected headers and which ones mapped/unmapped
    const originalHeaders = Object.keys(rows[0] || {});
    const mappedHeaders = originalHeaders.filter(k => KO_TO_EN[k]).map(k => `${k} → ${KO_TO_EN[k]}`);
    const unmappedHeaders = originalHeaders.filter(k => !KO_TO_EN[k] && !required.includes(k));
    return res.status(400).json({
      error: `필수 컬럼 누락: ${missing.join(', ')}`,
      debug: {
        detectedHeaders: originalHeaders,
        mappedHeaders,
        unmappedHeaders,
        needsMapping,
        totalRows: rows.length,
      }
    });
  }

  // Data quality warnings
  const warnings = [];
  const hasDateCol = columns.includes('survey_date');
  if (!hasDateCol) {
    warnings.push('survey_date 컬럼 없음: 월별 트렌드 분석이 비활성화됩니다.');
  } else {
    const datePattern = /^\d{4}[-/]\d{2}[-/]\d{2}/;
    const dateCount = rows.filter(r => datePattern.test(r.survey_date || '')).length;
    if (dateCount === 0) {
      warnings.push('survey_date가 날짜 형식이 아닙니다(순번 등): 월별 트렌드가 표시되지 않습니다.');
    } else if (dateCount < rows.length * 0.5) {
      warnings.push(`survey_date 중 ${rows.length - dateCount}건이 날짜 형식이 아닙니다. 해당 건은 월별 트렌드에서 제외됩니다.`);
    }
  }

  const emptyOpinion = rows.filter(r => !r.opinion || r.opinion.trim() === '' || r.opinion.trim() === '-').length;
  if (emptyOpinion > rows.length * 0.5) {
    warnings.push(`서술 의견이 ${emptyOpinion}건(${Math.round(emptyOpinion/rows.length*100)}%) 비어있습니다. 감성분석 정확도가 낮아질 수 있습니다.`);
  }

  const scoreFields = ['convenience','kindness','overall_satisfaction','social_responsibility','speed','accuracy','improvement','recommendation','total_score'];
  scoreFields.forEach(f => {
    const invalid = rows.filter(r => {
      const v = r[f];
      if (!v || v === '-') return false;
      return isNaN(parseFloat(v));
    }).length;
    if (invalid > 0) {
      warnings.push(`${f} 컬럼에 숫자가 아닌 값 ${invalid}건 감지. 해당 값은 '-'(미입력)으로 처리됩니다.`);
    }
  });

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
    message: '분석이 시작되었습니다',
    warnings
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

  const surveys = entry.results.customers;
  const header = '지사,계약종별,접수종류,업무구분,신청방법,접수자구분,이용편리성,직원친절도,전반적만족,사회적책임,처리신속도,처리정확도,업무개선도,사용추천도,종합점수,서술의견,감성분류';
  const csvRows = surveys.map(c =>
    `${c.branch},${c.contractType},${c.receiptType},${c.taskType},${c.applyMethod},${c.receiverType},${c.convenience},${c.kindness},${c.overallSatisfaction},${c.socialResponsibility},${c.speed},${c.accuracy},${c.improvement},${c.recommendation},${c.totalScore},"${(c.opinion||'').replace(/"/g,'""')}",${c.sentiment}`
  );
  const csv = '\uFEFF' + header + '\n' + csvRows.join('\n');

  res.setHeader('Content-Type', 'text/csv; charset=utf-8');
  res.setHeader('Content-Disposition', 'attachment; filename=CS_분석_리포트.csv');
  res.send(csv);
});

module.exports = router;

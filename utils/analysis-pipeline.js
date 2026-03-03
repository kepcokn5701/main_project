const { callLLM, sleep } = require('./llm');

const BATCH_SIZE = 10;
const MAX_SAMPLES = 200;

async function runPipeline(rows, onProgress) {
  const emit = (phase, percent, message, extra = {}) => {
    if (onProgress) onProgress({ phase, percent, message, ...extra });
  };

  // Phase 1: Validation
  emit('validation', 5, `데이터 검증 중... (${rows.length}건)`);
  const totalRows = rows.length;

  // Determine sample for LLM analysis
  let samplesToAnalyze = rows;
  let isSampled = false;
  if (totalRows > MAX_SAMPLES) {
    samplesToAnalyze = stratifiedSample(rows, MAX_SAMPLES);
    isSampled = true;
  }
  emit('validation', 10, `데이터 검증 완료 (${totalRows}건${isSampled ? `, ${samplesToAnalyze.length}건 샘플링` : ''})`);

  // Phase 2: Sentiment Analysis
  const sentimentResults = [];
  const batches = [];
  for (let i = 0; i < samplesToAnalyze.length; i += BATCH_SIZE) {
    batches.push(samplesToAnalyze.slice(i, i + BATCH_SIZE));
  }

  for (let bi = 0; bi < batches.length; bi++) {
    const batch = batches[bi];
    const processed = Math.min((bi + 1) * BATCH_SIZE, samplesToAnalyze.length);
    const percent = 10 + Math.round((processed / samplesToAnalyze.length) * 55);
    emit('sentiment', percent, `감성분석 수행 중... (${processed}/${samplesToAnalyze.length})`, { processed, total: samplesToAnalyze.length });

    try {
      const results = await analyzeSentimentBatch(batch, bi);
      sentimentResults.push(...results);
    } catch (e) {
      console.error(`Batch ${bi} failed:`, e.message);
      // Fallback: assign neutral sentiment
      batch.forEach((row, idx) => {
        sentimentResults.push({
          id: bi * BATCH_SIZE + idx + 1,
          sentiment: guessSentimentFromRating(row.total_score),
          score: ratingToScore(row.total_score),
          keywords: []
        });
      });
    }

    if (bi < batches.length - 1) await sleep(500);
  }

  // Map sentiment results back to rows
  for (let i = 0; i < samplesToAnalyze.length; i++) {
    const sr = sentimentResults[i] || { sentiment: 'neutral', score: 50, keywords: [] };
    samplesToAnalyze[i]._sentiment = sr.sentiment;
    samplesToAnalyze[i]._score = sr.score;
    samplesToAnalyze[i]._keywords = sr.keywords || [];
  }

  // If sampled, apply sentiment ratios to all rows
  if (isSampled) {
    const dist = calcSentimentDist(samplesToAnalyze);
    rows.forEach(row => {
      if (!row._sentiment) {
        row._sentiment = guessSentimentFromRating(row.total_score);
        row._score = ratingToScore(row.total_score);
        row._keywords = [];
      }
    });
  }

  emit('sentiment', 65, `감성분석 완료 (${samplesToAnalyze.length}건 분석)`);

  // Phase 3: Keyword Extraction
  emit('keywords', 70, '키워드 추출 중...');
  const allKeywords = {};
  samplesToAnalyze.forEach(row => {
    (row._keywords || []).forEach(kw => {
      if (!allKeywords[kw]) allKeywords[kw] = { count: 0, sentiments: [] };
      allKeywords[kw].count++;
      allKeywords[kw].sentiments.push(row._sentiment);
    });
  });

  let keywords;
  try {
    keywords = await extractKeywords(allKeywords);
  } catch (e) {
    console.error('Keyword extraction failed:', e.message);
    keywords = fallbackKeywords(allKeywords);
  }
  emit('keywords', 80, '키워드 추출 완료');

  // Phase 4: Statistics
  emit('statistics', 85, '통계 생성 중...');
  const dataSource = isSampled ? samplesToAnalyze : rows;
  const summary = buildSummary(dataSource, totalRows);
  const monthlyTrend = buildMonthlyTrend(dataSource);
  const customers = buildCustomerList(dataSource);
  emit('statistics', 88, '통계 생성 완료');

  // Phase 5: Insights
  emit('insights', 90, 'AI 인사이트 도출 중...');
  let insights;
  try {
    insights = await generateInsights(summary, monthlyTrend, keywords, customers);
  } catch (e) {
    console.error('Insight generation failed:', e.message);
    insights = fallbackInsights(summary);
  }
  emit('insights', 95, 'AI 인사이트 도출 완료');

  const results = { summary, monthlyTrend, keywords, insights, customers };
  emit('complete', 100, '분석 완료!');
  return results;
}

async function analyzeSentimentBatch(batch, batchIndex) {
  const system = `You are a Korean customer service sentiment analyzer. You MUST respond with ONLY a valid JSON array. No explanation, no markdown, no code fences.`;

  const comments = batch.map((row, i) => {
    const text = (row.opinion && row.opinion.trim() !== '' && row.opinion.trim() !== '-') ? row.opinion : '(의견 없음)';
    return `[${i + 1}] ${text}`;
  }).join('\n');

  const user = `Analyze each Korean survey comment. For each, return sentiment ("positive","neutral","negative"), score (0-100, 0=most negative), and 1-3 Korean keyword phrases.

Survey comments:
${comments}

Respond with ONLY this JSON format:
[{"id":1,"sentiment":"negative","score":15,"keywords":["키워드1","키워드2"]},{"id":2,"sentiment":"positive","score":85,"keywords":["키워드1"]}]`;

  const result = await callLLM(system, user, 200 * batch.length);
  if (!Array.isArray(result)) throw new Error('Expected array from LLM');
  return result;
}

async function extractKeywords(keywordMap) {
  const entries = Object.entries(keywordMap)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 50);

  if (entries.length === 0) return [];

  const system = `You are a Korean text analysis expert. Respond with ONLY a valid JSON array. No explanation.`;

  const kwList = entries.map(([text, data]) => {
    const dominant = mode(data.sentiments);
    return `${text}: ${data.count}회 (${dominant})`;
  }).join('\n');

  const user = `Below are keywords from Korean customer surveys with frequency and dominant sentiment.
Consolidate similar keywords and return the top 15 ranked by importance.

Raw keywords:
${kwList}

Return JSON array: [{"text":"키워드","count":38,"sentiment":"negative"},...]`;

  const result = await callLLM(system, user, 1500);
  if (!Array.isArray(result)) throw new Error('Expected array');
  return result.slice(0, 15);
}

async function generateInsights(summary, monthlyTrend, keywords, customers) {
  const system = `You are a Korean customer experience (CX) analytics expert. Respond with ONLY a valid JSON array. No explanation, no markdown.`;

  const highRisk = customers.filter(c => c.risk === 'high').length;
  const negKw = keywords.filter(k => k.sentiment === 'negative').slice(0, 3).map(k => `"${k.text}" (${k.count}건)`).join(', ');
  const posKw = keywords.filter(k => k.sentiment === 'positive').slice(0, 3).map(k => `"${k.text}" (${k.count}건)`).join(', ');

  const monthSummary = monthlyTrend.map(m => `${m.month}: 긍정 ${m.pos}%, 중립 ${m.neu}%, 부정 ${m.neg}%`).join('\n');

  const user = `Based on customer survey analysis, generate exactly 5 strategic insights in Korean.

Analysis Summary:
- 총 설문 수: ${summary.totalSurveys}건
- 긍정: ${summary.positivePercent}%, 중립: ${summary.neutralPercent}%, 부정: ${summary.negativePercent}%
- 평균 만족도: ${summary.avgSatisfaction}/10.0
- 고위험 고객 수: ${highRisk}명
- 주요 부정 키워드: ${negKw || '없음'}
- 주요 긍정 키워드: ${posKw || '없음'}

Monthly breakdown:
${monthSummary}

For each insight provide:
- icon: one of "alert-triangle","trending-up","clock","users","zap"
- iconColor: hex color (#f87171=warning, #22c55e=positive, #fb923c=caution, #a78bfa=users, #fbbf24=prediction)
- title: short Korean title (under 20 chars)
- text: detailed Korean analysis (2-3 sentences, use <strong> with color classes like text-orange-400, text-green-400, text-sky-400, text-red-400 for emphasis)
- trend: "up" or "down"
- trendColor: hex color
- trendText: short Korean label (e.g. "주의 필요", "긍정 상승")

Return JSON: [{"icon":"...","iconColor":"...","title":"...","text":"...","trend":"...","trendColor":"...","trendText":"..."},...]`;

  const result = await callLLM(system, user, 3000);
  if (!Array.isArray(result)) throw new Error('Expected array');
  return result.slice(0, 5);
}

// --- Helper functions ---

function isDateFormat(val) {
  return /^\d{4}[-/]\d{2}[-/]\d{2}/.test(val || '');
}

function stratifiedSample(rows, n) {
  // Check if survey_date exists and contains actual dates
  const hasDates = rows.some(r => isDateFormat(r.survey_date));

  if (hasDates) {
    // Stratify by month
    const byMonth = {};
    rows.forEach(r => {
      const m = isDateFormat(r.survey_date) ? r.survey_date.slice(0, 7) : 'unknown';
      if (!byMonth[m]) byMonth[m] = [];
      byMonth[m].push(r);
    });
    const months = Object.keys(byMonth).sort();
    const perMonth = Math.ceil(n / months.length);
    const sampled = [];
    months.forEach(m => {
      const pool = byMonth[m];
      const shuffled = pool.sort(() => Math.random() - 0.5);
      sampled.push(...shuffled.slice(0, perMonth));
    });
    return sampled.slice(0, n);
  } else {
    // No dates: random sample
    const shuffled = [...rows].sort(() => Math.random() - 0.5);
    return shuffled.slice(0, n);
  }
}

function parseScore(val) {
  const n = parseFloat(val);
  return isNaN(n) ? null : n;
}

function guessSentimentFromRating(totalScore) {
  const r = parseScore(totalScore);
  if (r === null) return 'neutral';
  if (r >= 7) return 'positive';
  if (r <= 4) return 'negative';
  return 'neutral';
}

function ratingToScore(totalScore) {
  const r = parseScore(totalScore);
  if (r === null) return 50;
  return Math.min(100, Math.max(0, Math.round((r - 1) * (100 / 9))));
}

function calcSentimentDist(rows) {
  const total = rows.length;
  const pos = rows.filter(r => r._sentiment === 'positive').length;
  const neg = rows.filter(r => r._sentiment === 'negative').length;
  const neu = total - pos - neg;
  return {
    positive: Math.round((pos / total) * 100),
    neutral: Math.round((neu / total) * 100),
    negative: Math.round((neg / total) * 100)
  };
}

function buildSummary(rows, totalCount) {
  const dist = calcSentimentDist(rows);
  const scores = rows.map(r => parseScore(r.total_score)).filter(s => s !== null);
  const avgScore = scores.length > 0 ? scores.reduce((a, b) => a + b, 0) / scores.length : 5;

  return {
    totalSurveys: totalCount,
    positivePercent: dist.positive,
    neutralPercent: dist.neutral,
    negativePercent: dist.negative,
    avgSatisfaction: Math.round(avgScore * 10) / 10
  };
}

function buildMonthlyTrend(rows) {
  const byMonth = {};
  rows.forEach(r => {
    if (!isDateFormat(r.survey_date)) return;
    const d = r.survey_date || '';
    const monthNum = parseInt(d.slice(5, 7)) || 0;
    if (monthNum < 1 || monthNum > 12) return;
    if (!byMonth[monthNum]) byMonth[monthNum] = [];
    byMonth[monthNum].push(r);
  });

  const months = ['1월','2월','3월','4월','5월','6월','7월','8월','9월','10월','11월','12월'];
  return months.map((name, i) => {
    const m = i + 1;
    const mRows = byMonth[m] || [];
    if (mRows.length === 0) return { month: name, pos: 0, neu: 0, neg: 0, count: 0 };
    const dist = calcSentimentDist(mRows);
    return { month: name, pos: dist.positive, neu: dist.neutral, neg: dist.negative, count: mRows.length };
  });
}

function buildCustomerList(rows) {
  return rows.map(r => {
    const ts = parseScore(r.total_score);
    let risk;
    if (ts === null || ts <= 4) risk = 'high';
    else if (ts <= 6) risk = 'mid';
    else risk = 'low';

    return {
      branch: r.branch || '',
      contractType: r.contract_type || '',
      receiptType: r.receipt_type || '',
      taskType: r.task_type || '',
      applyMethod: r.apply_method || '',
      receiverType: r.receiver_type || '',
      convenience: r.convenience || '-',
      kindness: r.kindness || '-',
      overallSatisfaction: r.overall_satisfaction || '-',
      socialResponsibility: r.social_responsibility || '-',
      speed: r.speed || '-',
      accuracy: r.accuracy || '-',
      improvement: r.improvement || '-',
      recommendation: r.recommendation || '-',
      totalScore: r.total_score || '-',
      opinion: r.opinion || '',
      sentiment: r._sentiment || guessSentimentFromRating(r.total_score),
      risk
    };
  }).sort((a, b) => {
    const sa = parseScore(a.totalScore) ?? 99;
    const sb = parseScore(b.totalScore) ?? 99;
    return sa - sb;
  });
}

function mode(arr) {
  const freq = {};
  arr.forEach(v => { freq[v] = (freq[v] || 0) + 1; });
  let maxVal = '', maxCount = 0;
  Object.entries(freq).forEach(([v, c]) => {
    if (c > maxCount) { maxCount = c; maxVal = v; }
  });
  return maxVal;
}

function fallbackKeywords(keywordMap) {
  return Object.entries(keywordMap)
    .sort((a, b) => b[1].count - a[1].count)
    .slice(0, 15)
    .map(([text, data]) => ({
      text,
      count: data.count,
      sentiment: mode(data.sentiments) || 'neutral'
    }));
}

function fallbackInsights(summary) {
  return [
    { icon: 'alert-triangle', iconColor: '#f87171', title: '부정 감성 분석', text: `전체 설문 중 <strong class="text-red-400">${summary.negativePercent}%</strong>가 부정 감성으로 분류되었습니다. 주요 원인 파악이 필요합니다.`, trend: 'up', trendColor: '#f87171', trendText: '주의 필요' },
    { icon: 'trending-up', iconColor: '#22c55e', title: '긍정 감성 현황', text: `긍정 감성 비율이 <strong class="text-green-400">${summary.positivePercent}%</strong>로 나타났습니다. 긍정적인 고객 경험을 유지하는 것이 중요합니다.`, trend: 'up', trendColor: '#22c55e', trendText: '긍정 유지' },
    { icon: 'clock', iconColor: '#fb923c', title: '처리 시간 분석', text: '고객 문의 처리 속도가 만족도에 큰 영향을 미치고 있습니다. 빠른 응대가 필요합니다.', trend: 'down', trendColor: '#fb923c', trendText: '개선 필요' },
    { icon: 'users', iconColor: '#a78bfa', title: '고위험 고객 관리', text: '고위험 고객에 대한 선제적 케어 프로그램 운영이 권장됩니다.', trend: 'up', trendColor: '#f87171', trendText: '관리 강화' },
    { icon: 'zap', iconColor: '#fbbf24', title: '예측 인사이트', text: `평균 만족도 <strong class="text-sky-400">${summary.avgSatisfaction}</strong>점을 바탕으로 개선 전략 수립이 필요합니다.`, trend: 'up', trendColor: '#fbbf24', trendText: '전략 수립' }
  ];
}

module.exports = { runPipeline };

const dotenv = require('dotenv');
dotenv.config();

const HF_URL = 'https://router.huggingface.co/v1/chat/completions';
const MODEL = 'Qwen/Qwen3.5-35B-A3B';

async function callLLM(systemPrompt, userPrompt, maxTokens = 2048) {
  const hfKey = process.env.HUGGINGFACE_API_KEY;
  if (!hfKey) throw new Error('HUGGINGFACE_API_KEY not set');

  let lastError;
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const r = await fetch(HF_URL, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${hfKey}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          model: MODEL,
          messages: [
            { role: 'system', content: systemPrompt },
            { role: 'user', content: userPrompt }
          ],
          max_tokens: maxTokens,
          temperature: 0.3
        })
      });

      if (r.status === 429) {
        const wait = Math.pow(3, attempt + 1) * 1000;
        await sleep(wait);
        continue;
      }

      const text = await r.text();
      let body;
      try { body = JSON.parse(text); } catch {
        throw new Error(`HF returned non-JSON: ${text.slice(0, 200)}`);
      }

      if (body.error) throw new Error(`HF API error: ${body.error}`);

      const content = body.choices?.[0]?.message?.content;
      if (!content) throw new Error('Empty LLM response');

      return extractJSON(content);
    } catch (e) {
      lastError = e;
      if (attempt < 2) await sleep(Math.pow(2, attempt) * 1000);
    }
  }
  throw lastError;
}

function extractJSON(text) {
  // Remove <think>...</think> blocks (Qwen reasoning)
  text = text.replace(/<think>[\s\S]*?<\/think>/g, '').trim();

  // Try direct parse
  try { return JSON.parse(text); } catch {}

  // Try extracting from markdown code fence
  const fenceMatch = text.match(/```(?:json)?\s*([\s\S]*?)```/);
  if (fenceMatch) {
    try { return JSON.parse(fenceMatch[1].trim()); } catch {}
  }

  // Try finding first [ or {
  const arrStart = text.indexOf('[');
  const objStart = text.indexOf('{');
  let start = -1;
  if (arrStart >= 0 && objStart >= 0) start = Math.min(arrStart, objStart);
  else if (arrStart >= 0) start = arrStart;
  else if (objStart >= 0) start = objStart;

  if (start >= 0) {
    const isArray = text[start] === '[';
    const closer = isArray ? ']' : '}';
    let depth = 0;
    for (let i = start; i < text.length; i++) {
      if (text[i] === text[start]) depth++;
      else if (text[i] === closer) depth--;
      if (depth === 0) {
        try { return JSON.parse(text.slice(start, i + 1)); } catch { break; }
      }
    }
  }

  throw new Error(`Failed to extract JSON from LLM response: ${text.slice(0, 300)}`);
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

module.exports = { callLLM, sleep };

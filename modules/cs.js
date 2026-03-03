// simulation module for CS project
export function start(el) {
  const keywords = ['불편함','요금 문의','친절한 응대','처리 지연','고압적 태도','신속 해결','민원 접수','개선 요청','만족도 높음','재방문 의향'];
  const sentiments = [{l:'긍정',pct:65,c:'#22c55e'},{l:'중립',pct:23,c:'#94a3b8'},{l:'부정',pct:12,c:'#ef4444'}];
  el.innerHTML = `
    <div class="p-2 space-y-4">
      <div class="flex items-center gap-2 text-xs text-slate-400 mb-2">
        <span class="spinner"></span> 설문 데이터 52,341건 분석 중...
      </div>
      <div class="grid grid-cols-3 gap-2 mb-4">
        ${sentiments.map(s=>`
          <div class="p-3 rounded-xl text-center" style="background:rgba(15,23,42,.8);border:1px solid rgba(148,163,184,.1);">
            <div class="text-xl font-bold counter" data-target="${s.pct}" data-color="${s.c}" style="color:${s.c}">0%</div>
            <div class="text-xs text-slate-400 mt-1">${s.l}</div>
          </div>`).join('')}
      </div>
      ${sentiments.map(s=>`
        <div class="flex items-center gap-3">
          <div class="text-xs text-slate-300 w-10">${s.l}</div>
          <div class="flex-1 h-3 rounded-full overflow-hidden" style="background:#1e293b;">
            <div class="h-full rounded-full bar-anim" style="width:0;background:${s.c};transition:width 1.5s ease-out;" data-w="${s.pct}%"></div>
          </div>
          <div class="text-xs font-bold w-8" style="color:${s.c}">${s.pct}%</div>
        </div>`).join('')}
      <div class="mt-4 p-3 rounded-xl" style="background:rgba(239,68,68,.08);border:1px solid rgba(239,68,68,.25);">
        <div class="text-xs font-bold text-red-400 mb-1">⚠ 잠재 민원 케어 대상 127명 자동 분류</div>
        <div class="text-xs text-slate-400">고위험 42명 · 중위험 85명 → 사전 케어 콜 예정</div>
      </div>
      <div class="text-xs text-slate-400 uppercase tracking-wider font-semibold mt-3 mb-2">추출 키워드</div>
      <div id="kw-area" class="flex flex-wrap gap-1.5"></div>
    </div>`;

  // Count up animation
  setTimeout(() => {
    el.querySelectorAll('.bar-anim').forEach(b => { b.style.width = b.dataset.w; });
    el.querySelectorAll('.counter').forEach(c => {
      let cur = 0, target = parseInt(c.dataset.target);
      const iv = setInterval(() => {
        cur = Math.min(cur + 2, target);
        c.textContent = cur + '%';
        if (cur >= target) clearInterval(iv);
      }, 30);
      simTimers.push(iv);
    });

    const kwArea = document.getElementById('kw-area');
    keywords.forEach((k, i) => {
      const t = setTimeout(() => {
        const span = document.createElement('span');
        span.className = 'text-xs px-2 py-1 rounded-full';
        const sizes = ['text-xs','text-sm','text-base'];
        span.style.cssText = `background:rgba(56,189,248,.1);border:1px solid rgba(56,189,248,.2);color:#7dd3fc;animation:fadeIn .4s ease-out;font-size:${11+Math.floor(Math.random()*4)}px`;
        span.textContent = k;
        kwArea.appendChild(span);
      }, i * 180);
      simTimers.push(t);
    });
  }, 300);
}

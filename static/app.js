// JEV Project Analyzer - dashboard frontend
(() => {
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  const state = {
    analysis: null,
    filter: 'all',
  };

  const recColors = {
    'AGORA': { bg: 'bg-emerald-500/15', text: 'text-emerald-300', border: 'border-emerald-500/30', solid: '#10b981' },
    'DEPOIS': { bg: 'bg-amber-500/15', text: 'text-amber-300', border: 'border-amber-500/30', solid: '#f59e0b' },
    'NÃO USAR': { bg: 'bg-red-500/15', text: 'text-red-300', border: 'border-red-500/30', solid: '#ef4444' },
  };

  function recBadge(rec) {
    const c = recColors[rec] || recColors['DEPOIS'];
    return `<span class="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ${c.bg} ${c.text} border ${c.border}">
      <span class="w-1.5 h-1.5 rounded-full" style="background:${c.solid}"></span>${rec}
    </span>`;
  }

  function scoreColor(score) {
    if (score >= 7.5) return '#10b981';
    if (score >= 5) return '#f59e0b';
    return '#ef4444';
  }

  function showError(msg) {
    const box = $('#errorBox');
    box.textContent = msg;
    box.classList.remove('hidden');
  }
  function clearError() {
    $('#errorBox').classList.add('hidden');
  }
  function setLoading(on, msg) {
    const box = $('#loadingBox');
    if (on) {
      box.classList.remove('hidden');
      $('#loadingText').textContent = msg || 'Analisando projeto…';
    } else {
      box.classList.add('hidden');
    }
  }

  async function analyze(source) {
    clearError();
    setLoading(true, 'Lendo projeto e detectando stack…');
    try {
      const r = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ source }),
      });
      if (!r.ok) {
        const j = await r.json().catch(() => ({}));
        throw new Error(j.detail || `Erro ${r.status}`);
      }
      const { analysis_id } = await r.json();
      setLoading(true, 'Construindo relatório e avaliando oportunidades…');
      const ar = await fetch(`/api/analysis/${analysis_id}`);
      if (!ar.ok) throw new Error('Falha ao carregar análise');
      state.analysis = await ar.json();
      state.analysisId = analysis_id;
      renderDashboard();
    } catch (e) {
      showError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function renderDashboard() {
    $('#inputSection').classList.add('hidden');
    const d = $('#dashboard');
    d.classList.remove('hidden');
    d.innerHTML = '';

    const a = state.analysis;
    const c = a.counts;

    // ---- Header / Overview ----
    const overview = document.createElement('section');
    overview.className = 'fade-in';
    overview.innerHTML = `
      <div class="flex items-start justify-between flex-wrap gap-4 mb-4">
        <div>
          <div class="flex items-center gap-2">
            <h2 class="text-3xl font-extrabold tracking-tight">${escapeHtml(a.project_name)}</h2>
            ${recBadge('AGORA').replace('AGORA', c.agora + ' AGORA').replace('bg-emerald-500/15', 'bg-emerald-500/10')}
          </div>
          <p class="text-slate-400 text-sm mt-1">
            <span class="mono text-xs text-slate-500">${escapeHtml(a.source_type.toUpperCase())} • ${escapeHtml(a.source_path)}</span>
          </p>
          <p class="text-slate-300 text-sm mt-3 max-w-3xl leading-relaxed">${escapeHtml(a.architecture_summary)}</p>
        </div>
        <button id="restartBtn" class="btn rounded-lg bg-white/5 hover:bg-white/10 text-slate-200 text-sm px-4 py-2 h-fit">← Analisar outro projeto</button>
      </div>

      <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3 mt-6">
        ${statCard('Fluxos analisados', c.flows_analyzed, '🧭')}
        ${statCard('AGORA', c.agora, '✅', 'text-emerald-300')}
        ${statCard('DEPOIS', c.depois, '⏳', 'text-amber-300')}
        ${statCard('NÃO USAR', c.nao_usar, '⛔', 'text-red-300')}
        ${statCard('Stack', (c.stack.frameworks?.[0] || c.stack.languages?.[0] || '—'), '🧱', 'text-sky-300', true)}
      </div>
    `;
    d.appendChild(overview);

    $('#restartBtn').addEventListener('click', () => {
      d.classList.add('hidden');
      $('#inputSection').classList.remove('hidden');
      $('#sourceInput').value = '';
      state.analysis = null;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });

    // ---- Stack chips ----
    const stackSection = document.createElement('section');
    stackSection.className = 'card rounded-2xl p-6 fade-in';
    const stackChips = renderStackChips(c.stack);
    stackSection.innerHTML = `
      <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Stack detectada</h3>
      ${stackChips}
      ${a.warnings?.length ? `
        <div class="mt-4 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-200 text-xs px-4 py-3 space-y-1">
          ${a.warnings.map(w => `<div>⚠️ ${escapeHtml(w)}</div>`).join('')}
        </div>` : ''}
    `;
    d.appendChild(stackSection);

    // ---- Architecture diagram ----
    const archSection = document.createElement('section');
    archSection.className = 'card rounded-2xl p-6 fade-in';
    archSection.innerHTML = `
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wider">Arquitetura atual × pontos de JEV</h3>
        <span class="text-xs text-slate-500">Representação simplificada inferida da análise estática</span>
      </div>
      <div id="archDiagram" class="w-full overflow-x-auto"></div>
      <p class="text-xs text-slate-500 mt-3">
        🔵 Nós em azul indicam os pontos onde uma camada JEV de decisão probabilística poderia ser inserida,
        sem alterar o restante da arquitetura.
      </p>
    `;
    d.appendChild(archSection);
    renderArch(archSection.querySelector('#archDiagram'), a.architecture_nodes, a.architecture_edges);

    // ---- Impact x complexity matrix ----
    const matrixSection = document.createElement('section');
    matrixSection.className = 'card rounded-2xl p-6 fade-in';
    matrixSection.innerHTML = `
      <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
        <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wider">Matriz Impacto × Complexidade</h3>
        <div class="text-xs text-slate-500">Canto superior esquerdo = quick wins</div>
      </div>
      <div class="relative">
        <canvas id="matrixChart" height="320"></canvas>
      </div>
    `;
    d.appendChild(matrixSection);
    renderMatrix(matrixSection.querySelector('#matrixChart'), a.opportunities);

    // ---- Filters + cards ----
    const cardsSection = document.createElement('section');
    cardsSection.className = 'fade-in';
    cardsSection.innerHTML = `
      <div class="flex items-center justify-between mb-4 flex-wrap gap-3">
        <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wider">Oportunidades JEV</h3>
        <div class="flex gap-2 text-xs">
          ${filterBtn('all', 'Todos', true)}
          ${filterBtn('AGORA', 'AGORA')}
          ${filterBtn('DEPOIS', 'DEPOIS')}
          ${filterBtn('NÃO USAR', 'NÃO USAR')}
        </div>
      </div>
      <div id="cardsGrid" class="grid md:grid-cols-2 gap-4"></div>
    `;
    d.appendChild(cardsSection);
    renderCards();

    cardsSection.querySelectorAll('.filter-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        state.filter = btn.dataset.filter;
        cardsSection.querySelectorAll('.filter-btn').forEach(b => {
          b.classList.remove('bg-sky-500', 'text-ink-950');
          b.classList.add('bg-white/5', 'text-slate-300');
        });
        btn.classList.add('bg-sky-500', 'text-ink-950');
        btn.classList.remove('bg-white/5', 'text-slate-300');
        renderCards();
      });
    });

    // ---- Detected flows (raw) ----
    if (a.flows?.length) {
      const flowsSection = document.createElement('section');
      flowsSection.className = 'card rounded-2xl p-6 fade-in';
      flowsSection.innerHTML = `
        <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-4">Fluxos detectados (evidências)</h3>
        <div class="grid md:grid-cols-2 gap-3">
          ${a.flows.map(f => `
            <div class="rounded-xl bg-ink-900/60 border border-white/5 p-4">
              <div class="flex items-center justify-between mb-1">
                <div class="font-semibold text-slate-100 text-sm">${escapeHtml(f.name)}</div>
                <div class="text-xs text-slate-500 mono">confiança ${Math.round(f.confidence*100)}%</div>
              </div>
              <div class="text-xs text-slate-400 mb-2">${escapeHtml(f.description)}</div>
              <div class="text-xs text-slate-500 mono space-y-1 max-h-28 overflow-auto scrollbar">
                ${f.evidence.slice(0,3).map(e => `<div>→ ${escapeHtml(e)}</div>`).join('')}
              </div>
            </div>
          `).join('')}
        </div>
      `;
      d.appendChild(flowsSection);
    }

    // ---- Limitations ----
    const lim = document.createElement('section');
    lim.className = 'card rounded-2xl p-6 fade-in';
    lim.innerHTML = `
      <h3 class="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">Limitações desta análise</h3>
      <ul class="text-xs text-slate-400 space-y-1 list-disc list-inside">
        ${a.limitations.map(l => `<li>${escapeHtml(l)}</li>`).join('')}
      </ul>
    `;
    d.appendChild(lim);
  }

  function statCard(label, value, icon, extraClass='', isText=false) {
    return `
      <div class="card rounded-xl p-4">
        <div class="flex items-center justify-between">
          <div class="text-xs text-slate-400 uppercase tracking-wider">${escapeHtml(label)}</div>
          <div class="text-lg">${icon}</div>
        </div>
        <div class="mt-2 ${isText ? 'text-lg' : 'text-3xl font-extrabold'} ${extraClass || 'text-slate-100'} truncate" title="${escapeHtml(String(value))}">${escapeHtml(String(value))}</div>
      </div>
    `;
  }

  function renderStackChips(stack) {
    const groups = [
      ['Linguagens', stack.languages],
      ['Frameworks', stack.frameworks],
      ['Bancos/Caches', stack.databases],
      ['Infra', stack.infrastructures],
      ['Pacotes', stack.package_managers],
      ['Serviços/Auth', stack.services],
    ];
    return groups.filter(([,arr]) => arr && arr.length).map(([name, arr]) => `
      <div class="mb-3 last:mb-0">
        <div class="text-xs text-slate-500 mb-1.5">${name}</div>
        <div class="flex flex-wrap gap-1.5">
          ${arr.slice(0,12).map(x => `<span class="chip rounded-md px-2 py-1 text-xs bg-ink-900 text-slate-300">${escapeHtml(x)}</span>`).join('')}
        </div>
      </div>
    `).join('');
  }

  function renderArch(container, nodes, edges) {
    // Lightweight SVG auto-layout: arrange by kind into columns, then rows.
    const kindOrder = ['client', 'frontend', 'backend', 'jev', 'queue', 'database', 'external'];
    const columns = {};
    nodes.forEach(n => {
      const k = kindOrder.indexOf(n.kind) >=0 ? n.kind : 'external';
      columns[k] = columns[k] || [];
      columns[k].push(n);
    });

    const colKeys = kindOrder.filter(k => columns[k]);
    const colW = 240, rowH = 110, marginX = 40, marginY = 30;
    const width = Math.max(720, colKeys.length * colW + marginX*2);

    const positions = {};
    let maxRows = 0;
    colKeys.forEach((k, ci) => {
      const colNodes = columns[k];
      maxRows = Math.max(maxRows, colNodes.length);
      colNodes.forEach((n, ri) => {
        positions[n.id] = {
          x: marginX + ci * colW + colW/2,
          y: marginY + ri * rowH + 50,
          node: n,
        };
      });
    });
    const height = marginY + maxRows * rowH + 60;

    const edgeColor = (e) => e.dashed ? '#38bdf8' : '#3b4468';
    const edgeDash = (e) => e.dashed ? '6,5' : null;

    // Curved path between columns
    function pathBetween(a, b) {
      const dx = b.x - a.x;
      const c1x = a.x + dx/2;
      const c2x = a.x + dx/2;
      return `M ${a.x} ${a.y} C ${c1x} ${a.y}, ${c2x} ${b.y}, ${b.x} ${b.y}`;
    }

    let svg = `<svg viewBox="0 0 ${width} ${height}" class="w-full min-w-[700px]">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#3b4468" />
        </marker>
        <marker id="arrowBlue" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#38bdf8" />
        </marker>
      </defs>
    `;

    // Edges first
    edges.forEach(e => {
      const a = positions[e.from], b = positions[e.to];
      if (!a || !b) return;
      const dash = edgeDash(e);
      const color = edgeColor(e);
      const marker = e.dashed ? 'url(#arrowBlue)' : 'url(#arrow)';
      svg += `<path d="${pathBetween(a,b)}" stroke="${color}" stroke-width="1.6" fill="none" ${dash ? `stroke-dasharray="${dash}"` : ''} marker-end="${marker}" />`;
      if (e.label) {
        const mx = (a.x+b.x)/2, my=(a.y+b.y)/2;
        svg += `<text x="${mx}" y="${my-6}" text-anchor="middle" fill="#7dd3fc" font-size="11" font-family="Inter">${escapeHtml(e.label)}</text>`;
      }
    });

    // Nodes
    Object.values(positions).forEach(p => {
      const n = p.node;
      const isJev = n.jev_here;
      const fill = isJev ? 'rgba(56,189,248,0.15)' : 'rgba(22,26,46,0.9)';
      const stroke = isJev ? '#38bdf8' : 'rgba(255,255,255,0.12)';
      const glowClass = isJev ? 'jev-glow' : '';
      const w = n.label.length > 26 ? 220 : 180;
      const x = p.x - w/2, y = p.y - 28;
      svg += `
        <g class="${glowClass}">
          <rect x="${x}" y="${y}" rx="12" ry="12" width="${w}" height="56" fill="${fill}" stroke="${stroke}" stroke-width="${isJev?2:1}" />
          <text x="${p.x}" y="${p.y-6}" text-anchor="middle" fill="${isJev ? '#e0f2fe' : '#cbd5e1'}" font-size="12" font-weight="600" font-family="Inter">${escapeHtml(n.label)}</text>
          <text x="${p.x}" y="${p.y+12}" text-anchor="middle" fill="${isJev ? '#7dd3fc' : '#64748b'}" font-size="10" font-family="Inter" font-style="italic">${isJev ? 'decision layer' : n.kind}</text>
        </g>`;
    });

    svg += `</svg>`;
    container.innerHTML = svg;
  }

  function renderMatrix(canvas, opps) {
    // Map recommendation -> complexity/impact proxy.
    // We need numerical complexity & impact for axes. We'll derive from utility_score and implementation_complexity word.
    const complexityValue = (c) => {
      const map = {'Baixa':1, 'Média':2, 'Alta':3, '—':2};
      return map[c] || 2;
    };
    // Impact proxy: from score; higher score => higher impact but we also nudge AGORA points.
    const data = opps.map((o, i) => ({
      x: complexityValue(o.implementation_complexity) + (Math.random()-0.5)*0.15,
      y: o.utility_score,
      label: shortLabel(o.use_case),
      rec: o.recommendation,
      i,
      r: 8 + Math.min(12, o.utility_score/2),
    }));

    const ctx = canvas.getContext('2d');
    if (matrixChart) matrixChart.destroy();
    matrixChart = new Chart(ctx, {
      type: 'bubble',
      data: {
        datasets: [{
          label: 'Oportunidades',
          data: data,
          backgroundColor: data.map(d => recColors[d.rec].solid + 'cc'),
          borderColor: data.map(d => recColors[d.rec].solid),
          borderWidth: 1,
        }],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const d = data[ctx.dataIndex];
                return `${d.label} — ${d.rec} • ${opps[d.i].utility_score}/10`;
              }
            }
          }
        },
        scales: {
          x: {
            title: { display: true, text: 'Complexidade de implementação →', color:'#94a3b8' },
            min: 0.5, max: 3.5,
            ticks: { color: '#94a3b8', stepSize: 1, callback: (v) => ({1:'Baixa',2:'Média',3:'Alta'}[v] || '') },
            grid: { color: 'rgba(255,255,255,0.05)' },
          },
          y: {
            title: { display: true, text: '↑ Utilidade / Score (0–10)', color:'#94a3b8' },
            min: 0, max: 10,
            ticks: { color: '#94a3b8' },
            grid: { color: 'rgba(255,255,255,0.08)' },
          }
        },
        onClick: (e, els) => {
          if (els.length) {
            const idx = data[els[0].index].i;
            openPrompt(idx);
          }
        }
      }
    });
    // Draw quadrant labels after chart renders
    setTimeout(() => {
      // Just visual hint via plugins would be nicer; keep simple for MVP.
    }, 50);
  }
  let matrixChart = null;

  function shortLabel(name) {
    if (name.length > 32) return name.slice(0,31)+'…';
    return name;
  }

  function renderCards() {
    const grid = $('#cardsGrid');
    const opps = state.analysis.opportunities;
    const filtered = state.filter === 'all' ? opps : opps.filter(o => o.recommendation === state.filter);
    // Sort AGORA first, then DEPOIS, then NÃO USAR, by score desc within each
    const order = {'AGORA':0,'DEPOIS':1,'NÃO USAR':2};
    filtered.sort((a,b) => {
      const d = order[a.recommendation]-order[b.recommendation];
      return d !== 0 ? d : b.utility_score - a.utility_score;
    });

    if (filtered.length === 0) {
      grid.innerHTML = `<div class="col-span-2 text-center text-slate-500 text-sm py-10">Nenhuma oportunidade neste filtro.</div>`;
      return;
    }

    grid.innerHTML = filtered.map(o => {
      const idx = opps.indexOf(o);
      const c = recColors[o.recommendation];
      const scoreColorVal = scoreColor(o.utility_score);
      return `
        <div class="card rounded-2xl p-5 flex flex-col gap-3 fade-in">
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1">
              <div class="flex items-center gap-2 flex-wrap mb-1.5">
                ${recBadge(o.recommendation)}
                <span class="text-xs text-slate-500 mono">${escapeHtml(o.category || '')}</span>
              </div>
              <h4 class="font-semibold text-slate-100 leading-snug">${escapeHtml(o.use_case)}</h4>
            </div>
            ${scoreRing(o.utility_score, scoreColorVal)}
          </div>
          <p class="text-sm text-slate-300 leading-relaxed">${escapeHtml(o.benefit)}</p>
          <div class="grid grid-cols-2 gap-2 text-xs">
            <div class="rounded-lg bg-ink-900/70 p-2.5 border border-white/5">
              <div class="text-slate-500 uppercase tracking-wider text-[10px]">Complexidade</div>
              <div class="text-slate-200 font-medium mt-0.5">${escapeHtml(o.implementation_complexity)}</div>
            </div>
            <div class="rounded-lg bg-ink-900/70 p-2.5 border border-white/5">
              <div class="text-slate-500 uppercase tracking-wider text-[10px]">Custo operacional</div>
              <div class="text-slate-200 font-medium mt-0.5">${escapeHtml(o.cost_impact.length > 80 ? o.cost_impact.slice(0,78)+'…' : o.cost_impact)}</div>
            </div>
          </div>
          <details class="text-sm">
            <summary class="flex items-center gap-2 text-slate-400 hover:text-slate-200">
              <span class="toggle-plus">▸</span> Ver análise crítica, prós/contras, riscos, comparação de alternativas
            </summary>
            <div class="mt-3 space-y-4 text-sm">
              <div>
                <div class="text-xs uppercase tracking-wider text-slate-500 mb-1">🔄 Onde JEV entra</div>
                <div class="text-slate-300 text-[13px] leading-relaxed">${escapeHtml(o.entry_point)}</div>
              </div>
              <div class="grid md:grid-cols-2 gap-3">
                <div>
                  <div class="text-xs uppercase tracking-wider text-emerald-400/80 mb-1">✅ Prós</div>
                  <ul class="list-disc list-inside text-slate-300 text-[13px] space-y-0.5">
                    ${o.pros.map(p => `<li>${escapeHtml(p)}</li>`).join('')}
                  </ul>
                </div>
                <div>
                  <div class="text-xs uppercase tracking-wider text-rose-400/80 mb-1">⚖️ Contras</div>
                  <ul class="list-disc list-inside text-slate-300 text-[13px] space-y-0.5">
                    ${o.cons.map(pn => `<li>${escapeHtml(pn)}</li>`).join('')}
                  </ul>
                </div>
              </div>
              <div>
                <div class="text-xs uppercase tracking-wider text-amber-400/80 mb-1">⚠️ Riscos e limitações</div>
                <ul class="list-disc list-inside text-slate-300 text-[13px] space-y-0.5">
                  ${o.risks.map(r => `<li>${escapeHtml(r)}</li>`).join('')}
                </ul>
              </div>
              <div>
                <div class="text-xs uppercase tracking-wider text-slate-500 mb-1">📈 Quando se justifica / gatilho de escala</div>
                <div class="text-slate-300 text-[13px]">${escapeHtml(o.trigger_scale)}</div>
              </div>
              <div>
                <div class="text-xs uppercase tracking-wider text-slate-500 mb-1">🔁 Solução atual/alternativa sem JEV</div>
                <div class="text-slate-300 text-[13px]">${escapeHtml(o.current_solution)}</div>
              </div>
              ${o.comparison ? `
              <div>
                <div class="text-xs uppercase tracking-wider text-slate-500 mb-2">⚖️ Comparação de alternativas</div>
                <div class="overflow-x-auto">
                  <table class="w-full text-xs">
                    <thead>
                      <tr class="text-slate-500 text-left">
                        <th class="py-1 pr-3">Solução</th><th class="py-1 pr-3">Custo</th><th class="py-1 pr-3">Latência</th><th class="py-1 pr-3">Previsibilidade</th><th class="py-1">Quando usar</th>
                      </tr>
                    </thead>
                    <tbody class="text-slate-300">
                      ${Object.entries(o.comparison).map(([name,m]) => `
                        <tr class="border-t border-white/5">
                          <td class="py-1.5 pr-3 font-medium ${name === 'JEV' ? 'text-sky-300' : ''}">${escapeHtml(name)}</td>
                          <td class="py-1.5 pr-3">${escapeHtml(m.custo)}</td>
                          <td class="py-1.5 pr-3">${escapeHtml(m.latência)}</td>
                          <td class="py-1.5 pr-3">${escapeHtml(m.previsibilidade)}</td>
                          <td class="py-1.5 text-slate-400">${escapeHtml(m.quando_usar)}</td>
                        </tr>
                      `).join('')}
                    </tbody>
                  </table>
                </div>
              </div>` : ''}
              ${o.score_breakdown?.criteria ? `
              <div>
                <div class="text-xs uppercase tracking-wider text-slate-500 mb-2">📊 Como o score foi calculado</div>
                <div class="grid grid-cols-2 md:grid-cols-3 gap-2 text-xs">
                  ${Object.entries(o.score_breakdown.criteria).map(([k,v]) => `
                    <div class="rounded-md bg-ink-900/60 border border-white/5 p-2">
                      <div class="text-slate-500 text-[11px]">${escapeHtml(k)}</div>
                      <div class="text-slate-200 font-semibold mono">${Number(v).toFixed(1)}</div>
                    </div>
                  `).join('')}
                </div>
                <div class="text-[11px] text-slate-500 mt-2 mono">${escapeHtml(o.score_breakdown.formula)}</div>
              </div>`:''}
            </div>
          </details>
          <div class="flex items-center justify-between gap-2 pt-1">
            <button class="prompt-btn btn text-xs rounded-lg bg-sky-500 hover:bg-sky-400 text-ink-950 font-semibold px-4 py-2" data-idx="${idx}">
              📋 Copiar Prompt de Implementação
            </button>
            <div class="text-[11px] text-slate-500 mono">#${idx+1}</div>
          </div>
        </div>
      `;
    }).join('');

    grid.querySelectorAll('.prompt-btn').forEach(btn => {
      btn.addEventListener('click', () => openPrompt(parseInt(btn.dataset.idx,10)));
    });
  }

  function scoreRing(score, color) {
    const r = 26, c = 2*Math.PI*r;
    const off = c - (Math.max(0,Math.min(10,score))/10)*c;
    return `
      <div class="relative w-[64px] h-[64px] flex-none">
        <svg width="64" height="64" class="score-ring">
          <circle cx="32" cy="32" r="${r}" stroke="rgba(255,255,255,0.08)" stroke-width="5" fill="none"/>
          <circle cx="32" cy="32" r="${r}" stroke="${color}" stroke-width="5" fill="none"
            stroke-dasharray="${c}" stroke-dashoffset="${off}" stroke-linecap="round"/>
        </svg>
        <div class="absolute inset-0 grid place-items-center">
          <div class="text-center">
            <div class="text-sm font-extrabold leading-none" style="color:${color}">${score}</div>
            <div class="text-[9px] text-slate-500 mono">/10</div>
          </div>
        </div>
      </div>
    `;
  }

  async function openPrompt(idx) {
    try {
      const r = await fetch(`/api/analysis/${state.analysisId}/prompt/${idx}`);
      if (!r.ok) throw new Error('Falha ao gerar prompt');
      const j = await r.json();
      $('#promptTitle').textContent = j.use_case;
      $('#promptBody').textContent = j.prompt;
      $('#promptModal').classList.remove('hidden');
      $('#promptModal').dataset.prompt = j.prompt;
    } catch (e) {
      showError(e.message);
    }
  }

  function filterBtn(id, label, active=false) {
    return `<button class="filter-btn btn rounded-lg ${active ? 'bg-sky-500 text-ink-950' : 'bg-white/5 text-slate-300'} px-3 py-1.5 font-semibold" data-filter="${id}">${label}</button>`;
  }

  function escapeHtml(s) {
    if (s == null) return '';
    return String(s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }

  // Wire up
  $('#analyzeBtn').addEventListener('click', () => {
    const v = $('#sourceInput').value.trim();
    if (!v) { showError('Informe uma URL ou caminho.'); return; }
    analyze(v);
  });
  $('#sourceInput').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') $('#analyzeBtn').click();
  });
  $$('.sample-btn').forEach(b => b.addEventListener('click', () => {
    $('#sourceInput').value = b.dataset.sample;
    $('#analyzeBtn').click();
  }));
  $('#closePromptBtn').addEventListener('click', () => $('#promptModal').classList.add('hidden'));
  $('#copyPromptBtn').addEventListener('click', async () => {
    const text = $('#promptModal').dataset.prompt || '';
    try {
      await navigator.clipboard.writeText(text);
      const btn = $('#copyPromptBtn');
      const orig = btn.textContent;
      btn.textContent = '✓ Copiado!';
      setTimeout(() => btn.textContent = orig, 1400);
    } catch {
      showError('Não foi possível copiar — selecione e copie manualmente.');
    }
  });
  $('#promptModal').addEventListener('click', (e) => {
    if (e.target.id === 'promptModal') $('#promptModal').classList.add('hidden');
  });
})();

// 서울 행정동 어린이집 공급 지표: 지도(Leaflet)와 그래프(Plotly)
const fmt = (v, d = 0) => (v === null || v === undefined || Number.isNaN(v)) ? '-' : Number(v).toLocaleString('ko-KR', { maximumFractionDigits: d, minimumFractionDigits: d });
const pct = (v, d = 1) => (v === null || v === undefined) ? '-' : (v * 100).toFixed(d) + '%';
const FONT = { family: 'Noto Sans KR, sans-serif', size: 13, color: '#1f2328' };
const QUAD_COLORS = {
  '아동 많음·공급 부족': '#c2410c',
  '아동 많음·공급 충분': '#1d4ed8',
  '아동 적음·공급 부족': '#f4b183',
  '아동 적음·공급 충분': '#a8bfd8',
};
const TYPES = ['국공립', '민간', '가정', '직장', '법인·단체등', '사회복지법인', '협동'];

const LAYERS = [
  { key: 'supply', label: '공급률 (1,000명당 정원)', kind: 'quantile', colors: ['#b91c1c', '#f97316', '#fde68a', '#93c5fd', '#1e40af'], unit: '명', d: 0 },
  { key: 'supply_nowork', label: '직장어린이집 제외 공급률', kind: 'quantile', colors: ['#b91c1c', '#f97316', '#fde68a', '#93c5fd', '#1e40af'], unit: '명', d: 0 },
  { key: 'gs', label: '유형 다양성 (Gini–Simpson)', kind: 'quantile', colors: ['#f3e8ff', '#d8b4fe', '#a855f7', '#7e22ce', '#4c1d95'], unit: '', d: 2 },
  { key: 'pub_lq', label: '국공립 정원 LQ', kind: 'breaks', breaks: [0.5, 0.8, 1.2, 1.5], colors: ['#8c510a', '#d8b365', '#f5f0e6', '#5ab4ac', '#01665e'], unit: '', d: 2 },
  { key: 'child', label: '0~9세 인구', kind: 'quantile', colors: ['#fff7ed', '#fed7aa', '#fb923c', '#ea580c', '#9a3412'], unit: '명', d: 0 },
  { key: 'quad', label: '교차 분류 (아동 × 공급)', kind: 'category' },
];

let geo, summary, gu, map, layerGroup, current = LAYERS[0], selected = null;
const byName = new Map();

function quantileBreaks(vals, n = 5) {
  const s = vals.filter(v => v !== null && !Number.isNaN(v)).sort((a, b) => a - b);
  const out = [];
  for (let i = 1; i < n; i++) out.push(s[Math.floor(i * s.length / n)]);
  return out;
}

function colorFor(layer, v, breaks) {
  if (layer.kind === 'category') return QUAD_COLORS[v] || '#ccc';
  if (v === null || v === undefined || Number.isNaN(v)) return '#d1d5db';
  let i = 0;
  while (i < breaks.length && v >= breaks[i]) i++;
  return layer.colors[i];
}

function legendHtml(layer, breaks) {
  if (layer.kind === 'category') {
    return '<b>교차 분류</b><br>' + Object.entries(QUAD_COLORS).map(([k, c]) => `<i style="background:${c}"></i>${k}`).join('<br>') +
      '<br><span style="color:#666">아동 LQ 1, 서울 평균 공급률 기준</span>';
  }
  const lab = [];
  const f = v => fmt(v, layer.d);
  lab.push(`&lt; ${f(breaks[0])}`);
  for (let i = 0; i < breaks.length - 1; i++) lab.push(`${f(breaks[i])} – ${f(breaks[i + 1])}`);
  lab.push(`≥ ${f(breaks[breaks.length - 1])}`);
  let html = `<b>${layer.label}</b><br>` + lab.map((t, i) => `<i style="background:${layer.colors[i]}"></i>${t}`).join('<br>');
  html += `<br><i style="background:#d1d5db"></i>자료 없음`;
  return html;
}

let legend;
function draw(layer) {
  current = layer;
  const vals = geo.features.map(f => f.properties[layer.key]);
  const breaks = layer.kind === 'quantile' ? quantileBreaks(vals) : (layer.breaks || []);
  if (layerGroup) layerGroup.remove();
  layerGroup = L.geoJSON(geo, {
    style: f => ({
      fillColor: colorFor(layer, f.properties[layer.key], breaks), fillOpacity: 0.82,
      color: f.properties.note ? '#111' : '#ffffff', weight: f.properties.note ? 1.6 : 0.6,
      dashArray: f.properties.note ? '4 3' : null,
    }),
    onEachFeature: (f, lyr) => {
      const p = f.properties;
      const v = layer.kind === 'category' ? p.quad : fmt(p[layer.key], layer.d) + (layer.unit ? ' ' + layer.unit : '');
      lyr.bindTooltip(`<b>${p.sggnm} ${p.name}</b><br>${layer.label}: ${v}`, { sticky: true });
      lyr.on('click', () => select(p.ucode));
      byName.set(p.ucode, lyr);
    },
  }).addTo(map);
  if (legend) legend.remove();
  legend = L.control({ position: 'bottomright' });
  legend.onAdd = () => { const d = L.DomUtil.create('div', 'legend'); d.innerHTML = legendHtml(layer, breaks); return d; };
  legend.addTo(map);
  document.querySelectorAll('#layers button').forEach(b => b.classList.toggle('on', b.dataset.key === layer.key));
  if (selected) highlight(selected);
}

function highlight(code) {
  const lyr = byName.get(code);
  if (!lyr) return;
  lyr.setStyle({ weight: 3, color: '#111' });
  lyr.bringToFront();
}

function select(code) {
  if (selected && byName.get(selected)) layerGroup.resetStyle(byName.get(selected));
  selected = code;
  const f = geo.features.find(x => x.properties.ucode === code);
  if (!f) return;
  const p = f.properties;
  highlight(code);
  const maxCap = Math.max(...TYPES.map(t => p[t] || 0), 1);
  const bars = TYPES.filter(t => p[t] > 0).map(t =>
    `<div class="row"><span>${t}</span><span class="bar"><i style="width:${(p[t] / maxCap * 100).toFixed(1)}%"></i></span><span style="text-align:right">${fmt(p[t])}</span></div>`).join('');
  document.getElementById('panel').innerHTML = `
    <h3>${p.name}</h3><p class="gu">${p.sggnm} · ${p.quad}</p>
    <dl>
      <dt>0~9세 인구</dt><dd>${fmt(p.child)}명</dd>
      <dt>어린이집 수</dt><dd>${fmt(p.n)}곳</dd>
      <dt>정원 / 현원</dt><dd>${fmt(p.cap)} / ${fmt(p.cur)}</dd>
      <dt>공급률</dt><dd><b>${fmt(p.supply, 1)}</b> (서울 ${fmt(summary.seoul_supply, 1)})</dd>
      <dt>직장 제외 공급률</dt><dd>${fmt(p.supply_nowork, 1)}</dd>
      <dt>유형 다양성</dt><dd>${fmt(p.gs, 3)}</dd>
      <dt>국공립 비중 / LQ</dt><dd>${pct(p.pub_share)} / ${fmt(p.pub_lq, 2)}</dd>
      <dt>정원 충족률</dt><dd>${pct(p.fill)}</dd>
      <dt>아동 LQ</dt><dd>${fmt(p.child_lq, 2)}</dd>
    </dl>
    ${bars ? '<div class="bars"><div style="font-size:12px;color:#5f6670;margin-bottom:2px">유형별 정원</div>' + bars + '</div>' : ''}
    ${p.note ? `<div class="note">${p.note}: 03시 생활인구 ${fmt(p.total)}명, 면적 ${fmt(p.area_km2, 2)}㎢</div>` : ''}`;
}

function initMap() {
  map = L.map('map', { zoomSnap: 0.25, scrollWheelZoom: false }).setView([37.5636, 126.99], 10.75);
  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles © Esri — Esri, HERE, Garmin, © OpenStreetMap contributors', maxZoom: 16,
  }).addTo(map);
  map.on('focus', () => map.scrollWheelZoom.enable());
  map.on('blur', () => map.scrollWheelZoom.disable());
  const box = document.getElementById('layers');
  LAYERS.forEach(l => {
    const b = document.createElement('button');
    b.textContent = l.label; b.dataset.key = l.key;
    b.onclick = () => draw(l);
    box.appendChild(b);
  });
  const dl = document.getElementById('dong-list');
  geo.features.map(f => f.properties).sort((a, b) => a.name.localeCompare(b.name, 'ko')).forEach(p => {
    const o = document.createElement('option'); o.value = `${p.name} (${p.sggnm})`; o.dataset.code = p.ucode; dl.appendChild(o);
  });
  document.getElementById('search').addEventListener('change', e => {
    const v = e.target.value;
    const p = geo.features.map(f => f.properties).find(p => `${p.name} (${p.sggnm})` === v || p.name === v);
    if (!p) return;
    const lyr = byName.get(p.ucode);
    if (lyr) map.fitBounds(lyr.getBounds(), { maxZoom: 14 });
    select(p.ucode);
  });
  draw(LAYERS[0]);
}

function layout(extra) {
  return Object.assign({ font: FONT, margin: { l: 56, r: 16, t: 10, b: 50 }, paper_bgcolor: '#fff', plot_bgcolor: '#fff', hoverlabel: { font: FONT } }, extra);
}
const CFG = { displayModeBar: false, responsive: true };

function charts() {
  const P = geo.features.map(f => f.properties);
  // 로렌츠 곡선
  Plotly.newPlot('c-lorenz', [
    { x: [0, 1], y: [0, 1], mode: 'lines', line: { color: '#9ca3af', dash: 'dot' }, name: '완전 균등', hoverinfo: 'skip' },
    { x: summary.lorenz.x, y: summary.lorenz.y, mode: 'lines', line: { color: '#c2410c', width: 3 }, fill: 'tonexty', fillcolor: 'rgba(194,65,12,.12)', name: '서울 424개 동',
      hovertemplate: '아동 누적 %{x:.0%}<br>정원 누적 %{y:.0%}<extra></extra>' },
  ], layout({
    xaxis: { title: '누적 0~9세 인구 비율 (공급률 낮은 동부터)', tickformat: '.0%', range: [0, 1] },
    yaxis: { title: '누적 정원 비율', tickformat: '.0%', range: [0, 1] },
    showlegend: false,
    annotations: [{ x: 0.62, y: 0.3, text: `Gini = ${summary.gini.toFixed(3)}`, showarrow: false, font: { size: 18, color: '#c2410c' } }],
  }), CFG);

  // 아동 인구 vs 공급률
  const sc = Object.keys(QUAD_COLORS).map(q => {
    const s = P.filter(p => p.quad === q && p.supply > 0);
    return {
      x: s.map(p => p.child), y: s.map(p => p.supply), mode: 'markers', type: 'scatter', name: q,
      marker: { color: QUAD_COLORS[q], size: 7, opacity: 0.85, line: { width: 0.5, color: '#fff' } },
      text: s.map(p => `${p.sggnm} ${p.name}`),
      hovertemplate: '%{text}<br>0~9세 %{x:,.0f}명<br>공급률 %{y:,.1f}<extra></extra>',
    };
  });
  Plotly.newPlot('c-scatter', sc, layout({
    xaxis: { title: '0~9세 인구 (명, 로그)', type: 'log' },
    yaxis: { title: '1,000명당 정원 (로그)', type: 'log' },
    legend: { orientation: 'h', y: -0.25, font: { size: 11 } },
    margin: { l: 56, r: 16, t: 10, b: 90 },
    shapes: [{ type: 'line', xref: 'paper', x0: 0, x1: 1, y0: summary.seoul_supply, y1: summary.seoul_supply, line: { dash: 'dash', color: '#6b7280', width: 1 } }],
    annotations: [{ xref: 'paper', x: 0.99, y: Math.log10(summary.seoul_supply), yanchor: 'bottom', xanchor: 'right', text: `서울 평균 ${summary.seoul_supply}`, showarrow: false, font: { size: 11, color: '#6b7280' } },
      { xref: 'paper', yref: 'paper', x: 0.02, y: 0.04, xanchor: 'left', text: `스피어만 ρ = ${summary.spearman_child_supply}`, showarrow: false, font: { size: 13 } }],
  }), CFG);

  // 자치구별 공급률
  const g1 = [...gu].sort((a, b) => a.supply - b.supply);
  Plotly.newPlot('c-gu', [{
    type: 'bar', orientation: 'h', y: g1.map(g => g.gu), x: g1.map(g => g.supply),
    marker: { color: g1.map(g => g.supply < summary.seoul_supply ? '#c2410c' : '#1d4ed8') },
    hovertemplate: '%{y}<br>공급률 %{x:.1f}<extra></extra>',
  }], layout({
    margin: { l: 70, r: 16, t: 10, b: 44 }, height: 560,
    xaxis: { title: '0~9세 1,000명당 정원' }, yaxis: { automargin: true },
    shapes: [{ type: 'line', yref: 'paper', y0: 0, y1: 1, x0: summary.seoul_supply, x1: summary.seoul_supply, line: { dash: 'dash', color: '#6b7280', width: 1 } }],
  }), CFG);

  // 구별 Gini
  const g2 = [...gu].sort((a, b) => a.gini - b.gini);
  Plotly.newPlot('c-gugini', [{
    type: 'bar', orientation: 'h', y: g2.map(g => g.gu), x: g2.map(g => g.gini), marker: { color: '#7e22ce' },
    customdata: g2.map(g => g.dongs), hovertemplate: '%{y}<br>Gini %{x:.3f}<br>행정동 %{customdata}개<extra></extra>',
  }], layout({ margin: { l: 70, r: 16, t: 10, b: 44 }, height: 560, xaxis: { title: '구 안 동 간 Gini' }, yaxis: { automargin: true } }), CFG);
  document.getElementById('c-gu').style.height = '560px';
  document.getElementById('c-gugini').style.height = '560px';

  // 교차 분류별 충족률
  Plotly.newPlot('c-fill', Object.keys(QUAD_COLORS).map(q => ({
    type: 'box', name: q.replace('·', '<br>'), y: P.filter(p => p.quad === q && p.fill !== null).map(p => p.fill),
    marker: { color: QUAD_COLORS[q] }, boxpoints: false, hovertemplate: '%{y:.0%}<extra></extra>',
  })), layout({ showlegend: false, yaxis: { title: '정원 충족률 (현원 ÷ 정원)', tickformat: '.0%' }, margin: { l: 56, r: 16, t: 10, b: 70 } }), CFG);

  // 국공립 LQ vs 다양성
  const s2 = P.filter(p => p.gs !== null);
  Plotly.newPlot('c-gs', [{
    x: s2.map(p => p.pub_lq), y: s2.map(p => p.gs), mode: 'markers', type: 'scatter',
    marker: { color: '#4c1d95', size: 6, opacity: 0.55 }, text: s2.map(p => `${p.sggnm} ${p.name}`),
    hovertemplate: '%{text}<br>국공립 LQ %{x:.2f}<br>다양성 %{y:.2f}<extra></extra>',
  }], layout({
    xaxis: { title: '국공립 정원 LQ (1 = 서울 평균)' }, yaxis: { title: 'Gini–Simpson 다양성', range: [-0.03, 0.86] },
    shapes: [{ type: 'line', x0: 1, x1: 1, yref: 'paper', y0: 0, y1: 1, line: { dash: 'dot', color: '#9ca3af' } }],
  }), CFG);
}

function kpis() {
  document.getElementById('k-fac').textContent = fmt(summary.n_facilities) + '곳';
  document.getElementById('k-cap').textContent = fmt(summary.cap) + '명';
  document.getElementById('k-sup').textContent = fmt(summary.seoul_supply, 1) + '명';
  document.getElementById('k-gini').textContent = summary.gini.toFixed(3);
  document.getElementById('t-pub').textContent = pct(summary.seoul_pub_share);
  document.getElementById('t-fill').textContent = pct(summary.seoul_fill);
}

Promise.all(['data/dong.geojson', 'data/summary.json', 'data/gu.json'].map(u => fetch(u).then(r => r.json())))
  .then(([g, s, gg]) => { geo = g; summary = s; gu = gg; kpis(); initMap(); charts(); })
  .catch(e => { document.getElementById('panel').textContent = '자료를 불러오지 못했습니다: ' + e; });

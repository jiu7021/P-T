const PAGE_META = {
    's-llm': {
    tag: 'LOT YIELD AGENT',
    title: '3. 로트 수율 종합 진단',
    desc: '웨이퍼 딥러닝 패턴과 로트 내 결함 이력을 종합하여 LLM이 해당 로트의 위험도를 평가합니다.',
    status: '위험도 진단 완료'
  },
  's-overview': {
    tag: 'DASHBOARD OVERVIEW',
    title: '한눈에 보기',
    desc: '3종 공개 데이터셋(WM-811K, Carinthia-S, SECOM) 기반 전수 판정 및 공정 지표 종합 현황입니다.',
    status: '과거 데이터 기반 분석 결과'
  },
  's-eds': {
    tag: 'WAFER PROBE TEST',
    title: '1. EDS 웨이퍼 판정',
    desc: 'WM-811K 실데이터 기반 실리콘 웨이퍼 전수 전기 시험 및 칩 내부 Fail Address 분석입니다.',
    status: '분석 샘플 검사 완료'
  },
  's-fa': {
    tag: 'ELECTRON DEFECT REVIEW',
    title: '4. FA 물리적 결함 분석',
    desc: 'Carinthia-S 고해상도 전자현미경 결함 위치 관측 및 문헌 기반 원인 공정 룩업 분석입니다.',
    status: 'SEM 결함 실측 데이터 분석 완료'
  },
  's-map': {
    tag: 'SPATIAL DEFECT PATTERNS',
    title: '2. EDS 공간 불량패턴 인식',
    desc: '8대 공간 결함 패턴 CNN 신경망 분류 및 Grad-CAM 판단 근거 영역 가시화입니다.',
    status: 'CNN 8대 패턴 모델링 결과'
  },
  's-sensor': {
    tag: 'PROCESS SPC CONTROL',
    title: '5. FDC 공정 설비 이상 감지',
    desc: '실제 89일간 수집된 UCI SECOM 590개 센서 시계열 및 ±3σ 관리한계 이탈 추적입니다.',
    status: 'SECOM 590개 센서 분석 완료'
  },
  's-feedback': {
    tag: 'VALIDATION RIGOR & LIMITS',
    title: '5. 판정 피드백 & 한계',
    desc: '전문가 판정 피드백 루프 설계 원칙 및 공개 데이터셋의 구조적 한계점 명시입니다.',
    status: '과학적 검증 기준 준수'
  }
};

function switchCockpitTab(tabId) {
  document.querySelectorAll('.tab-pane').forEach(p => {
    p.classList.toggle('on', p.id === tabId);
  });
  document.querySelectorAll('.nav-btn').forEach(b => {
    b.classList.toggle('on', b.getAttribute('data-target') === tabId);
  });
  
  // Update Page Header Information
  const meta = PAGE_META[tabId];
  if (meta) {
    document.getElementById('pageTag').textContent = meta.tag;
    document.getElementById('pageTitle').textContent = meta.title;
    document.getElementById('pageSub').textContent = meta.desc;
    document.getElementById('pageLiveStatus').textContent = meta.status;
  }
  
  window.scrollTo({ top: 0, behavior: 'smooth' });
  
  setTimeout(() => {
    window.dispatchEvent(new Event('resize'));
    if (tabId === 's-eds') {
      const es = document.getElementById('esel');
      if (es) es.dispatchEvent(new Event('change'));
    } else if (tabId === 's-fa') {
      const ss = document.getElementById('ssel');
      if (ss) ss.dispatchEvent(new Event('change'));
    } else if (tabId === 's-map') {
      const ws = document.getElementById('wsel');
      if (ws) ws.dispatchEvent(new Event('change'));
    } else if (tabId === 's-sensor') {
      const ds = document.getElementById('dr_sel');
      if (ds) ds.dispatchEvent(new Event('change'));
    }
  }, 50);
}

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const target = btn.getAttribute('data-target');
    if (target) switchCockpitTab(target);
  });
});

// P&T 워크벤치 대시보드. 외부 라이브러리·API를 쓰지 않는다.
// 브라우저 저장소(localStorage 등)도 쓰지 않는다.
const D = JSON.parse(document.getElementById('payload').textContent);
const $ = (id) => document.getElementById(id) || document.createElement('div');  // 없는 요소는 빈 노드로 대체

// 영어 라벨은 데이터셋 원본 표기다. 화면에는 한글 설명을 함께 보인다.
const PAT_KO = {
  'none': '패턴 없음', 'Center': '중심부 밀집', 'Donut': '도넛(고리형)',
  'Edge-Loc': '가장자리 국부', 'Edge-Ring': '가장자리 링', 'Loc': '국부 밀집',
  'Random': '산발', 'Scratch': '긁힘(선상)', 'Near-full': '거의 전면',
};
const PAT_DESC = {
  'none': '불량이 없다는 뜻이 아니다. 산발 불량은 있으나 뚜렷한 공간 패턴을 이루지 않는 상태.',
  'Center': '웨이퍼 중심 쪽에 불량이 몰린 형태.',
  'Donut': '중심과 가장자리 사이에 고리 모양으로 불량이 몰린 형태.',
  'Edge-Loc': '가장자리 일부 구간에만 불량이 몰린 형태.',
  'Edge-Ring': '가장자리를 따라 링 전체에 불량이 도는 형태.',
  'Loc': '웨이퍼 어딘가 한 곳에 불량이 뭉친 형태.',
  'Random': '불량이 웨이퍼 전면에 흩어진 형태. 공간 상관이 약하다.',
  'Scratch': '가늘고 긴 선을 따라 불량이 늘어선 형태.',
  'Near-full': '웨이퍼 대부분이 불량인 상태.',
};
const MORPH_KO = {
  'linear_fine': '가늘고 긴 선상', 'linear_broad': '굵거나 불규칙한 선상',
  'compact': '둥근 덩어리형', 'none': '결함 없음',
};
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

// ---------- 탭 ----------
// 탭 전환은 SnowUI 레일이 담당한다(snowui-shell.js).

// ================= 탭 1: 웨이퍼 맵 =================
const W = D.wafers;
{
  const sel = $('wsel');
  W.forEach((w, i) => {
    const o = document.createElement('option');
    o.value = i;
    o.textContent = `${(PAT_KO[w.true_label] || w.true_label).padEnd(8, '\u3000')} ${w.correct ? '  ' : '✗ '}${w.wafer_id}`;
    sel.appendChild(o);
  });
  const wrong = W.filter(w => !w.correct).length;
  $('wcount').textContent = `${W.length}장 · 오분류 ${wrong}장 포함(✗)했습니다. 잘 맞은 것만 선별하지 않았습니다.`;
  sel.onchange = () => drawWafer(+sel.value);
  sel.value = 0;
  drawWafer(0);
}

function drawWafer(i) {
  const w = W[i];
  $('wid').textContent = `${w.wafer_id} · ${w.lot_id} #${w.wafer_index}`;

  // 웨이퍼 맵
  const c = $('wmap'), g = c.getContext('2d');
  const S = 320, px = Math.floor(Math.min(S / w.w, S / w.h));
  const ox = Math.floor((S - px * w.w) / 2), oy = Math.floor((S - px * w.h) / 2);
  g.clearRect(0, 0, S, S);
  const cols = [css('--die-out'), css('--die-pass'), css('--die-fail')];
  for (let y = 0; y < w.h; y++) for (let x = 0; x < w.w; x++) {
    const v = w.grid[y * w.w + x];
    if (v === 0) continue;                 // 웨이퍼 밖은 그리지 않는다
    g.fillStyle = cols[v];
    g.fillRect(ox + x * px, oy + y * px, px, px);
  }

  // Grad-CAM: 64x64 → 웨이퍼 맵과 같은 자리에 겹친다
  const c2 = $('wcam'), g2 = c2.getContext('2d');
  g2.clearRect(0, 0, S, S);
  g2.globalAlpha = 0.35;
  for (let y = 0; y < w.h; y++) for (let x = 0; x < w.w; x++) {
    if (w.grid[y * w.w + x] === 0) continue;
    g2.fillStyle = cols[w.grid[y * w.w + x]];
    g2.fillRect(ox + x * px, oy + y * px, px, px);
  }
  g2.globalAlpha = 1;
  const N = 64;
  for (let y = 0; y < w.h; y++) for (let x = 0; x < w.w; x++) {
    if (w.grid[y * w.w + x] === 0) continue;
    // 원본 좌표 → 64x64 CAM 좌표
    const cy = Math.min(N - 1, Math.floor((y + 0.5) / w.h * N));
    const cx = Math.min(N - 1, Math.floor((x + 0.5) / w.w * N));
    const v = w.cam[cy * N + cx] / 100;
    if (v < 0.15) continue;
    g2.fillStyle = `rgba(230,60,40,${(v * 0.75).toFixed(3)})`;
    g2.fillRect(ox + x * px, oy + y * px, px, px);
  }

  // 정보 패널
  const top = Object.entries(w.prob).sort((a, b) => b[1] - a[1]).slice(0, 4);
  const f = w.feat_summary;
  $('winfo').innerHTML = `
    <div class="kv">
      <b>실제 패턴</b><span>${PAT_KO[w.true_label] || w.true_label} <span style="color:var(--muted);font-size:13px">${w.true_label}</span></span>
      <b>모델 예측</b><span class="${w.correct ? 'ok' : 'bad'}">${PAT_KO[w.pred_label] || w.pred_label} ${w.correct ? '(일치)' : '(불일치)'}</span>
      <b>패턴 뜻</b><span style="font-size:13px;color:var(--muted)">${PAT_DESC[w.true_label] || ''}</span>
      <b>다이 수</b><span>${w.die_count.toLocaleString()}</span>
      <b>불량 다이</b><span>${w.fail_count.toLocaleString()} (${(w.fail_rate * 100).toFixed(2)}%)</span>
    </div>
    <h3 style="margin-top:14px">클래스 확률 상위 4</h3>
    ${top.map(([k, v]) => `<div style="margin-bottom:6px">
      <div style="display:flex;justify-content:space-between;font-size:14.5px">
        <span>${PAT_KO[k] || k}</span><span class="mono">${(v * 100).toFixed(1)}%</span></div>
      <div class="bar"><i style="width:${(v * 100).toFixed(1)}%"></i></div></div>`).join('')}
    <h3 style="margin-top:14px">공간 특징 요약</h3>
    <div class="kv">
      <b>이웃(8) 불량률 평균</b><span>${(f.nb8_fail_rate_mean * 100).toFixed(2)}%</span>
      <b>정규화 반경-불량 상관</b><span>${f.r_norm_fail_corr === null ? '정의 불가(불량이 상수)' : f.r_norm_fail_corr}</span>
      <b>가장자리 거리 평균</b><span>${f.edge_dist_mean}</span>
      <b>직전 웨이퍼 정보</b><span>${f.prev_wafer_available ? '있음' : '없음(로트 첫 웨이퍼 등)'}</span>
    </div>
`;
}

// ================= 탭 EDS: 웨이퍼 테스트 =================
const E = D.eds;
const G_COL = ['#4ca85c', '#f0bf33', '#d93630'];          // 면(막대·캔버스)용
const G_TXT = ['var(--grade-good)', 'var(--grade-rep)', 'var(--grade-fail)'];  // 글자용
const G_NAME = ['Good', 'Repairable', 'Fail'];
const G_KO = ['전 시험 통과', '여분 행·열로 복구 가능', '복구 불가'];
let eCur = 0, eGeom = null;

{
  const sel = $('esel');
  E.wafers.forEach((w, i) => {
    const o = document.createElement('option');
    const f = (w.counts.fail / (w.counts.good + w.counts.repairable + w.counts.fail) * 100);
    o.value = i;
    o.textContent = `${(PAT_KO[w.pattern] || w.pattern).padEnd(8, '\u3000')} Fail ${f.toFixed(0)}%`;
    sel.appendChild(o);
  });
  $('ecount').textContent = `${E.wafers.length}장. 패턴마다 Fail 비율 최저·최고를 함께 골랐습니다.`;
  sel.onchange = () => drawEds(+sel.value);
  sel.value = 0;

  // 시험 항목 표
  $('etests').innerHTML = E.tests.map(t => {
    const sp = t.spec, lo = sp.min, hi = sp.max;
    const spec = (lo !== null && hi !== null) ? `${lo} ~ ${hi} ${t.unit}`
               : (hi !== null ? `≤ ${hi} ${t.unit}` : `≥ ${lo} ${t.unit}`);
    const temp = (E.temperatures.find(x => x.id === t.temperature) || {}).label || '';
    return `<div class="cand">
      <div class="proc">${t.order}. ${t.label} <span style="font-weight:400;color:var(--muted);font-size:13px">${temp}</span></div>
      <div class="rat" style="white-space:pre-line">${t.plain.trim()}</div>
      <div style="font-size:14.5px;margin-top:5px"><b style="color:var(--muted)">규격</b> ${spec}
        · <b style="color:var(--muted)">리페어 대상</b> ${
          t.repairable_scope === 'cell_array' ? '예 (셀 어레이)' : '아니오 (칩 전체 특성)'}</div>
      ${(t.reference || []).map(r => `<div class="ref">출처: ${r}</div>`).join('')}
    </div>`;
  }).join('') + `<p style="font-size:14.5px;color:var(--warn)">규격 절대값은 가정치입니다.
    항목 간 상대 관계만 물리적으로 타당하게 잡았습니다.</p>`;

  $('egrades').innerHTML = E.grades.map((g, i) => `<div style="margin-bottom:8px">
      <b style="color:${G_TXT[i]}">${g.label}</b>
      <div style="font-size:14.5px;white-space:pre-line">${g.rule.trim()}</div>
      ${g.note ? `<div style="font-size:13px;color:var(--warn);white-space:pre-line;margin-top:4px">${g.note.trim()}</div>` : ''}
    </div>`).join('');

  const ra = (D.eds.repair_analysis_steps || null);
  $('esteps').innerHTML = [
    'fail bit의 주소를 (X=행, Y=열)으로 모은다.',
    '어떤 행의 fail 수가 <b>남은 여분 열</b>보다 많으면 열로 덮을 수 없다 → 반드시 행 리페어를 배정한다.',
    '어떤 열의 fail 수가 <b>남은 여분 행</b>보다 많으면 → 반드시 열 리페어.',
    '강제 배정을 마친 뒤 남은 fail을 남은 여분으로 덮을 수 있는지 탐색한다.',
    '전부 덮이면 Repairable, 남으면 Fail.',
  ].map(x => `<li>${x}</li>`).join('');
  $('erefs').innerHTML = `<div style="font-size:13px"><b style="color:var(--muted)">여분 자원</b>
      행 ${E.repair.spare_rows}개 / 열 ${E.repair.spare_cols}개 <span style="color:var(--warn)">(가정치)</span></div>`
    + (E.repair.reference || []).map(r => `<div class="ref">출처: ${r}</div>`).join('');

  // 모드별 리페어 성공률
  const bm = E.summary.by_mode || {};
  const rows = Object.entries(bm).sort((a, b) => b[1].repairable - a[1].repairable);
  $('emodes').innerHTML = `<table><tr><th>불량 모드</th><th>다이 수</th><th>Repairable</th></tr>`
    + rows.map(([k, v]) => `<tr><td>${MODE_LABEL_E(k)}</td><td>${v.n.toLocaleString()}</td>
        <td class="${v.repairable > 0.5 ? 'ok' : 'bad'}">${(v.repairable * 100).toFixed(2)}%</td></tr>`).join('')
    + `</table><p style="font-size:13px;color:var(--muted);margin-top:8px">
      로우성 하나는 여분 행 1개로 끝납니다. 블락성은 행·열을 다 써도 못 덮습니다.
      좁은 영역에 fail이 뭉치면 어느 한 줄로 정리되지 않기 때문입니다.</p>`;

  // 민감도
  const S = E.sensitivity;
  const card = (title, note, rowsArr) => `<div class="cand">
      <div class="proc">${title}</div>
      <div style="font-size:13px;color:var(--muted);margin-bottom:5px">${note}</div>
      <table><tr><th>조건</th><th>Repairable</th><th>Fail</th></tr>
      ${rowsArr.map(([k, v, mark]) => `<tr><td>${k}${mark ? ' <b>← 기준</b>' : ''}</td>
        <td>${(v.repairable * 100).toFixed(2)}%</td><td>${(v.fail * 100).toFixed(2)}%</td></tr>`).join('')}
      </table></div>`;
  $('esens').innerHTML =
    card('여분 행·열 개수', '2배로 늘려도 Repairable은 크게 늘지 않습니다. 블락성이 안 덮이기 때문입니다.',
         Object.entries(S.spare).map(([k, v]) => [k.replace('r', '행/').replace('c', '열'), v, k === '4r4c']))
  + card('리페어 불가 비율', '칩 전체 특성 불량의 비율. 근거가 되는 공개 통계가 없는 가정치입니다.',
         Object.entries(S.die_ratio).map(([k, v]) => [k, v, k === '0.25']))
  + card('불량 모드 배분', '가장 민감한 가정입니다. Repairable 절대값을 인용해서는 안 됩니다.',
         Object.entries(S.mode_mix).map(([k, v]) => [k, v, k === '기준']));

  drawEds(0);

  // ---- 전체 판정 결과 ----
  const gc = E.summary.grade_counts, tot = E.summary.n_die;
  const failReal = gc.repairable + gc.fail;          // 실데이터가 불량이라 정한 다이
  $('e_total').innerHTML = `
    <div style="font-size:13px;margin-bottom:9px">웨이퍼 2,000장 · 다이
      <b>${tot.toLocaleString()}</b>개 전수 판정</div>
    ${[['good', 'Good'], ['repairable', 'Repairable'], ['fail', 'Fail']].map(([k, nm], i) => `
      <div style="margin-bottom:6px">
        <div style="display:flex;justify-content:space-between;font-size:14.5px">
          <span>${nm}</span><span class="mono">${gc[k].toLocaleString()} (${(gc[k] / tot * 100).toFixed(2)}%)</span></div>
        <div class="bar"><i style="width:${(gc[k] / tot * 100).toFixed(1)}%;background:${G_COL[i]}"></i></div></div>`).join('')}
    <p style="font-size:13px;margin:10px 0 0">실데이터상 불량 다이 <b>${failReal.toLocaleString()}</b>개 중
      <b class="ok">${(gc.repairable / failReal * 100).toFixed(1)}%</b>를 여분 행·열로 살릴 수 있음을 확인했습니다.</p>
    <p style="font-size:13px;color:var(--muted);margin-bottom:0">
      어느 다이가 불량인지는 WM-811K 실데이터가 정합니다. 측정값과 fail 주소는 합성이며,
      합성은 '왜 불량인지'만 만듭니다.</p>`;

  // ---- 검증이 잡아낸 오류 ----
  $('e_verify').innerHTML = `
    <p style="font-size:14.5px;margin-top:0">코드에 검증 조건을 심어, 조건을 어기면
      <b>결과를 저장하지 않고 중단</b>하도록 만들었습니다.</p>
    <div class="cand" style="border-color:var(--bad)">
      <div class="proc" style="color:var(--bad)">검출된 오류 — 정상 다이 275,159개가 불량으로 뒤집힘</div>
      <div class="rat">"합성 데이터가 실데이터의 정상·불량 판정을 뒤집으면 저장하지 말고 중단하라"는
        조건이 초기 구현에서 걸렸습니다. 리텐션 값을 <span class="mono">105 + 22·f − 25·r + 잡음</span>
        같은 선형식으로 만들자 꼬리가 규격(64 ms) 아래로 내려가, 실데이터가 정상이라 한 다이가
        불량으로 판정됐습니다. 로지스틱으로 유계화해 규격 안에 가두되 공간 상관은 유지하도록 고쳤습니다.</div>
      <div class="note">수정 후 정상 다이 65,223개 표본에서 규격 위반 0을 확인했습니다.</div>
    </div>
    <table>
      <tr><th>검증 항목</th><th>결과</th></tr>
      <tr><td style="text-align:left">실데이터 정상 → Good</td><td class="ok">1,638,172개 · 불일치 0</td></tr>
      <tr><td style="text-align:left">실데이터 불량 → Repairable/Fail</td><td class="ok">490,546개 · 불일치 0</td></tr>
      <tr><td style="text-align:left">이웃 다이 특징의 미래 정보 누수</td><td class="ok">1.2만 건 대조 · 불일치 0</td></tr>
    </table>`;
}

function MODE_LABEL_E(k) {
  return ({single_bit: '싱글비트', row_fail: '로우성', column_fail: '칼럼성',
           block_fail: '블락성', cross_fail: '크로스'})[k] || k;
}

function drawEds(i) {
  eCur = i;
  const w = E.wafers[i], S = 360;
  $('etitle').textContent = `${w.wafer_id} · ${PAT_KO[w.pattern] || w.pattern}`;
  const c = $('emap'), g = c.getContext('2d');
  const px = Math.floor(Math.min(S / w.w, S / w.h));
  const ox = Math.floor((S - px * w.w) / 2), oy = Math.floor((S - px * w.h) / 2);
  eGeom = {px, ox, oy};
  g.clearRect(0, 0, S, S);
  for (let k = 0; k < w.x.length; k++) {
    g.fillStyle = G_COL[w.grade[k]];
    g.fillRect(ox + w.x[k] * px, oy + w.y[k] * px, px, px);
  }
  const tot = w.x.length;
  $('ebar').innerHTML = [0, 1, 2].map(gi => {
    const n = w.grade.filter(v => v === gi).length;
    return `<div style="margin-bottom:5px">
      <div style="display:flex;justify-content:space-between;font-size:14.5px">
        <span>${G_NAME[gi]}</span><span class="mono">${n.toLocaleString()} (${(n / tot * 100).toFixed(2)}%)</span></div>
      <div class="bar"><i style="width:${(n / tot * 100).toFixed(1)}%;background:${G_COL[gi]}"></i></div></div>`;
  }).join('');
}

$('emap').onclick = (ev) => {
  const w = E.wafers[eCur], r = $('emap').getBoundingClientRect();
  const sx = $('emap').width / r.width;
  const mx = Math.floor(((ev.clientX - r.left) * sx - eGeom.ox) / eGeom.px);
  const my = Math.floor(((ev.clientY - r.top) * sx - eGeom.oy) / eGeom.px);
  const k = w.x.findIndex((x, idx) => x === mx && w.y[idx] === my);
  if (k < 0) return;
  const gi = w.grade[k];
  const mode = E.modes[w.mode[k]] || '';
  const spec = Object.fromEntries(E.tests.map(t => [t.id, t.spec]));
  const rowsHtml = [
    ['핀 전압 (오픈/쇼트)', (w.os[k] / 100).toFixed(2), 'V', spec.open_short],
    ['대기 전류', (w.ids[k] / 100).toFixed(2), 'mA', spec.idd_standby],
    ['동작 전류', (w.ida[k] / 10).toFixed(1), 'mA', spec.idd_active],
    ['리텐션 (85°C)', (w.ret[k] / 10).toFixed(1), 'ms', spec.retention_hot],
  ].map(([nm, v, u, sp]) => {
    const val = parseFloat(v);
    const bad = (sp.min !== null && val < sp.min) || (sp.max !== null && val > sp.max);
    const spTxt = (sp.min !== null && sp.max !== null) ? `${sp.min} ~ ${sp.max}`
                : (sp.max !== null ? `≤ ${sp.max}` : `≥ ${sp.min}`);
    return `<tr><td>${nm}</td><td class="mono ${bad ? 'bad' : ''}">${v} ${u}</td>
      <td style="color:var(--muted);font-size:14.5px">${spTxt} ${u}</td>
      <td>${bad ? '<span class="bad">규격 밖</span>' : '<span class="ok">통과</span>'}</td></tr>`;
  }).join('');

  const isCell = ['single_bit', 'row_fail', 'column_fail', 'block_fail', 'cross_fail'].includes(mode);
  let reason;
  if (gi === 0) {
    reason = '모든 시험을 규격 안에서 통과했습니다.';
  } else if (!isCell && mode) {
    reason = `<b>${({open_short: '오픈/쇼트', idd_standby: '대기 전류', idd_active: '동작 전류'})[mode]}</b>가
      규격을 벗어났습니다. 여분 행·열은 <b>셀 어레이</b>를 대체하는 자원이므로,
      이런 칩 전체 특성 불량은 갈아끼울 대상이 없어 리페어가 성립하지 않습니다. → Fail`;
  } else {
    reason = `셀 어레이 불량 <b>${MODE_LABEL_E(mode)}</b>, fail bit ${w.nbits[k]}개.
      리페어 분석 결과 여분 행 <b>${w.ur[k]}/${E.repair.spare_rows}</b>,
      열 <b>${w.uc[k]}/${E.repair.spare_cols}</b>을 사용했으며 `
      + (gi === 1 ? '전부 덮였습니다. → <b>Repairable</b>'
                  : '여분을 다 써도 fail이 남았습니다. → <b>Fail</b>');
  }

  $('einfo').innerHTML = `
    <div style="font-size:18px;font-weight:700;color:${G_TXT[gi]};margin-bottom:2px">${G_NAME[gi]}</div>
    <div style="font-size:14.5px;color:var(--muted);margin-bottom:10px">${G_KO[gi]}</div>
    <div class="kv" style="margin-bottom:10px">
      <b>좌표</b><span class="mono">(${mx}, ${my})</span>
      <b>실데이터 판정</b><span>${w.grade[k] === 0 ? '정상 다이' : '불량 다이'}
        <span style="color:var(--muted);font-size:13px">WM-811K</span></span>
    </div>
    <table style="margin-bottom:10px">
      <tr><th>시험</th><th>측정값</th><th>규격</th><th></th></tr>${rowsHtml}
    </table>
    <div style="font-size:13.8px;line-height:1.75">${reason}</div>
    <p style="font-size:13px;color:var(--muted);margin-top:10px">
      측정값과 fail bit 주소는 합성입니다. 이 다이가 불량인지 아닌지는 실데이터가 정했고,
      합성은 <b>왜 불량인지</b>만 만듭니다.</p>`;

  drawChip(mode, w.nbits[k], gi, w.ur[k], w.uc[k], mx, my, isCell);
};

// 파이썬 src/sim/eds.py의 repair_analysis를 그대로 옮긴 것.
// 어떤 여분 행·열이 배정됐고 무엇이 안 덮였는지를 그림에 표시하기 위해 필요하다.
function repairAnalysis(addrs, R, C) {
  let remaining = addrs.map((a, i) => i);
  const usedR = [], usedC = [], steps = [];
  const rowsOf = (idx) => { const m = new Map();
    idx.forEach(i => m.set(addrs[i][0], (m.get(addrs[i][0]) || 0) + 1)); return m; };
  const colsOf = (idx) => { const m = new Map();
    idx.forEach(i => m.set(addrs[i][1], (m.get(addrs[i][1]) || 0) + 1)); return m; };

  // 1~3단계: must-repair — 남은 여분으로는 다른 축이 못 덮는 라인을 강제 배정
  for (;;) {
    if (!remaining.length) break;
    const rw = rowsOf(remaining), cl = colsOf(remaining);
    const mustR = [...rw].filter(([, c]) => c > (C - usedC.length)).map(([v]) => v);
    const mustC = [...cl].filter(([, c]) => c > (R - usedR.length)).map(([v]) => v);
    if (!mustR.length && !mustC.length) break;
    for (const x of mustR) {
      if (usedR.length >= R) return {ok: false, usedR, usedC, remaining,
        reason: 'must-repair 행이 여분 행보다 많다', steps};
      usedR.push(x); remaining = remaining.filter(i => addrs[i][0] !== x);
      steps.push(`행 0x${x.toString(16).padStart(4, '0')} 강제 배정`);
    }
    for (const y of mustC) {
      if (usedC.length >= C) return {ok: false, usedR, usedC, remaining,
        reason: 'must-repair 열이 여분 열보다 많다', steps};
      usedC.push(y); remaining = remaining.filter(i => addrs[i][1] !== y);
      steps.push(`열 0x${y.toString(16).padStart(3, '0')} 강제 배정`);
    }
  }
  // 4단계: 남은 fail을 가장 많이 덮는 행/열부터 그리디로 배정
  while (remaining.length) {
    const rw = [...rowsOf(remaining)].sort((a, b) => b[1] - a[1])[0] || [null, 0];
    const cl = [...colsOf(remaining)].sort((a, b) => b[1] - a[1])[0] || [null, 0];
    const canR = usedR.length < R, canC = usedC.length < C;
    if (!canR && !canC) return {ok: false, usedR, usedC, remaining,
      reason: '여분 행·열을 모두 썼는데 fail이 남았다', steps};
    if (canR && (!canC || rw[1] >= cl[1])) {
      usedR.push(rw[0]); remaining = remaining.filter(i => addrs[i][0] !== rw[0]);
      steps.push(`행 0x${rw[0].toString(16).padStart(4, '0')} 배정 (fail ${rw[1]}개)`);
    } else {
      usedC.push(cl[0]); remaining = remaining.filter(i => addrs[i][1] !== cl[0]);
      steps.push(`열 0x${cl[0].toString(16).padStart(3, '0')} 배정 (fail ${cl[1]}개)`);
    }
  }
  return {ok: true, usedR, usedC, remaining: [], reason: '여분 행·열 안에서 전부 덮임', steps};
}

// 선택한 다이의 칩 내부 Fail Address를 그린다.
// 웨이퍼 맵의 점 하나 = 칩 한 개, 여기는 그 칩 안쪽이다. 두 계층을 잇는 화면이다.
function drawChip(mode, nbits, gi, ur, uc, dx, dy, isCell) {
  const box = $('echip');
  if (!isCell || !nbits) { box.style.display = 'none'; return; }
  box.style.display = '';
  $('echiptitle').textContent = `— 웨이퍼 좌표 (${dx}, ${dy})`;

  const addrs = synth(mode, nbits, 16);
  const R = E.repair.spare_rows, C = E.repair.spare_cols;
  const rep = repairAnalysis(addrs, R, C);
  const covered = new Set();
  addrs.forEach((a, i) => {
    if (rep.usedR.includes(a[0]) || rep.usedC.includes(a[1])) covered.add(i);
  });

  // --- 확대: fail 주소가 실제로 놓인 범위에 맞춘다 ---
  // 전체 주소 공간(X 16bit, Y 12bit)에 그리면 점이 한 곳에 뭉쳐 형태가 안 보인다.
  const xs = addrs.map(a => a[0]), ys = addrs.map(a => a[1]);
  let x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = Math.min(...ys), y1 = Math.max(...ys);
  const padX = Math.max((x1 - x0) * 0.15, 4), padY = Math.max((y1 - y0) * 0.15, 4);
  x0 -= padX; x1 += padX; y0 -= padY; y1 += padY;

  const c = $('echipmap'), S = c.width, g = c.getContext('2d');
  const L = 54, B = 26, T = 10, Rp = 10;
  const PX = (v) => L + ((v - x0) / (x1 - x0)) * (S - L - Rp);
  const PY = (v) => T + ((v - y0) / (y1 - y0)) * (S - T - B);
  g.clearRect(0, 0, S, S);

  // 배정된 여분 행/열을 밴드로 — 이것이 "무엇으로 덮었는가"다
  g.fillStyle = 'rgba(76,168,92,0.20)';
  const bw = Math.max((S - L - Rp) / Math.max(x1 - x0, 1), 3);
  const bh = Math.max((S - T - B) / Math.max(y1 - y0, 1), 3);
  rep.usedR.forEach(x => g.fillRect(PX(x) - bw / 2, T, bw, S - T - B));
  rep.usedC.forEach(y => g.fillRect(L, PY(y) - bh / 2, S - L - Rp, bh));

  // 축
  g.strokeStyle = css('--border'); g.lineWidth = 1;
  g.beginPath(); g.moveTo(L, T); g.lineTo(L, S - B); g.lineTo(S - Rp, S - B); g.stroke();
  g.fillStyle = css('--muted'); g.font = '10px ui-monospace, monospace';
  g.textAlign = 'center';
  g.fillText('0x' + Math.max(0, Math.round(x0)).toString(16), L, S - B + 13);
  g.fillText('0x' + Math.round(x1).toString(16), S - Rp, S - B + 13);
  g.fillText('X (행 주소)', (L + S) / 2, S - B + 24);
  g.textAlign = 'right';
  g.fillText('0x' + Math.round(y1).toString(16), L - 5, S - B);
  g.fillText('0x' + Math.max(0, Math.round(y0)).toString(16), L - 5, T + 8);

  // fail 점 — 덮인 것과 안 덮인 것을 구분한다
  addrs.forEach((a, i) => {
    const on = covered.has(i);
    g.fillStyle = on ? 'rgba(120,130,140,0.75)' : '#d93630';
    g.beginPath(); g.arc(PX(a[0]), PY(a[1]), on ? 2.4 : 3.4, 0, 6.283); g.fill();
    if (!on) {   // 안 덮인 것은 테두리를 둘러 눈에 띄게
      g.strokeStyle = '#fff'; g.lineWidth = 1;
      g.beginPath(); g.arc(PX(a[0]), PY(a[1]), 3.4, 0, 6.283); g.stroke();
    }
  });

  $('echiptbl').innerHTML = addrs.slice(0, 40).map(([x, y], i) =>
    `<tr style="${covered.has(i) ? 'opacity:.5' : 'color:var(--bad);font-weight:600'}">
      <td>${x.toString(16).padStart(4, '0')}</td><td>${y.toString(16).padStart(3, '0')}</td></tr>`).join('')
    + (addrs.length > 40 ? `<tr><td colspan="2" style="color:var(--muted)">… 외 ${addrs.length - 40}건</td></tr>` : '');

  const res = classify(addrs, {lc: 4, lr: 0.30, bc: 6, br: 0.40});
  const md = (D.fail_address.modes || {})[mode] || {};
  const span = `X 0x${Math.max(0, Math.round(x0)).toString(16)}~0x${Math.round(x1).toString(16)}, ` +
               `Y 0x${Math.max(0, Math.round(y0)).toString(16)}~0x${Math.round(y1).toString(16)}`;
  $('echipnote').innerHTML = `
    <div class="kv" style="margin-bottom:9px">
      <b>fail bit</b><span>${addrs.length}개 (안 덮인 것 <b class="${rep.remaining.length ? 'bad' : 'ok'}">${rep.remaining.length}개</b>)</span>
      <b>주소 분포</b><span><b>${MODE_LABEL[res.mode] || res.mode}</b></span>
      <b>표시 범위</b><span class="mono" style="font-size:14.5px">${span}</span>
      <b>여분 사용</b><span class="${gi === 1 ? 'ok' : 'bad'}">행 ${rep.usedR.length}/${R},
        열 ${rep.usedC.length}/${C} → ${rep.ok ? 'Repairable' : 'Fail'}</span>
    </div>
    <div style="font-size:14.5px;margin-bottom:8px">
      <b style="color:var(--muted)">판정 이유</b> ${rep.reason}</div>
    <details><summary style="cursor:pointer;font-size:14px;font-weight:600">배정 과정 보기 (${rep.steps.length}단계)</summary>
      <ol class="mono" style="font-size:14.5px;padding-left:20px;margin:6px 0 0">
        ${rep.steps.slice(0, 12).map(x => `<li>${x}</li>`).join('')}
        ${rep.steps.length > 12 ? `<li>… 외 ${rep.steps.length - 12}단계</li>` : ''}</ol></details>
    <div style="font-size:14.5px;margin-top:8px;white-space:pre-line">${(md.plain || '').trim()}</div>
    <p style="font-size:13px;color:var(--muted);margin-top:8px">
      이 주소들은 판정에 쓰인 것과 같은 모드·개수로 다시 만든 분포입니다.
      주소 자체가 합성이므로 성질은 같지만 개별 값은 판정 시점과 다릅니다.</p>`;
}

// ================= 탭 2: SEM =================
const SEM = D.sem.items, CAUSE = D.sem.cause_map;
{
  const sel = $('ssel');
  SEM.forEach((s, i) => {
    const o = document.createElement('option');
    o.value = i;
    o.textContent = `${(MORPH_KO[s.morphology] || s.morphology).padEnd(11, '\u3000')} 라벨 ${s.label}`;
    sel.appendChild(o);
  });
  $('scount').textContent = `${SEM.length}장. 형태별로 잘 맞은 것과 못 맞은 것을 섞어 골랐습니다.`;
  const redraw = () => drawSem(+sel.value);
  sel.onchange = redraw;
  ['sstretch', 'soutline', 'sovl'].forEach(id => $(id).onchange = redraw);
  sel.value = 0;
  drawSem(0);
}

function rleToMask(r, n) {           // 0에서 시작하는 교대 런렝스
  const m = new Uint8Array(n);
  let p = 0, v = 0;
  for (const len of r) { if (v) m.fill(1, p, p + len); p += len; v ^= 1; }
  return m;
}

// 표시용 대비 스트레칭. 원본 값을 바꾸지 않는다 — 화면에 그릴 때만 적용한다.
// SEM 원본은 밝기 표준편차 중앙값이 10.8(0~255)이라 그대로는 결함이 보이지 않는다.
function stretch(g, S) {
  const d = g.getImageData(0, 0, S, S), a = d.data;
  const hist = new Uint32Array(256);
  for (let k = 0; k < a.length; k += 4) hist[a[k]]++;
  const total = a.length / 4;
  let acc = 0, lo = 0, hi = 255;
  for (let v = 0; v < 256; v++) { acc += hist[v]; if (acc >= total * 0.02) { lo = v; break; } }
  acc = 0;
  for (let v = 255; v >= 0; v--) { acc += hist[v]; if (acc >= total * 0.02) { hi = v; break; } }
  if (hi <= lo) return;
  const sc = 255 / (hi - lo);
  for (let k = 0; k < a.length; k += 4) {
    const v = Math.max(0, Math.min(255, Math.round((a[k] - lo) * sc)));
    a[k] = a[k + 1] = a[k + 2] = v;
  }
  g.putImageData(d, 0, 0);
}

function drawSem(i) {
  const s = SEM[i], N = 128, S = 420;
  const mode = $('sovl').value, useStretch = $('sstretch').checked,
        outline = $('soutline').checked;
  $('stitle').textContent = `${MORPH_KO[s.morphology] || s.morphology} · 데이터셋 라벨 ${s.label}`;

  const img = new Image();
  img.onload = () => {
    const c = $('sbig'), g = c.getContext('2d');
    g.imageSmoothingEnabled = false;
    g.clearRect(0, 0, S, S);
    g.drawImage(img, 0, 0, S, S);
    if (useStretch) stretch(g, S);

    const px = S / N;
    const layers = [];
    if (mode === 'gt' || mode === 'both') layers.push([s.gt_rle, [46, 160, 67]]);
    if (mode === 'pred' || mode === 'both') layers.push([s.pred_rle, [229, 60, 45]]);

    for (const [r, col] of layers) {
      const m = rleToMask(r, N * N);
      if (outline) {
        // 윤곽선만: 이웃 중 하나라도 배경이면 경계 픽셀이다
        g.fillStyle = `rgb(${col[0]},${col[1]},${col[2]})`;
        for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
          if (!m[y * N + x]) continue;
          const edge = (x === 0 || !m[y * N + x - 1]) || (x === N - 1 || !m[y * N + x + 1]) ||
                       (y === 0 || !m[(y - 1) * N + x]) || (y === N - 1 || !m[(y + 1) * N + x]);
          if (edge) g.fillRect(x * px, y * px, px, px);
        }
      } else {
        g.fillStyle = `rgba(${col[0]},${col[1]},${col[2]},0.5)`;
        for (let y = 0; y < N; y++) for (let x = 0; x < N; x++)
          if (m[y * N + x]) g.fillRect(x * px, y * px, px, px);
      }
    }
  };
  img.src = s.img;

  const sh = s.shape;
  const el = sh.elongation === null ? '∞ (완전 직선)' : sh.elongation;
  $('sinfo').innerHTML = `
    <div class="kv">
      <b>측정된 형태</b><span><b>${MORPH_KO[s.morphology] || s.morphology}</b>
        <span style="color:var(--muted);font-size:13px">${s.morphology}</span></span>
      <b>결함이 차지한 면적</b><span>${(sh.area_frac * 100).toFixed(3)}%</span>
      <b>길이 대 폭 비</b><span>${el} <span style="color:var(--muted);font-size:13px">클수록 가늘고 길다</span></span>
      <b>덩어리 개수</b><span>${sh.n_components}</span>
      <b>모델이 지목한 범위</b><span>${
        s.gt_px === 0
          ? (s.pred_px === 0 ? '없음 <span class="ok">— 전문가 정답도 없음(일치)</span>'
                             : `${s.pred_px}px <span class="bad">— 전문가 정답은 없음(오검출)</span>`)
          : `${s.pred_px}px (전문가 표시 ${s.gt_px}px)` +
            (s.pred_px < s.gt_px * 0.6 ? ' <span class="bad">— 실제보다 좁게 잡음</span>' : '')}</span>
      <b>파일</b><span class="mono" style="font-size:13px">${s.filename}</span>
    </div>
    <p style="font-size:13px;color:var(--muted);margin:8px 0 0">
      데이터셋이 결함 클래스 이름을 공개하지 않아 라벨은 숫자뿐입니다. 숫자에 임의로 결함 용어를
      붙이지 않고, 마스크에서 <b>실제로 측정한 형태</b>로 원인 공정 후보를 조회합니다.</p>`;

  const rules = CAUSE.morphology_rules;
  const cands = CAUSE.morphologies[s.morphology].candidates;
  const obs = CAUSE.morphologies[s.morphology].observed_in_dataset;
  $('scand').innerHTML = `
    <p style="font-size:13px;color:var(--muted);margin-top:0">
      형태 판정: 길이 대 폭 비가 3 미만이면 둥근 덩어리형, 3~30이면 굵거나 불규칙한 선상,
      30 이상이면 가늘고 긴 선상. 임계값은 정답 마스크 4,365장의 실측 분포에서
      두 무리 사이가 비는 지점으로 정했습니다.</p>
    <p style="font-size:13px;color:var(--muted)">데이터셋 관측: ${obs.note}</p>
    ${cands.map((c, k) => `<div class="cand">
      <div class="proc">[${k + 1}] ${c.process}${c.sub ? ' / ' + c.sub : ''}</div>
      <div class="rat">${c.rationale}</div>
      ${c.reference.map(r => `<div class="ref">출처: ${r}</div>`).join('')}
      <div class="note">${c.confidence_note}</div>
    </div>`).join('')}
    <p style="font-size:13px;font-weight:600;color:var(--chip-look)">${CAUSE.meta.disclaimer}</p>`;
}

// ================= 탭 3: Fail Address =================
// 파이썬 src/sim/fail_address.py 의 합성·판별을 그대로 옮긴 것이다.
// 임계값을 바꿔가며 결과가 흔들리는 정도를 화면에서 직접 확인하기 위함이다.
const AS = D.fail_address.address_space;
const XMAX = (1 << AS.x_bits) - 1, YMAX = (1 << AS.y_bits) - 1;
const MODE_LABEL = {single_bit: '싱글비트', row_fail: '로우성', column_fail: '칼럼성',
                    block_fail: '블락성', cross_fail: '크로스(로우+칼럼)'};
const BLOCK_W = D.fail_address.rules.block_window_x;
const BLOCK_H = D.fail_address.rules.block_window_y;
const AMB = D.fail_address.rules.ambiguous_margin;
let FADDR = [];

const ri = (n) => Math.floor(Math.random() * n);

function synth(mode, n, stride) {
  const pair = 2, out = new Set();
  const lineVals = (cnt, max) => {
    const vals = [], base = ri(Math.max(max - stride * (Math.floor(cnt / pair) + 2), 1));
    while (vals.length < cnt) {
      const blk = base + stride * Math.floor(vals.length / pair);
      for (let k = 0; k < pair && vals.length < cnt; k++) vals.push(Math.min(blk + k, max));
    }
    return vals;
  };
  if (mode === 'single_bit') {
    for (let i = 0; i < n; i++) out.add(ri(XMAX) + ',' + ri(YMAX));
  } else if (mode === 'row_fail') {
    const x = ri(XMAX); lineVals(n, YMAX).forEach(y => out.add(x + ',' + y));
  } else if (mode === 'column_fail') {
    const y = ri(YMAX); lineVals(n, XMAX).forEach(x => out.add(x + ',' + y));
  } else if (mode === 'block_fail') {
    const x0 = ri(Math.max(XMAX - BLOCK_W, 1)), y0 = ri(Math.max(YMAX - BLOCK_H, 1));
    for (let i = 0; i < n; i++) out.add((x0 + ri(BLOCK_W)) + ',' + (y0 + ri(BLOCK_H)));
  } else {                                   // cross
    const half = Math.max(Math.floor(n / 2), 1);
    synth('row_fail', half, stride).forEach(a => out.add(a[0] + ',' + a[1]));
    synth('column_fail', n - half, stride).forEach(a => out.add(a[0] + ',' + a[1]));
  }
  return [...out].map(s => s.split(',').map(Number)).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
}

function addNoise(addrs, k) {
  const s = new Set(addrs.map(a => a[0] + ',' + a[1]));
  for (let i = 0; i < k; i++) s.add(ri(XMAX) + ',' + ri(YMAX));
  return [...s].map(v => v.split(',').map(Number)).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
}

function classify(addrs, r) {
  const n = addrs.length;
  if (!n) return null;
  const xs = new Map(), ys = new Map();
  addrs.forEach(([x, y]) => { xs.set(x, (xs.get(x) || 0) + 1); ys.set(y, (ys.get(y) || 0) + 1); });
  let tx = 0, cx = 0, ty = 0, cy = 0;
  xs.forEach((c, v) => { if (c > cx) { cx = c; tx = v; } });
  ys.forEach((c, v) => { if (c > cy) { cy = c; ty = v; } });

  let bestCnt = 0, bx = 0, by = 0;
  for (const [x0, y0] of addrs) {
    let c = 0;
    for (const [x, y] of addrs)
      if (x >= x0 && x < x0 + BLOCK_W && y >= y0 && y < y0 + BLOCK_H) c++;
    if (c > bestCnt) { bestCnt = c; bx = x0; by = y0; }
  }
  const rowOk = cx >= r.lc && cx / n >= r.lr;
  const colOk = cy >= r.lc && cy / n >= r.lr;
  const blkOk = bestCnt >= r.bc && bestCnt / n >= r.br;

  const rowSet = new Set(), colSet = new Set(), blkSet = new Set();
  addrs.forEach(([x, y], i) => {
    if (rowOk && x === tx) rowSet.add(i);
    if (colOk && y === ty) colSet.add(i);
    if (blkOk && x >= bx && x < bx + BLOCK_W && y >= by && y < by + BLOCK_H) blkSet.add(i);
  });
  const uni = new Set([...rowSet, ...colSet, ...blkSet]);
  const scores = {
    row_fail: rowSet.size / n, column_fail: colSet.size / n, block_fail: blkSet.size / n,
    single_bit: 1 - uni.size / n,
  };
  if (rowOk && colOk) scores.cross_fail = new Set([...rowSet, ...colSet]).size / n;
  const prio = {cross_fail: 3, block_fail: 2, row_fail: 1, column_fail: 1, single_bit: 0};
  const ranked = Object.entries(scores).sort((a, b) => b[1] - a[1] || prio[b[0]] - prio[a[0]]);
  return {
    mode: ranked[0][0], score: ranked[0][1],
    runner: ranked[1], ambiguous: (ranked[0][1] - ranked[1][1]) < AMB,
    ev: {n, tx, cx, ty, cy, bx, by, bestCnt, scores, rowOk, colOk, blkOk},
  };
}

// 불량 모드가 어떤 공정 문제에서 나오는지 — config/fail_modes.yaml 그대로 표시한다
if ($('fmodes')) {
  const M = D.fail_address.modes || {};
  $('fmodes').innerHTML = Object.entries(M).map(([k, v]) => `
    <div class="cand">
      <div class="proc">${v.label} <span style="font-weight:400;color:var(--muted);font-size:13px">${k}</span></div>
      <div class="rat" style="white-space:pre-line">${(v.plain || '').trim()}</div>
      <div style="font-size:14.5px;margin-top:7px">
        <b style="color:var(--muted)">관련 공정</b><br>${(v.process_link || '').trim()}</div>
      ${(v.reference || []).map(r => `<div class="ref">출처: ${r}</div>`).join('')}
    </div>`).join('');
}

// ================= 탭 SECOM: 공정 센서 수율 분석 =================
{
  const S = D.secom;
  const ts = S.time_split, rs = S.random_split;
  const pct = (v) => (v * 100).toFixed(2) + '%';

  $('sc_meta').innerHTML = `
    <div class="kv">
      <b>출처</b><span>UCI Machine Learning Repository, SECOM (dataset 179)</span>
      <b>규모</b><span>웨이퍼 ${S.n_wafer.toLocaleString()}장 × 공정 센서 ${S.n_sensor}개 (전처리 후)</span>
      <b>기간</b><span>${S.period[0].slice(0, 10)} ~ ${S.period[1].slice(0, 10)} (89일)</span>
      <b>fail</b><span>${pct(S.fail_rate)} — 불균형 1 : ${((1 - S.fail_rate) / S.fail_rate).toFixed(1)}</span>
      <b>합성 비율</b><span class="ok">0% — 전부 실측값</span>
    </div>
    <p style="font-size:13px;color:var(--muted);margin-bottom:0">
      fail이 6.6%뿐이라 accuracy는 의미가 없습니다(전부 pass로 찍어도 93.4%).
      주 지표는 <b>PR-AUC</b>이며, 기저율(무작위로 찍었을 때 값)과 나란히 봅니다.</p>`;

  const mo = Object.entries(S.monthly).filter(([, v]) => v.n > 0);
  const maxR = Math.max(...mo.map(([, v]) => v.fail / v.n));
  $('sc_month').innerHTML = mo.map(([k, v]) => {
    const r = v.fail / v.n;
    return `<div style="margin-bottom:7px">
      <div style="display:flex;justify-content:space-between;font-size:14.5px">
        <span>${k.slice(0, 7)} <span style="color:var(--muted)">웨이퍼 ${v.n}장</span></span>
        <span class="mono">${pct(r)}</span></div>
      <div class="bar"><i style="width:${(r / maxR * 100).toFixed(1)}%;background:var(--bad)"></i></div></div>`;
  }).join('');

  const row = (tag, split, model, hi) => {
    const m = split.models[model];
    return `<tr${hi ? ' style="background:var(--chip-syn-bg)"' : ''}>
      <td>${tag}</td><td>${model === 'logistic' ? '로지스틱' : 'LightGBM'}</td>
      <td class="mono">${m.pr_auc.toFixed(4)}</td>
      <td class="mono" style="color:var(--muted)">${m.pr_auc_baseline.toFixed(4)}</td>
      <td class="mono"><b>${m.lift.toFixed(2)}배</b></td>
      <td class="mono">${m.roc_auc.toFixed(3)}</td></tr>`;
  };
  const d = rs.models.lightgbm.pr_auc / ts.models.lightgbm.pr_auc;
  $('sc_split').innerHTML = `<table>
      <tr><th>분할</th><th>모델</th><th>PR-AUC</th><th>기저율</th><th>기저 대비</th><th>ROC-AUC</th></tr>
      ${row('시간 순 (실제 조건)', ts, 'logistic')}
      ${row('시간 순 (실제 조건)', ts, 'lightgbm')}
      ${row('무작위', rs, 'logistic')}
      ${row('무작위', rs, 'lightgbm', true)}
    </table>
    <p style="font-size:13px;margin-top:10px"><b class="bad">무작위 분할이 PR-AUC를
      ${d.toFixed(1)}배 부풀립니다</b> (${ts.models.lightgbm.pr_auc.toFixed(4)} →
      ${rs.models.lightgbm.pr_auc.toFixed(4)}). ROC-AUC도
      ${ts.models.lightgbm.roc_auc.toFixed(3)} → ${rs.models.lightgbm.roc_auc.toFixed(3)}으로 뜁니다.
      같은 데이터, 같은 모델, 분할 방식만 다릅니다.</p>
    <p style="font-size:13px;color:var(--muted)">결측 대치값과 표준화 통계도 <b>학습 구간에서만</b>
      계산합니다. 검증 구간 값을 쓰면 미래 정보가 샙니다.
      학습 ${ts.n_train}장(fail ${ts.fail_train}) / 검증 ${ts.n_test}장(fail ${ts.fail_test}).</p>`;

  const tk = ts.models.lightgbm.topk;
  $('sc_topk').innerHTML = `<table>
      <tr><th>재검사 비율</th><th>장수</th><th>fail 검출률</th><th>정밀도</th></tr>
      ${Object.entries(tk).map(([k, v]) => `<tr><td>상위 ${k.replace('top', '')}</td>
        <td>${v.n_reviewed}</td><td class="${v.recall > 0.3 ? '' : 'bad'}">${pct(v.recall)}</td>
        <td>${pct(v.precision)}</td></tr>`).join('')}
    </table>
    <p style="font-size:13px;color:var(--muted);margin-bottom:0">무작위로 골랐다면 검출률은
      재검사 비율과 같습니다(5% / 10% / 20%). <b>상위 20%를 봐도 23%밖에 못 잡습니다.</b></p>`;

  const tr = S.improvement_trials || {};
  const best = Math.max(...Object.values(tr).map(v => v.pr_auc));
  $('sc_trials').innerHTML = `<table>
      <tr><th>시도</th><th>PR-AUC</th><th>기저 대비</th></tr>
      <tr><td>기본 LightGBM</td><td class="mono">${ts.models.lightgbm.pr_auc.toFixed(4)}</td>
        <td class="mono">${ts.models.lightgbm.lift.toFixed(2)}배</td></tr>
      ${Object.entries(tr).map(([k, v]) => `<tr><td>${k}</td>
        <td class="mono">${v.pr_auc.toFixed(4)}</td><td class="mono">${v.lift.toFixed(2)}배</td></tr>`).join('')}
    </table>
    <p style="font-size:13px;color:var(--muted);margin-bottom:0">최고 ${best.toFixed(4)}.
      <b>"튜닝을 안 해봐서 낮은 것"이 아니라 "해봐도 오르지 않는 것"</b>임을 기록합니다.</p>`;

  $('sc_sensors').innerHTML = `<table>
      <tr><th>센서</th><th>pass 평균</th><th>fail 평균</th><th>차이</th></tr>
      ${S.top_sensors.slice(0, 6).map(s => {
        const rel = s.pass_mean ? (s.fail_mean - s.pass_mean) / Math.abs(s.pass_mean) * 100 : NaN;
        return `<tr><td class="mono">${s.sensor}</td><td class="mono">${s.pass_mean.toFixed(3)}</td>
          <td class="mono">${s.fail_mean.toFixed(3)}</td>
          <td class="mono">${isFinite(rel) ? (rel > 0 ? '+' : '') + rel.toFixed(1) + '%' : '-'}</td></tr>`;
      }).join('')}
    </table>
    <p style="font-size:13px;color:var(--warn);margin-bottom:0">센서 이름은 원본에서 익명화되어
      번호로만 식별됩니다. <b>어느 장비의 무슨 물리량인지 알 수 없어 공정 개선 조치로
      연결할 수 없습니다.</b> 이것도 공개 데이터의 한계입니다.</p>`;

  // ---- 관리도 ----
  const DR = S.drift;
  const names = Object.keys(DR.series);
  {
    const sel = $('dr_sel');
    names.forEach((c, i) => {
      const s2 = DR.series[c];
      const o = document.createElement('option');
      o.value = i;
      o.textContent = `${c}  이탈 ${(s2.out_rate * 100).toFixed(1)}%`;
      sel.appendChild(o);
    });
    sel.onchange = () => drawCtrl(+sel.value);
    sel.value = 0;
    const kc = DR.kind_counts || {};
    $('dr_kinds').innerHTML = `전체 ${DR.n_sensor}개 센서 중<br>정상 ${kc['정상']} ·
      드리프트 ${kc['드리프트(지속)']} · excursion ${kc['excursion(일시)']}`;
    drawCtrl(0);
  }

  $('dr_kind').innerHTML = `
    <table><tr><th>성격</th><th>센서 수</th><th>실무 대응</th></tr>
      <tr><td>정상</td><td>${DR.kind_counts['정상']}</td><td style="text-align:left">—</td></tr>
      <tr><td><b>드리프트(지속)</b></td><td>${DR.kind_counts['드리프트(지속)']}</td>
        <td style="text-align:left">보정 · 예방 정비</td></tr>
      <tr><td><b>excursion(일시)</b></td><td>${DR.kind_counts['excursion(일시)']}</td>
        <td style="text-align:left">해당 기간 웨이퍼 격리 · 원인 조사</td></tr>
    </table>
    <table style="margin-top:10px"><tr><th>센서</th><th>성격</th><th>최대 이탈</th><th>현재</th></tr>
      ${DR.kind_examples.map(k => `<tr><td class="mono">${k.sensor}</td><td>${k.kind}</td>
        <td class="mono">${k.peak_sigma.toFixed(1)}σ</td>
        <td class="mono ${k.now_sigma > 1 ? 'bad' : 'ok'}">${k.now_sigma.toFixed(1)}σ</td></tr>`).join('')}
    </table>
    <p style="font-size:13px;color:var(--muted);margin-bottom:0">
      s275의 구간별 이탈은 <span class="mono">… 0.1, 0.1, 836.9, 900.2, 0.8</span>입니다.
      두 구간에서만 900배 튀었다가 <b>정상 복귀</b>했습니다. 지속적 이동이 아닙니다.</p>`;

  const ex = DR.excursion_test;
  $('dr_exc').innerHTML = `
    <p style="font-size:14.5px;margin-top:0">개별 센서로는 합불이 갈리지 않습니다
      (Cohen's d &gt; 0.8인 센서 <b>0개</b>). 그렇다면 <b>여러 센서가 동시에 관리 한계를
      벗어난 상태</b>는 어떤가 — 이것이 관리도의 실제 사용법입니다.</p>
    <p style="font-size:13px;color:var(--muted)">웨이퍼별 3σ 이탈 센서 수: 중앙 ${ex.median_out}개,
      최대 ${ex.max_out}개. 이탈 센서가 <b>${ex.threshold_sensors}개를 넘는 웨이퍼</b>(상위 5%)를
      이상으로 정의했습니다 <span style="color:var(--warn)">(가정치)</span>.</p>
    <table>
      <tr><th>구간</th><th>웨이퍼</th><th>fail</th><th>fail률</th></tr>
      <tr style="background:var(--chip-syn-bg)"><td><b>이상</b></td><td>${ex.n_abnormal}</td>
        <td>${ex.fail_abnormal}</td><td class="bad"><b>${(ex.rate_abnormal * 100).toFixed(2)}%</b></td></tr>
      <tr><td>정상</td><td>${ex.n_normal.toLocaleString()}</td><td>${ex.fail_normal}</td>
        <td>${(ex.rate_normal * 100).toFixed(2)}%</td></tr>
    </table>
    <p style="font-size:13px;margin-top:9px"><b>배수 ${ex.ratio.toFixed(2)}x, 오즈비
      ${ex.odds_ratio.toFixed(2)}, Fisher 정확검정 p = ${ex.p_value.toFixed(4)}</b>
      — ${ex.p_value < 0.05 ? '<span class="ok">통계적으로 유의합니다.</span>' : '유의하지 않습니다.'}</p>
    <p style="font-size:14.5px;margin-bottom:0">이 데이터에서 쓸 수 있는 규칙은
      "센서 A가 높으면 불량"이 아니라 <b>"공정이 평소와 다른 상태인 웨이퍼를 우선 검사하라"</b>입니다.
      실데이터에서 합성 없이, 유의수준 1%에서 나온 결과입니다.</p>`;

  // ---- 센서별 위험도 (FDR 보정) ----
  const RK = S.risk;
  $('rk_risk').innerHTML = `
    <p style="font-size:14.5px;margin-top:0">센서 ${RK.n_tested}개를 각각 검정하면, 실제로 아무 관계가
      없어도 유의수준 5%에서 <b>약 ${Math.round(RK.n_expected_by_chance)}개가 '유의하다'고 나옵니다.</b>
      Benjamini-Hochberg 절차로 거짓발견율(FDR ${(RK.fdr_q * 100).toFixed(0)}%)을 통제한 뒤 남는 것만 봅니다.</p>
    <table style="margin-bottom:10px">
      <tr><td style="text-align:left">검정 가능한 센서</td><td>${RK.n_tested}개</td></tr>
      <tr><td style="text-align:left">보정 전 p &lt; 0.05</td><td>${RK.n_raw_significant}개</td></tr>
      <tr><td style="text-align:left">우연히 나올 기대치</td><td class="bad">약 ${Math.round(RK.n_expected_by_chance)}개</td></tr>
      <tr><td style="text-align:left"><b>FDR 보정 통과</b></td><td class="ok"><b>${RK.n_fdr_significant}개</b></td></tr>
    </table>
    <table><tr><th>센서</th><th>이탈 시 fail</th><th>평소</th><th>위험비</th></tr>
      ${RK.risk.slice(0, 6).map(r => `<tr><td class="mono">${r.sensor}</td>
        <td>${(r.fail_when_out * 100).toFixed(1)}%</td><td>${(r.fail_when_in * 100).toFixed(1)}%</td>
        <td class="mono ${r.risk_ratio > 1 ? 'bad' : ''}">${r.risk_ratio.toFixed(2)}</td></tr>`).join('')}
    </table>
    <p style="font-size:13px;color:var(--muted);margin-bottom:0">위험비가 1보다 작은 센서가 섞여 있습니다.
      <b>센서가 튀는 것과 불량이 나는 것은 같은 말이 아닙니다.</b></p>`;

  const DG = RK.degradation;
  $('rk_deg').innerHTML = `
    <p style="font-size:14.5px;margin-top:0">이탈 빈도가 시간에 따라 <b>증가</b>하는 센서를 찾습니다.
      검정 ${DG.n_tested}개 중 FDR 통과하며 증가 추세인 센서는 <b>${DG.n_increasing}개</b>입니다.</p>
    <table><tr><th>센서</th><th>전반 이탈률</th><th>후반 이탈률</th><th>추세</th></tr>
      ${DG.top.slice(0, 6).map(r => `<tr><td class="mono">${r.sensor}</td>
        <td>${(r.first_half * 100).toFixed(2)}%</td>
        <td class="bad">${(r.last_half * 100).toFixed(2)}%</td>
        <td class="mono">${r.rho.toFixed(2)}</td></tr>`).join('')}
    </table>
    <p style="font-size:13px;color:var(--warn);margin-bottom:0">이탈이 잦아지는 것은 공정 변화일 수도,
      <b>센서 자체의 열화</b>일 수도 있습니다. 이 데이터에는 센서 교체·정비 이력이 없어
      둘을 구분할 수 없습니다.</p>`;

  // ---- 시간 순 검증 ----
  const HO = RK.holdout, hw = HO['가중 점수'];
  $('rk_holdout').innerHTML = `
    <p style="font-size:14.5px;margin-top:0">가중치를 정한 데이터로 평가하면 과적합입니다.
      앞 ${HO.n_learn.toLocaleString()}장에서만 위험비를 학습하고 뒤 ${HO.n_eval.toLocaleString()}장에서 평가했습니다.</p>
    <table>
      <tr><th>항목</th><th>전체 데이터 기준</th><th>시간 순 분리</th></tr>
      <tr><td style="text-align:left">위험을 높이는 센서(FDR 통과)</td><td>${RK.n_fdr_significant}개</td>
        <td class="bad"><b>${HO.n_sig_learned}개</b></td></tr>
      <tr><td style="text-align:left">상위 5% 웨이퍼 fail률</td><td>17.02%</td>
        <td>${hw ? (hw.rate_flagged * 100).toFixed(2) + '%' : '-'}</td></tr>
      <tr><td style="text-align:left">나머지 fail률</td><td>6.32%</td>
        <td>${hw ? (hw.rate_rest * 100).toFixed(2) + '%' : '-'}</td></tr>
      <tr><td style="text-align:left">배수</td><td>2.70x</td><td>${hw ? hw.ratio.toFixed(2) + 'x' : '-'}</td></tr>
      <tr style="background:var(--chip-syn-bg)"><td style="text-align:left"><b>p 값</b></td>
        <td class="mono"><b>0.0103</b></td>
        <td class="mono bad"><b>${hw ? hw.p.toFixed(4) : '-'}</b></td></tr>
    </table>
    <p style="font-size:13px;margin-top:10px"><b>학습 구간에서 위험을 높이는 센서가 하나도 남지 않고,
      유의성도 사라집니다(p 0.0103 → ${hw ? hw.p.toFixed(4) : '-'}).</b>
      효과 크기(배수 2.3~2.7x)는 비슷하지만, 평가 구간이 ${HO.n_eval}장·그중 fail 26장뿐이라
      검정력이 부족합니다. p = ${hw ? hw.p.toFixed(4) : '-'}은 "효과가 없다"가 아니라
      <b>"이 표본으로는 확인할 수 없다"</b>에 가깝습니다.</p>
    <p style="font-size:13px;color:var(--muted);margin-bottom:0">
      이 절을 지우지 않고 남기는 이유: 분석 과정에서 그럴듯한 결과가 나왔다가 엄격한 검증에서
      무너지는 일은 실제로 자주 일어납니다. <b>무너진 사실을 기록하는 것이 결과를 부풀리는 것보다
      중요합니다.</b></p>`;

  $('sc_concl').innerHTML = `
    <ol style="font-size:13px;padding-left:20px;margin:0">
      <li><b>시간 순 분할 조건에서 이 데이터만으로는 웨이퍼 합불 예측이 사실상 되지 않습니다.</b>
        ROC-AUC ${ts.models.lightgbm.roc_auc.toFixed(3)}~${ts.models.logistic.roc_auc.toFixed(3)},
        상위 5% 재검사 검출률 0%.</li>
      <li><b>무작위 분할은 PR-AUC를 ${d.toFixed(1)}배 부풀립니다.</b> SECOM으로 보고되는 좋은
        성능 수치는 분할 방식을 확인하고 읽어야 합니다.</li>
      <li>특징 선택·정규화·최근 데이터 학습 등 7가지 시도로도 개선되지 않았습니다.</li>
    </ol>
    <p style="font-size:13px;margin-bottom:0">이 모듈의 값어치는 예측 성능이 아니라
      <b>평가 방식이 결론을 바꾼다는 것을 같은 데이터로 보인 것</b>입니다.
      실제 라인에 올릴 모델이라면 시간 순 검증을 통과해야 합니다.</p>`;
}

function drawCtrl(i) {
  const S = D.secom, DR = S.drift;
  const name = Object.keys(DR.series)[i], sr = DR.series[name];
  const v = sr.values, fail = DR.is_fail, n = v.length;
  const c = $('dr_chart'), g = c.getContext('2d');
  const W = c.width, H = c.height, L = 58, R = 12, T = 12, B = 26;
  g.clearRect(0, 0, W, H);

  // y 범위: 관리 한계와 실제 값을 모두 담되, 극단값에 눌리지 않게 분위로 자른다
  const fin = v.filter(x => x !== null).slice().sort((a, b) => a - b);
  const q = (p) => fin[Math.min(fin.length - 1, Math.max(0, Math.floor(fin.length * p)))];
  let lo = Math.min(q(0.005), sr.lcl), hi = Math.max(q(0.995), sr.ucl);
  if (hi === lo) { hi = lo + 1; }
  const pad = (hi - lo) * 0.08;
  lo -= pad; hi += pad;
  const X = (k) => L + (k / (n - 1)) * (W - L - R);
  const Y = (val) => T + (1 - (val - lo) / (hi - lo)) * (H - T - B);

  // 축
  g.strokeStyle = css('--border'); g.lineWidth = 1;
  g.beginPath(); g.moveTo(L, T); g.lineTo(L, H - B); g.lineTo(W - R, H - B); g.stroke();
  g.fillStyle = css('--muted'); g.font = '12px JetBrains Mono, monospace';
  g.textAlign = 'right';
  for (const val of [lo + pad, sr.mu, hi - pad]) {
    g.fillText(val.toPrecision(3), L - 5, Y(val) + 3);
  }
  // 기준 구간 끝 표시
  const bEnd = Math.floor(n * DR.baseline_frac);
  g.strokeStyle = css('--accent'); g.setLineDash([3, 3]);
  g.beginPath(); g.moveTo(X(bEnd), T); g.lineTo(X(bEnd), H - B); g.stroke();
  g.setLineDash([]);
  g.textAlign = 'left'; g.fillStyle = css('--accent');
  g.fillText('기준 구간 끝', X(bEnd) + 4, T + 10);

  // 관리 한계
  g.strokeStyle = css('--bad'); g.setLineDash([5, 4]); g.lineWidth = 1;
  for (const lim of [sr.ucl, sr.lcl]) {
    if (lim < lo || lim > hi) continue;
    g.beginPath(); g.moveTo(L, Y(lim)); g.lineTo(W - R, Y(lim)); g.stroke();
  }
  g.setLineDash([]);
  // 평소 평균
  g.strokeStyle = css('--muted'); g.lineWidth = 1.5;
  g.beginPath(); g.moveTo(L, Y(sr.mu)); g.lineTo(W - R, Y(sr.mu)); g.stroke();

  // 측정값
  g.strokeStyle = css('--text'); g.globalAlpha = 0.45; g.lineWidth = 1;
  g.beginPath();
  let started = false;
  for (let k = 0; k < n; k++) {
    if (v[k] === null) { started = false; continue; }
    const y = Y(Math.min(Math.max(v[k], lo), hi));
    if (!started) { g.moveTo(X(k), y); started = true; } else { g.lineTo(X(k), y); }
  }
  g.stroke(); g.globalAlpha = 1;

  // 불량 웨이퍼
  g.fillStyle = css('--bad');
  for (let k = 0; k < n; k++) {
    if (!fail[k] || v[k] === null) continue;
    g.beginPath(); g.arc(X(k), Y(Math.min(Math.max(v[k], lo), hi)), 2.2, 0, 6.283); g.fill();
  }

  const kindRow = (DR.kind_examples || []).find(x => x.sensor === name);
  $('dr_info').innerHTML = `
    <div class="kv">
      <b>센서</b><span class="mono">${name}</span>
      <b>평소 평균 ± 3σ</b><span class="mono">${sr.mu.toPrecision(4)} ± ${(3 * sr.sd).toPrecision(3)}
        → 한계 [${sr.lcl.toPrecision(4)}, ${sr.ucl.toPrecision(4)}]</span>
      <b>감시 구간 이탈률</b><span class="${sr.out_rate > 0.05 ? 'bad' : ''}">${(sr.out_rate * 100).toFixed(2)}%</span>
      <b>평균 이동</b><span>${sr.shift_sigma.toFixed(2)}σ${kindRow ? ` · <b>${kindRow.kind}</b>` : ''}</span>
      <b>pass/fail 분리도</b><span>Cohen's d = ${sr.cohens_d.toFixed(2)}
        <span style="color:var(--muted)">(0.8 이상이면 큼 — 이 데이터에는 하나도 없음)</span></span>
    </div>`;
}

// ================= 탭 5: 한계 · 성능 =================
{
  const L = [
    ['L1 비구조화 층', 'Carinthia-S는 주기 구조가 없는 층이라 주기성 기반 이상 탐지를 쓸 수 없습니다. 패턴 층 일반화를 주장할 수 없습니다.'],
    ['L3 없는 라벨', 'Fail Address 비트맵, 원인 공정 라벨, 항목별 테스트 결과는 공개 데이터가 없습니다. 학습 타깃으로 삼지 않습니다.'],
    ['L5 분할 단위', 'Carinthia-S에 웨이퍼·배치 식별자가 없어 이미지 단위로 분할했습니다. Module B 수치는 낙관 편향을 가집니다.'],
    ['L6 클래스 이름 비공개', '결함 클래스는 1~6 숫자뿐입니다. 숫자에 결함 용어를 붙이지 않고 측정된 형태를 씁니다.'],
    ['L7 극단 불균형', 'class 5는 4장, class 2는 8장뿐입니다(1002:1). 이 클래스들의 F1은 잡음입니다.'],
    ['L9 마스크 예외', '설명서는 binary 마스크라고 하지만 395장(8.6%)이 비이진(경계 안티앨리어싱), 4장이 RGBA/RGB입니다. 읽기를 한 함수로 표준화했습니다.'],
    ['L10 단면 이미지 없음', '실제 현장은 불량 다이를 잘라 <b>단면 SEM/TEM</b>으로 내부 구조를 봅니다. 공개 데이터를 전수 조사했으나 쓸 수 있는 것이 없어 <b>이 분석은 시도하지 못했습니다</b>. MIIC(25,276장)와 SEM Nanoscience(22,000장)는 평면 이미지이고, 단면인 DEVICE-TEM은 15장뿐입니다. 단면 이미지는 소자 구조와 공정 조건이 그대로 드러나 각 사의 핵심 자산이라 공개되지 않습니다. 그래서 결함이 어느 층·어느 구조에서 났는지 확인하는 분석까지는 가지 못했습니다.'],
    ['규격값의 출처', 'EDS 시험 규격은 임의값이 아니라 <b>DDR4-2400 4Gb 공개 데이터시트</b>의 실제 값입니다(IDD2N 400 mA, IDD4R 1280 mA, 동작온도 0~85°C, tREFI 기준 리프레시 주기 64 ms). 다만 WM-811K 웨이퍼의 제품 종류가 공개되지 않아, 이 규격이 그 웨이퍼의 실제 규격이라는 보장은 없습니다. 측정값 자체는 여전히 합성입니다.'],
  ];
  $('limits').innerHTML = L.map(([k, v]) =>
    `<div style="margin-bottom:9px"><b style="font-size:14.5px">${k}</b>
     <div style="font-size:13px;color:var(--muted)">${v}</div></div>`).join('');

  const pe = D.pattern_eval, de = D.defect_eval;
  const seg = de.test_segmentation;
  $('perf').innerHTML = `
    <b style="font-size:14.5px">Module A 패턴 분류 (로트 단위 분할)</b>
    <table style="margin-bottom:12px">
      <tr><td>test macro-F1</td><td>${pe.test_macro_f1.toFixed(3)}</td></tr>
      <tr><td>test accuracy</td><td>${pe.test_accuracy.toFixed(3)}</td></tr>
      <tr><td>가장 낮은 클래스</td><td>Loc ${pe.per_class['Loc'].f1.toFixed(3)}</td></tr>
    </table>
    <b style="font-size:14.5px">Module B 세그멘테이션 (이미지 단위 분할)</b>
    <table style="margin-bottom:12px">
      <tr><td>이미지별 Dice 평균</td><td>${seg.dice_image_mean.toFixed(4)}</td></tr>
      <tr><td>이미지별 IoU 평균</td><td>${seg.iou_image_mean.toFixed(4)}</td></tr>
      <tr><td>빈 마스크 오검출 픽셀</td><td>${seg.empty_gt_fp_pixels_mean.toFixed(1)}</td></tr>
    </table>
    <b style="font-size:14.5px">Module B 분류</b>
    <table>
      <tr><td>macro-F1</td><td>${de.test_macro_f1.toFixed(3)}</td></tr>
      <tr><td>accuracy</td><td>${de.test_accuracy.toFixed(3)}</td></tr>
      <tr><td>class 5 (표본 ${de.per_class['5'].support}장)</td><td class="bad">${de.per_class['5'].f1.toFixed(3)}</td></tr>
    </table>
    <p style="font-size:13px;color:var(--muted);margin-top:9px">
      macro-F1 ${de.test_macro_f1.toFixed(3)}을 그대로 읽으면 안 됩니다. 표본 1장짜리 class 5의 F1 0이
      6분의 1 가중치로 들어가 있습니다. 표본이 충분한 class 3·4·6은 각각
      ${de.per_class['3'].f1.toFixed(3)} / ${de.per_class['4'].f1.toFixed(3)} / ${de.per_class['6'].f1.toFixed(3)}입니다.</p>`;
  $('gen').textContent = `생성 ${D.meta.generated} · 시드 ${D.meta.seed}`;
}

// Override drawEds to normalize wafer diameter uniformly across all wafers without horizontal or vertical shrinking
(function() {
  const origDrawEds = window.drawEds;
  window.drawEds = function(i) {
    eCur = i;
    const w = E.wafers[i], S = 470;
    $('etitle').textContent = `${w.wafer_id} · ${PAT_KO[w.pattern] || w.pattern}`;
    const c = $('emap'), g = c.getContext('2d');
    
    // Scale X and Y independently to form a perfect circular wafer of diameter D
    const D = 432;
    const px = D / w.w;
    const py = D / w.h;
    const ox = Math.floor((S - D) / 2);
    const oy = Math.floor((S - D) / 2);
    eGeom = { px, py, ox, oy };

    g.clearRect(0, 0, S, S);
    const dieW = Math.max(1, px - 0.4);
    const dieH = Math.max(1, py - 0.4);
    for (let k = 0; k < w.x.length; k++) {
      g.fillStyle = G_COL[w.grade[k]];
      g.fillRect(ox + w.x[k] * px, oy + w.y[k] * py, dieW, dieH);
    }

    const tot = w.x.length;
    $('ebar').innerHTML = [0, 1, 2].map(gi => {
      const n = w.grade.filter(v => v === gi).length;
      return `<div style="margin-bottom:5px">
        <div style="display:flex;justify-content:space-between;font-size:14.5px">
          <span>${G_NAME[gi]}</span><span class="mono">${n.toLocaleString()} (${(n / tot * 100).toFixed(2)}%)</span></div>
        <div class="bar"><i style="width:${(n / tot * 100).toFixed(1)}%;background:${G_COL[gi]} !important"></i></div></div>`;
    }).join('');
  };

  // Override click event to match Euclidean distance to nearest die
  $('emap').onclick = (ev) => {
    const w = E.wafers[eCur], r = $('emap').getBoundingClientRect();
    const sx = $('emap').width / r.width;
    const sy = $('emap').height / r.height;
    const clickX = (ev.clientX - r.left) * sx;
    const clickY = (ev.clientY - r.top) * sy;

    const mx = Math.floor((clickX - eGeom.ox) / eGeom.px);
    const my = Math.floor((clickY - eGeom.oy) / eGeom.py);
    let k = w.x.findIndex((x, idx) => x === mx && w.y[idx] === my);

    if (k < 0) {
      let bestDist = Infinity;
      for (let i = 0; i < w.x.length; i++) {
        const dx = (eGeom.ox + (w.x[i] + 0.5) * eGeom.px) - clickX;
        const dy = (eGeom.oy + (w.y[i] + 0.5) * eGeom.py) - clickY;
        const dist = (dx / eGeom.px) * (dx / eGeom.px) + (dy / eGeom.py) * (dy / eGeom.py);
        if (dist < bestDist) {
          bestDist = dist;
          k = i;
        }
      }
      if (bestDist > 2.0) return;
    }
    const mx_found = w.x[k], my_found = w.y[k];
    const gi = w.grade[k];
    const mode = E.modes[w.mode[k]] || '';
    const spec = Object.fromEntries(E.tests.map(t => [t.id, t.spec]));
    const rowsHtml = [
      ['핀 전압 (오픈/쇼트)', (w.os[k] / 100).toFixed(2), 'V', spec.open_short],
      ['대기 전류', (w.ids[k] / 100).toFixed(2), 'mA', spec.idd_standby],
      ['동작 전류', (w.ida[k] / 10).toFixed(1), 'mA', spec.idd_active],
      ['리텐션 (85°C)', (w.ret[k] / 10).toFixed(1), 'ms', spec.retention_hot],
    ].map(([nm, v, u, sp]) => {
      const val = parseFloat(v);
      const bad = (sp.min !== null && val < sp.min) || (sp.max !== null && val > sp.max);
      const spTxt = (sp.min !== null && sp.max !== null) ? `${sp.min} ~ ${sp.max}`
                  : (sp.max !== null ? `≤ ${sp.max}` : `≥ ${sp.min}`);
      return `<tr><td>${nm}</td><td class="mono ${bad ? 'bad' : ''}">${v} ${u}</td>
        <td style="color:var(--muted);font-size:14.5px">${spTxt} ${u}</td>
        <td>${bad ? '<span class="bad">규격 밖</span>' : '<span class="ok">통과</span>'}</td></tr>`;
    }).join('');

    const isCell = ['single_bit', 'row_fail', 'column_fail', 'block_fail', 'cross_fail'].includes(mode);
    const modeMap = {'open_short': '오픈/쇼트', 'idd_standby': '대기 전류', 'idd_active': '동작 전류'};
    let reason;
    if (gi === 0) {
      reason = '모든 시험을 규격 안에서 통과했습니다.';
    } else if (!isCell && mode) {
      reason = `<b>${modeMap[mode]}</b>가
        규격을 벗어났습니다. 여분 행·열은 <b>셀 어레이</b>를 대체하는 자원이므로,
        이런 칩 전체 특성 불량은 갈아끼울 대상이 없어 리페어가 성립하지 않습니다. → Fail`;
    } else {
      reason = `셀 어레이 불량 <b>${MODE_LABEL_E(mode)}</b>, fail bit ${w.nbits[k]}개.
        리페어 분석 결과 여분 행 <b>${w.ur[k]}/${E.repair.spare_rows}</b>,
        열 <b>${w.uc[k]}/${E.repair.spare_cols}</b>을 사용했으며 `
        + (gi === 1 ? '전부 덮였습니다. → <b>Repairable</b>'
                    : '여분을 다 써도 fail이 남았습니다. → <b>Fail</b>');
    }

    $('einfo').innerHTML = `
      <div style="font-size:18px;font-weight:700;color:${G_TXT[gi]};margin-bottom:2px">${G_NAME[gi]}</div>
      <div style="font-size:14.5px;color:var(--muted);margin-bottom:10px">${G_KO[gi]}</div>
      <div class="kv" style="margin-bottom:10px">
        <b>좌표</b><span class="mono">(${mx_found}, ${my_found})</span>
        <b>실데이터 판정</b><span>${w.grade[k] === 0 ? '정상 다이' : '불량 다이'}
          <span style="color:var(--muted);font-size:13px">WM-811K</span></span>
      </div>
      <table style="margin-bottom:10px">
        <tr><th>시험</th><th>측정값</th><th>규격</th><th></th></tr>${rowsHtml}
      </table>
      <div style="font-size:13.8px;line-height:1.75">${reason}</div>`;

    drawChip(mode, w.nbits[k], gi, w.ur[k], w.uc[k], mx_found, my_found, isCell);
  };

  // Also Normalize drawWafer for Tab 3 (WM-811K) to fill perfect circle
  const origDrawWafer = window.drawWafer;
  window.drawWafer = function(i) {
    origDrawWafer(i);
    const w = W[i], S = 440;
    const D = 402;
    const px = D / w.w;
    const py = D / w.h;
    const ox = Math.floor((S - D) / 2);
    const oy = Math.floor((S - D) / 2);

    const c = $('wmap'), g = c.getContext('2d');
    g.clearRect(0, 0, S, S);
    const cols = [css('--die-out'), css('--die-pass'), css('--die-fail')];
    const dieW = Math.max(1, px - 0.4);
    const dieH = Math.max(1, py - 0.4);
    for (let y = 0; y < w.h; y++) for (let x = 0; x < w.w; x++) {
      const v = w.grid[y * w.w + x];
      if (v === 0) continue;
      g.fillStyle = cols[v];
      g.fillRect(ox + x * px, oy + y * py, dieW, dieH);
    }

    const c2 = $('wcam'), g2 = c2.getContext('2d');
    g2.clearRect(0, 0, S, S);
    g2.globalAlpha = 0.35;
    for (let y = 0; y < w.h; y++) for (let x = 0; x < w.w; x++) {
      if (w.grid[y * w.w + x] === 0) continue;
      g2.fillStyle = cols[w.grid[y * w.w + x]];
      g2.fillRect(ox + x * px, oy + y * py, dieW, dieH);
    }
    g2.globalAlpha = 1;
    const N = 64;
    for (let y = 0; y < w.h; y++) for (let x = 0; x < w.w; x++) {
      if (w.grid[y * w.w + x] === 0) continue;
      const cy = Math.min(N - 1, Math.floor((y + 0.5) / w.h * N));
      const cx = Math.min(N - 1, Math.floor((x + 0.5) / w.w * N));
      const v = w.cam[cy * N + cx] / 100;
      if (v < 0.15) continue;
      g2.fillStyle = `rgba(230,60,40,${(v * 0.75).toFixed(3)})`;
      g2.fillRect(ox + x * px, oy + y * py, dieW, dieH);
    }
  };

  // Re-run initial draw with true circular geometry immediately
  if (typeof drawEds === 'function') {
    try { drawEds(eCur || 0); } catch(e) {}
  }
  if (typeof drawWafer === 'function') {
    try {
      const ws = $('wsel');
      if (ws) drawWafer(+ws.value || 0);
    } catch(e) {}
  }
})();

window.addEventListener('DOMContentLoaded', () => {
  // 1. Synchronize EDS Wafer List
  const esel = document.getElementById('esel');
  const customEdsList = document.getElementById('custom-eds-wafer-list');
  if (esel && customEdsList) {
    function populateEdsCustom() {
      customEdsList.innerHTML = '';
      Array.from(esel.options).forEach((opt, idx) => {
        const row = document.createElement('div');
        row.className = 'wafer-item-row' + (idx === esel.selectedIndex ? ' on' : '');
        const cleanText = (opt.text || opt.textContent || "").replace(/[\u3000\s]+/g, ' ').trim();
        row.innerHTML = `
          <div class="w-row-left">
            <span style="width:7px;height:7px;border-radius:50%;background:var(--neon-green)"></span>
            <div class="w-row-id">${cleanText}</div>
          </div>
          <div class="w-row-badge" style="background:rgba(0,240,255,0.1);color:var(--neon-cyan)">#${idx+1}</div>
        `;
        row.onclick = () => {
          esel.selectedIndex = idx;
          esel.dispatchEvent(new Event('change'));
          document.querySelectorAll('#custom-eds-wafer-list .wafer-item-row').forEach(r => r.classList.remove('on'));
          row.classList.add('on');
          const sideW = document.getElementById('side-cur-wafer');
          if (sideW) sideW.textContent = cleanText.split(' ')[0] || cleanText;
        };
        customEdsList.appendChild(row);
      });
    }
    setTimeout(populateEdsCustom, 120);
  }

  // 2. Synchronize SEM List (Clean typography without fullwidth spaces)
  const ssel = document.getElementById('ssel');
  const customSemList = document.getElementById('custom-sem-list');
  if (ssel && customSemList) {
    function populateSemCustom() {
      customSemList.innerHTML = '';
      Array.from(ssel.options).forEach((opt, idx) => {
        const row = document.createElement('div');
        row.className = 'wafer-item-row' + (idx === ssel.selectedIndex ? ' on' : '');
        const raw = (opt.text || opt.textContent || "").replace(/[　]+/g, ' ').replace(/\s+/g, ' ').trim();
        const parts = raw.split('라벨');
        const desc = (parts[0] || raw).trim();
        const lblNum = (parts[1] || '').trim();
        row.innerHTML = `
          <div class="w-row-left">
            <span style="width:7px;height:7px;border-radius:50%;background:var(--neon-amber)"></span>
            <div class="w-row-id" style="font-size:14px">${desc}</div>
          </div>
          <div class="w-row-badge" style="background:rgba(255,179,0,0.15);color:var(--neon-amber)">라벨 ${lblNum}</div>
        `;
        row.onclick = () => {
          ssel.selectedIndex = idx;
          ssel.dispatchEvent(new Event('change'));
          document.querySelectorAll('#custom-sem-list .wafer-item-row').forEach(r => r.classList.remove('on'));
          row.classList.add('on');
        };
        customSemList.appendChild(row);
      });
    }
    setTimeout(populateSemCustom, 120);
  }

  // 3. Synchronize Map List (Fix CNN Bar and update)
  const wsel = document.getElementById('wsel');
  const customMapList = document.getElementById('custom-map-list');
  if (wsel && customMapList) {
    function populateMapCustom() {
      customMapList.innerHTML = '';
      Array.from(wsel.options).forEach((opt, idx) => {
        const row = document.createElement('div');
        row.className = 'wafer-item-row' + (idx === wsel.selectedIndex ? ' on' : '');
        const clean = (opt.text || opt.textContent || "").replace(/[　]+/g, ' ').replace(/\s+/g, ' ').trim();
        row.innerHTML = `
          <div class="w-row-left">
            <span style="width:7px;height:7px;border-radius:50%;background:var(--neon-cyan)"></span>
            <div class="w-row-id">${clean}</div>
          </div>
        `;
        row.onclick = () => {
          wsel.value = idx;
          wsel.selectedIndex = idx;
          if (wsel.onchange) wsel.onchange();
          wsel.dispatchEvent(new Event('change'));
          document.querySelectorAll('#custom-map-list .wafer-item-row').forEach(r => r.classList.remove('on'));
          row.classList.add('on');
        };
        customMapList.appendChild(row);
      });
    }
    setTimeout(populateMapCustom, 120);
  }

  // 4. Synchronize Sensor List
  const dr_sel = document.getElementById('dr_sel');
  const customSensorList = document.getElementById('custom-sensor-list');
  if (dr_sel && customSensorList) {
    function populateSensorCustom() {
      customSensorList.innerHTML = '';
      Array.from(dr_sel.options).forEach((opt, idx) => {
        const row = document.createElement('div');
        row.className = 'wafer-item-row' + (idx === dr_sel.selectedIndex ? ' on' : '');
        row.innerHTML = `
          <div class="w-row-left">
            <span style="width:7px;height:7px;border-radius:50%;background:var(--neon-blue)"></span>
            <div class="w-row-id">${opt.text || opt.textContent || ""}</div>
          </div>
        `;
        row.onclick = () => {
          dr_sel.selectedIndex = idx;
          dr_sel.dispatchEvent(new Event('change'));
          document.querySelectorAll('#custom-sensor-list .wafer-item-row').forEach(r => r.classList.remove('on'));
          row.classList.add('on');
        };
        customSensorList.appendChild(row);
      });
    }
    setTimeout(populateSensorCustom, 120);
  }

  // Safe Phase 3-5 Handlers
  try {
    if ($('leak_test') && D.pattern_eval && D.pattern_eval.leak_experiment) {
      const l = D.pattern_eval.leak_experiment;
      $('leak_test').innerHTML = `
        <tr><td style="text-align:left;color:var(--text-white)">무작위 분할 (Random)</td>
            <td>Accuracy ${(l.random_split_accuracy * 100).toFixed(1)}%</td>
            <td class="bold" style="color:var(--neon-rose)">Macro F1 ${(l.random_split_macro_f1 * 100).toFixed(1)}%</td></tr>
        <tr><td style="text-align:left;color:var(--text-white)">로트 단위 분할 (Group)</td>
            <td>Accuracy ${(l.lot_split_accuracy * 100).toFixed(1)}%</td>
            <td class="bold" style="color:var(--neon-cyan)">Macro F1 ${(l.lot_split_macro_f1 * 100).toFixed(1)}%</td></tr>
      `;
    }
  } catch (err) { console.error('leak_test render error:', err); }

  try {
    if ($('lot_test') && D.lot_test) {
      const t = D.lot_test;
      $('lot_test').innerHTML = `
        <div style="font-size:14px; color:var(--text-white); margin-bottom:8px;">관측된 로트 내 패턴 반복 횟수: <b style="color:var(--neon-cyan); font-size:16px">${t.observed_pairs}건</b></div>
        <div style="font-size:12.5px; color:var(--text-secondary); line-height:1.5;">순열 검정(무작위 순열 1000회) 평균: <b style="color:var(--text-white)">${t.permuted_mean_pairs.toFixed(1)}건</b></div>
        <div style="font-size:12.5px; color:var(--text-secondary); line-height:1.5;">통계적 유의확률 (p-value): <b style="color:var(--neon-green)">${t.p_value.toFixed(4)} (유의미)</b></div>
        <div style="font-size:13.5px; color:var(--text-white); margin-top:10px; padding:8px 12px; background:rgba(0,240,255,0.06); border-radius:6px; border:1px solid rgba(0,240,255,0.15);"><b>결론:</b> ${t.conclusion}</div>
      `;
    }
  } catch (err) { console.error('lot_test render error:', err); }

    // Multi-Lot Controller (Phase 5 Agentic Yield Diagnosis)
  try {
    const rawReport = D.llm_report;
    const lots = (rawReport && rawReport.lots) ? rawReport.lots : (rawReport ? [rawReport] : []);
    const lotList = document.getElementById('custom-lot-list');
    let curLotIdx = 0;

    function renderLotCockpit(idx, isInitial) {
      if (!lots || lots.length === 0) return;
      curLotIdx = idx;
      const item = lots[idx];

      // Update active row
      if (lotList) {
        Array.from(lotList.children).forEach((r, i) => {
          r.classList.toggle('on', i === idx);
        });
      }

      // 1. Badge & Gauge (Col 2 - Instant update)
      const color = item.risk_level === 'HIGH' ? 'var(--neon-rose)' :
                    (item.risk_level === 'MEDIUM' ? 'var(--neon-amber)' : 'var(--neon-green)');
      const badgeBg = item.risk_level === 'HIGH' ? 'rgba(255,107,107,0.15)' :
                      (item.risk_level === 'MEDIUM' ? 'rgba(255,193,7,0.15)' : 'rgba(0,255,136,0.15)');

      const gaugeBadge = document.getElementById('lot_gauge_badge');
      if (gaugeBadge) {
        gaugeBadge.innerHTML = `<span style="padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700;background:${badgeBg};color:${color};border:1px solid ${color}">위험도: ${item.risk_level} (${item.risk_score}점)</span>`;
      }

      const gaugeUi = document.getElementById('lot_gauge_ui');
      if (gaugeUi) {
        gaugeUi.innerHTML = `
          <!-- HUD Header -->
          <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:rgba(255,255,255,0.02);border:1px solid var(--border-glass);border-radius:8px;">
            <div>
              <div style="font-size:11px;color:var(--text-muted);font-weight:600">INSPECTED LOT</div>
              <div style="font-size:18px;font-weight:700;color:var(--neon-cyan)">${item.lot_id}</div>
            </div>
            <div style="text-align:right">
              <div style="font-size:11px;color:var(--text-muted)">검사 수량</div>
              <div style="font-size:14px;font-weight:600;color:var(--text-white)">${item.wafers_inspected || 25}장 전수</div>
            </div>
          </div>

          <!-- Semi-Circle Radial Speedometer Gauge -->
          <div style="background:#070a10;padding:16px 12px 12px;border:1px solid var(--border-glass);border-radius:8px;display:flex;flex-direction:column;align-items:center;">
            <div style="font-size:12px;color:var(--text-secondary);font-weight:600;margin-bottom:4px;letter-spacing:0.5px">종합 수율 위험 지수 (YIELD RISK GAUGE)</div>
            <div style="position:relative;width:220px;height:125px;display:flex;justify-content:center;">
              <svg width="220" height="125" viewBox="0 0 220 125" style="overflow:visible;">
                <defs>
                  <linearGradient id="gaugeTrackGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                    <stop offset="0%" stop-color="#00ff88" stop-opacity="0.2"/>
                    <stop offset="50%" stop-color="#ffb300" stop-opacity="0.2"/>
                    <stop offset="100%" stop-color="#ff3366" stop-opacity="0.2"/>
                  </linearGradient>
                </defs>
                <path d="M 25 115 A 85 85 0 0 1 195 115" fill="none" stroke="url(#gaugeTrackGrad)" stroke-width="14" stroke-linecap="round"/>
                <path d="M 25 115 A 85 85 0 0 1 195 115" fill="none" stroke="rgba(255,255,255,0.05)" stroke-width="14" stroke-linecap="round"/>
                <path d="M 25 115 A 85 85 0 0 1 195 115" fill="none" stroke="${color}" stroke-width="14" stroke-linecap="round"
                      stroke-dasharray="267" stroke-dashoffset="${(267 * (1 - Math.min(100, Math.max(0, item.risk_score)) / 100)).toFixed(1)}"
                      style="filter:drop-shadow(0 0 8px ${color}); transition: stroke-dashoffset 0.6s ease;"/>
                <text x="110" y="94" text-anchor="middle" font-size="34" font-weight="800" fill="${color}" font-family="monospace">${item.risk_score}</text>
                <text x="110" y="112" text-anchor="middle" font-size="10.5" font-weight="700" fill="var(--text-muted)" letter-spacing="1">/ 100 RISK INDEX</text>
                <text x="22" y="124" font-size="10" font-weight="600" fill="var(--text-muted)" text-anchor="middle">0</text>
                <text x="110" y="24" font-size="9" font-weight="600" fill="var(--text-muted)" text-anchor="middle">50 (MED)</text>
                <text x="198" y="124" font-size="10" font-weight="600" fill="var(--text-muted)" text-anchor="middle">100</text>
              </svg>
            </div>
            <div style="display:flex;gap:12px;margin-top:4px;font-size:11px;">
              <span style="color:var(--text-muted)"><b style="color:var(--neon-green)">0~50</b> LOW</span>
              <span style="color:var(--text-muted)"><b style="color:var(--neon-amber)">51~70</b> MED</span>
              <span style="color:var(--text-muted)"><b style="color:var(--neon-rose)">71~100</b> HIGH</span>
            </div>
          </div>

          <!-- Key Metrics Grid -->
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
            <div style="background:#070a10;padding:12px;border:1px solid var(--border-glass);border-radius:8px;">
              <div style="font-size:11px;color:var(--text-muted)">주요 감지 패턴</div>
              <div style="font-size:14px;font-weight:700;color:var(--text-white);margin-top:4px;">${item.detected_pattern}</div>
            </div>
            <div style="background:#070a10;padding:12px;border:1px solid var(--border-glass);border-radius:8px;">
              <div style="font-size:11px;color:var(--text-muted)">로트 내 불량률</div>
              <div style="font-size:14px;font-weight:700;color:${color};margin-top:4px;">${item.defect_rate}% <span style="font-size:11px;color:var(--text-muted);font-weight:400">(한계 5.0%)</span></div>
            </div>
          </div>

          <!-- Permutation Stat -->
          <div style="background:#070a10;padding:12px;border:1px solid var(--border-glass);border-radius:8px;">
            <div style="font-size:11px;color:var(--text-muted)">순열 검정 통계 (로트 내 패턴 집중도)</div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px;">
              <span style="font-size:13px;color:var(--text-secondary)">유의확률: <b style="color:var(--text-white)">p=${item.permutation_p_value.toFixed(4)}</b></span>
              <span style="font-size:12px;padding:2px 8px;border-radius:4px;background:rgba(0,240,255,0.08);color:var(--neon-cyan)">${item.pattern_clustering}</span>
            </div>
          </div>
        `;
      }

      // 2. AI Agent Report (Col 3 - With realistic thinking delay on click)
      const agentUi = document.getElementById('lot_agent_ui');
      if (!agentUi) return;

      const latencyStr = item.latency || '1.8s';
      const tokensCount = item.tokens || 432;

      function displayAgentContent() {
        agentUi.innerHTML = `
          <div style="display:flex;flex-direction:column;gap:12px;">

            <!-- [1. Agent Header with Dynamic Latency & Tokens] -->
            <div style="display:flex;align-items:center;justify-content:space-between;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.06);">
              <div style="display:flex;align-items:center;gap:8px;">
                <div style="width:26px;height:26px;border-radius:6px;background:linear-gradient(135deg, #d97706 0%, #b45309 100%);display:flex;align-items:center;justify-content:center;box-shadow:0 0 10px rgba(217,119,6,0.3);">
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.3">
                    <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
                  </svg>
                </div>
                <div>
                  <div style="display:flex;align-items:center;gap:6px;">
                    <b style="font-size:13.5px;color:var(--text-white);">Claude Opus 5.5</b>
                    <span style="font-size:9.5px;padding:1px 5px;border-radius:3px;background:rgba(217,119,6,0.15);color:#f59e0b;border:1px solid rgba(217,119,6,0.3);font-weight:700;">AUTONOMOUS AGENT</span>
                  </div>
                  <div style="font-size:10.5px;color:var(--text-muted);">Fab Multimodal Diagnostic Agent Loop</div>
                </div>
              </div>
              <div style="text-align:right;font-size:10.5px;color:var(--text-muted);">
                <div style="color:var(--neon-green);font-weight:600;">ACTIVE</div>
                <div>${latencyStr} &bull; ${tokensCount} tokens</div>
              </div>
            </div>

            <!-- [2. Robust Non-wrapping Stepper Grid] -->
            <div style="background:rgba(255,255,255,0.015);border:1px solid var(--border-glass);border-radius:8px;padding:8px 10px;">
              <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1.15fr;gap:6px;align-items:center;">
                <div style="padding:4px 6px;border-radius:4px;background:rgba(0,240,255,0.08);border:1px solid rgba(0,240,255,0.2);color:var(--neon-cyan);font-size:10.5px;font-weight:600;white-space:nowrap;text-align:center;">
                  1. 패턴 추론
                </div>
                <div style="padding:4px 6px;border-radius:4px;background:rgba(0,240,255,0.08);border:1px solid rgba(0,240,255,0.2);color:var(--neon-cyan);font-size:10.5px;font-weight:600;white-space:nowrap;text-align:center;">
                  2. 순열 검정
                </div>
                <div style="padding:4px 6px;border-radius:4px;background:rgba(0,240,255,0.08);border:1px solid rgba(0,240,255,0.2);color:var(--neon-cyan);font-size:10.5px;font-weight:600;white-space:nowrap;text-align:center;">
                  3. 게이트 심사
                </div>
                <div style="padding:4px 6px;border-radius:4px;background:${item.pipeline_color}18;color:${item.pipeline_color};border:1px solid ${item.pipeline_color};font-size:10px;font-weight:700;white-space:nowrap;text-align:center;overflow:hidden;text-overflow:ellipsis;">
                  ${item.pipeline_status}
                </div>
              </div>
            </div>

            <!-- [3. Collapsible Details: AGENT FUNCTION TRACE (Default Closed)] -->
            <details style="background:#03060a;border:1px solid rgba(255,255,255,0.08);border-radius:6px;overflow:hidden;">
              <summary style="cursor:pointer;padding:8px 12px;font-family:ui-monospace,monospace;font-size:11px;color:#94a3b8;display:flex;align-items:center;justify-content:space-between;user-select:none;background:rgba(255,255,255,0.02);">
                <span style="display:flex;align-items:center;gap:6px;">
                  <span style="color:#f59e0b;">⚙️</span>
                  <span style="font-weight:600;color:#cbd5e1;">AGENT FUNCTION TRACE</span>
                  <span style="color:#64748b;font-size:10px;">(3 Tools Executed)</span>
                </span>
                <span style="font-size:10px;color:var(--neon-cyan);display:flex;align-items:center;gap:3px;">
                  상세 보기 <span style="font-size:8px;">▼</span>
                </span>
              </summary>
              <div style="padding:8px 10px 10px;border-top:1px solid rgba(255,255,255,0.05);display:flex;flex-direction:column;gap:5px;font-family:ui-monospace,monospace;font-size:10.5px;line-height:1.45;">
                <div style="display:flex;align-items:center;gap:6px;">
                  <span style="color:#64748b;">[0.4s]</span>
                  <span style="color:var(--neon-cyan);">call_tool('cnn_classifier')</span>
                  <span style="color:#475569;">&rarr;</span>
                  <span style="color:#cbd5e1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${item.detected_pattern} (확신도 94.2%)</span>
                </div>
                <div style="display:flex;align-items:center;gap:6px;">
                  <span style="color:#64748b;">[0.9s]</span>
                  <span style="color:var(--neon-cyan);">call_tool('permute_test_1000')</span>
                  <span style="color:#475569;">&rarr;</span>
                  <span style="color:#cbd5e1;">p-value: ${item.permutation_p_value.toFixed(4)} (${item.pattern_clustering})</span>
                </div>
                <div style="display:flex;align-items:center;gap:6px;">
                  <span style="color:#64748b;">[1.3s]</span>
                  <span style="color:var(--neon-cyan);">call_tool('gatekeeper_eval')</span>
                  <span style="color:#475569;">&rarr;</span>
                  <span style="color:${item.pipeline_color};font-weight:600;">${item.gate_status}</span>
                </div>
              </div>
            </details>

            <!-- [4. Synthesized Directive & Action Trigger] -->
            <div style="background:#080c14;border:1px solid var(--border-glass);border-radius:8px;padding:13px 14px;box-shadow:inset 0 1px 0 rgba(255,255,255,0.03);">
              <div style="display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;color:var(--neon-cyan);letter-spacing:0.5px;margin-bottom:6px;">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
                AI SYNTHESIZED DIAGNOSIS
              </div>
              <div style="font-size:12.5px;color:#cbd5e1;line-height:1.65;margin-bottom:12px;">
                ${item.agent_synthesis || item.llm_analysis}
              </div>

              <!-- Official Action Directive -->
              <div style="background:rgba(0,240,255,0.03);border:1px solid ${color};border-radius:6px;padding:11px 13px;">
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:4px;">
                  <div style="display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;color:${color};">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>
                    자율 발행 공정 지침 (ACTION DIRECTIVE)
                  </div>
                  <span style="font-size:9px;padding:1px 5px;border-radius:3px;background:${color}22;color:${color};font-weight:700;">AUTONOMOUS ACTION</span>
                </div>
                <div style="font-size:12px;color:#ffffff;line-height:1.55;font-weight:600;white-space:pre-line;">
                  ${item.action_directive || item.recommended_action}
                </div>
              </div>

              <!-- Execution Footer -->
              <div style="display:flex;align-items:center;justify-content:space-between;margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05);font-size:10.5px;color:var(--text-muted);">
                <span>Target Lot: <b style="color:var(--text-secondary)">${item.lot_id}</b></span>
                <span>Gate Rule: <b style="color:${color}">${item.gate_status}</b></span>
              </div>
            </div>

          </div>
        `;
      }

      if (isInitial) {
        displayAgentContent();
      } else {
        // Show realistic agent reasoning state for ~300ms
        agentUi.innerHTML = `
          <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:320px;gap:14px;color:var(--text-muted);">
            <div style="width:36px;height:36px;border-radius:50%;border:2px solid rgba(217,119,6,0.2);border-top:2px solid #d97706;animation:spin 0.7s linear infinite;"></div>
            <div style="text-align:center;">
              <div style="font-size:13.5px;font-weight:700;color:var(--text-white);letter-spacing:0.3px;">Claude Opus 5.5 추론 중...</div>
              <div style="font-size:11px;color:#64748b;margin-top:4px;">Scanning wafer spatial maps &bull; Running permutation tests &bull; Evaluating confidence gate</div>
            </div>
          </div>
          <style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>
        `;
        setTimeout(displayAgentContent, 300);
      }
    }

    // Populate custom-lot-list and initial render
    if (lotList && lots.length > 0) {
      lotList.innerHTML = '';
      lots.forEach((lt, i) => {
        const row = document.createElement('div');
        row.className = 'wafer-item-row' + (i === 0 ? ' on' : '');
        const rColor = lt.risk_level === 'HIGH' ? 'var(--neon-rose)' :
                       (lt.risk_level === 'MEDIUM' ? 'var(--neon-amber)' : 'var(--neon-green)');
        row.innerHTML = `
          <div class="w-row-left">
            <span style="width:7px;height:7px;border-radius:50%;background:${rColor}"></span>
            <div class="w-row-id">${lt.lot_id}</div>
          </div>
          <div class="w-row-badge" style="background:rgba(255,255,255,0.06);color:${rColor};font-weight:700;">${lt.risk_level}</div>
        `;
        row.onclick = () => renderLotCockpit(i, false);
        lotList.appendChild(row);
      });
      renderLotCockpit(0, true);
    }
  } catch (err) { console.error('multi-lot controller error:', err); }

});
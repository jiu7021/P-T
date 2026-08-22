// P&T 워크벤치 대시보드. 외부 라이브러리·API를 쓰지 않는다.
// 브라우저 저장소(localStorage 등)도 쓰지 않는다.
const D = JSON.parse(document.getElementById('payload').textContent);
const $ = (id) => document.getElementById(id);

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
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav button').forEach(x => x.classList.toggle('on', x === b));
  document.querySelectorAll('.tab').forEach(s => s.classList.toggle('on', s.id === b.dataset.tab));
});

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
  $('wcount').textContent = `${W.length}장 · 오분류 ${wrong}장 포함(✗). 잘 맞은 것만 고르지 않았습니다.`;
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
      <b>실제 패턴</b><span>${PAT_KO[w.true_label] || w.true_label} <span style="color:var(--muted);font-size:11px">${w.true_label}</span></span>
      <b>모델 예측</b><span class="${w.correct ? 'ok' : 'bad'}">${PAT_KO[w.pred_label] || w.pred_label} ${w.correct ? '(일치)' : '(불일치)'}</span>
      <b>패턴 뜻</b><span style="font-size:11.5px;color:var(--muted)">${PAT_DESC[w.true_label] || ''}</span>
      <b>다이 수</b><span>${w.die_count.toLocaleString()}</span>
      <b>불량 다이</b><span>${w.fail_count.toLocaleString()} (${(w.fail_rate * 100).toFixed(2)}%)</span>
    </div>
    <h3 style="margin-top:14px">클래스 확률 상위 4</h3>
    ${top.map(([k, v]) => `<div style="margin-bottom:6px">
      <div style="display:flex;justify-content:space-between;font-size:12.5px">
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
const G_COL = ['#4ca85c', '#f0bf33', '#d93630'];
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
      <div class="proc">${t.order}. ${t.label} <span style="font-weight:400;color:var(--muted);font-size:12px">${temp}</span></div>
      <div class="rat" style="white-space:pre-line">${t.plain.trim()}</div>
      <div style="font-size:12.5px;margin-top:5px"><b style="color:var(--muted)">규격</b> ${spec}
        · <b style="color:var(--muted)">리페어 대상</b> ${
          t.repairable_scope === 'cell_array' ? '예 (셀 어레이)' : '아니오 (칩 전체 특성)'}</div>
      ${(t.reference || []).map(r => `<div class="ref">출처: ${r}</div>`).join('')}
    </div>`;
  }).join('') + `<p style="font-size:11.5px;color:var(--warn)">규격 절대값은 가정치입니다.
    항목 간 상대 관계만 물리적으로 타당하게 잡았습니다.</p>`;

  $('egrades').innerHTML = E.grades.map((g, i) => `<div style="margin-bottom:8px">
      <b style="color:${G_COL[i]}">${g.label}</b>
      <div style="font-size:12.5px;white-space:pre-line">${g.rule.trim()}</div>
      ${g.note ? `<div style="font-size:12px;color:var(--warn);white-space:pre-line;margin-top:4px">${g.note.trim()}</div>` : ''}
    </div>`).join('');

  const ra = (D.eds.repair_analysis_steps || null);
  $('esteps').innerHTML = [
    'fail bit의 주소를 (X=행, Y=열)으로 모은다.',
    '어떤 행의 fail 수가 <b>남은 여분 열</b>보다 많으면 열로 덮을 수 없다 → 반드시 행 리페어를 배정한다.',
    '어떤 열의 fail 수가 <b>남은 여분 행</b>보다 많으면 → 반드시 열 리페어.',
    '강제 배정을 마친 뒤 남은 fail을 남은 여분으로 덮을 수 있는지 탐색한다.',
    '전부 덮이면 Repairable, 남으면 Fail.',
  ].map(x => `<li>${x}</li>`).join('');
  $('erefs').innerHTML = `<div style="font-size:12px"><b style="color:var(--muted)">여분 자원</b>
      행 ${E.repair.spare_rows}개 / 열 ${E.repair.spare_cols}개 <span style="color:var(--warn)">(가정치)</span></div>`
    + (E.repair.reference || []).map(r => `<div class="ref">출처: ${r}</div>`).join('');

  // 모드별 리페어 성공률
  const bm = E.summary.by_mode || {};
  const rows = Object.entries(bm).sort((a, b) => b[1].repairable - a[1].repairable);
  $('emodes').innerHTML = `<table><tr><th>불량 모드</th><th>다이 수</th><th>Repairable</th></tr>`
    + rows.map(([k, v]) => `<tr><td>${MODE_LABEL_E(k)}</td><td>${v.n.toLocaleString()}</td>
        <td class="${v.repairable > 0.5 ? 'ok' : 'bad'}">${(v.repairable * 100).toFixed(2)}%</td></tr>`).join('')
    + `</table><p style="font-size:12px;color:var(--muted);margin-top:8px">
      로우성 하나는 여분 행 1개로 끝납니다. 블락성은 행·열을 다 써도 못 덮습니다.
      좁은 영역에 fail이 뭉치면 어느 한 줄로 정리되지 않기 때문입니다.</p>`;

  // 민감도
  const S = E.sensitivity;
  const card = (title, note, rowsArr) => `<div class="cand">
      <div class="proc">${title}</div>
      <div style="font-size:12px;color:var(--muted);margin-bottom:5px">${note}</div>
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
      <div style="display:flex;justify-content:space-between;font-size:12.5px">
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
      <td style="color:var(--muted);font-size:11.5px">${spTxt} ${u}</td>
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
    <div style="font-size:16px;font-weight:700;color:${G_COL[gi]};margin-bottom:2px">${G_NAME[gi]}</div>
    <div style="font-size:12.5px;color:var(--muted);margin-bottom:10px">${G_KO[gi]}</div>
    <div class="kv" style="margin-bottom:10px">
      <b>좌표</b><span class="mono">(${mx}, ${my})</span>
      <b>실데이터 판정</b><span>${w.grade[k] === 0 ? '정상 다이' : '불량 다이'}
        <span style="color:var(--muted);font-size:11px">WM-811K</span></span>
    </div>
    <table style="margin-bottom:10px">
      <tr><th>시험</th><th>측정값</th><th>규격</th><th></th></tr>${rowsHtml}
    </table>
    <div style="font-size:12.5px;line-height:1.7">${reason}</div>
    <p style="font-size:11.5px;color:var(--muted);margin-top:10px">
      측정값과 fail bit 주소는 합성입니다. 이 다이가 불량인지 아닌지는 실데이터가 정했고,
      합성은 <b>왜 불량인지</b>만 만듭니다.</p>`;

  drawChip(mode, w.nbits[k], gi, w.ur[k], w.uc[k], mx, my, isCell);
};

// 선택한 다이의 칩 내부 Fail Address를 그린다.
// 웨이퍼 맵의 점 하나 = 칩 한 개, 여기는 그 칩 안쪽이다. 두 계층을 잇는 화면이다.
function drawChip(mode, nbits, gi, ur, uc, dx, dy, isCell) {
  const box = $('echip');
  if (!isCell || !nbits) {
    box.style.display = 'none';
    return;
  }
  box.style.display = '';
  $('echiptitle').textContent = `— 웨이퍼 좌표 (${dx}, ${dy})`;

  const addrs = synth(mode, nbits, 16);
  const S = 300, c = $('echipmap'), g = c.getContext('2d');
  g.clearRect(0, 0, S, S);
  g.strokeStyle = css('--border');
  g.strokeRect(0.5, 0.5, S - 1, S - 1);
  // 눈금: 주소 공간을 8등분해 옅은 격자를 깐다. 줄인지 덩어리인지 눈으로 잡기 쉽다.
  g.strokeStyle = css('--die-out');
  for (let i = 1; i < 8; i++) {
    g.beginPath(); g.moveTo(i * S / 8, 0); g.lineTo(i * S / 8, S); g.stroke();
    g.beginPath(); g.moveTo(0, i * S / 8); g.lineTo(S, i * S / 8); g.stroke();
  }
  g.fillStyle = gi === 1 ? '#e8a317' : '#d93630';
  addrs.forEach(([x, y]) => {
    g.beginPath();
    g.arc(4 + (x / XMAX) * (S - 8), 4 + (y / YMAX) * (S - 8), 2.4, 0, 6.283);
    g.fill();
  });

  $('echiptbl').innerHTML = addrs.slice(0, 40).map(([x, y]) =>
    `<tr><td>${x.toString(16).padStart(4, '0')}</td><td>${y.toString(16).padStart(3, '0')}</td></tr>`).join('')
    + (addrs.length > 40 ? `<tr><td colspan="2" style="color:var(--muted)">… 외 ${addrs.length - 40}건</td></tr>` : '');

  const res = classify(addrs, {lc: 4, lr: 0.30, bc: 6, br: 0.40});
  const md = (D.fail_address.modes || {})[mode] || {};
  $('echipnote').innerHTML = `
    <div class="kv" style="margin-bottom:9px">
      <b>fail bit</b><span>${addrs.length}개</span>
      <b>주소 분포가 말하는 것</b><span><b>${MODE_LABEL[res.mode] || res.mode}</b>
        (설명 비율 ${res.score.toFixed(2)})</span>
      <b>리페어 결과</b><span class="${gi === 1 ? 'ok' : 'bad'}">
        여분 행 ${ur}/${E.repair.spare_rows}, 열 ${uc}/${E.repair.spare_cols} 사용 →
        ${gi === 1 ? 'Repairable' : 'Fail'}</span>
    </div>
    <div style="font-size:12.5px;white-space:pre-line">${(md.plain || '').trim()}</div>
    <div style="font-size:12.5px;margin-top:7px"><b style="color:var(--muted)">관련 공정</b><br>${
      (md.process_link || '').trim()}</div>
    <p style="font-size:11.5px;color:var(--muted);margin-top:8px">
      이 주소들은 판정에 쓰인 것과 <b>같은 모드·같은 개수로 다시 만든 분포</b>입니다.
      주소 자체가 합성이므로 성질은 같지만 개별 값은 판정 시점과 다릅니다.
      리페어 결과는 판정 시점의 실제 계산 값입니다.</p>`;
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
        <span style="color:var(--muted);font-size:11px">${s.morphology}</span></span>
      <b>결함이 차지한 면적</b><span>${(sh.area_frac * 100).toFixed(3)}%</span>
      <b>길이 대 폭 비</b><span>${el} <span style="color:var(--muted);font-size:11px">클수록 가늘고 길다</span></span>
      <b>덩어리 개수</b><span>${sh.n_components}</span>
      <b>모델이 지목한 범위</b><span>${
        s.gt_px === 0
          ? (s.pred_px === 0 ? '없음 <span class="ok">— 전문가 정답도 없음(일치)</span>'
                             : `${s.pred_px}px <span class="bad">— 전문가 정답은 없음(오검출)</span>`)
          : `${s.pred_px}px (전문가 표시 ${s.gt_px}px)` +
            (s.pred_px < s.gt_px * 0.6 ? ' <span class="bad">— 실제보다 좁게 잡음</span>' : '')}</span>
      <b>파일</b><span class="mono" style="font-size:11px">${s.filename}</span>
    </div>
    <p style="font-size:11.5px;color:var(--muted);margin:8px 0 0">
      데이터셋이 결함 클래스 이름을 공개하지 않아 라벨은 숫자뿐입니다. 숫자에 임의로 결함 용어를
      붙이지 않고, 마스크에서 <b>실제로 측정한 형태</b>로 원인 공정 후보를 조회합니다.</p>`;

  const rules = CAUSE.morphology_rules;
  const cands = CAUSE.morphologies[s.morphology].candidates;
  const obs = CAUSE.morphologies[s.morphology].observed_in_dataset;
  $('scand').innerHTML = `
    <p style="font-size:12px;color:var(--muted);margin-top:0">
      형태 판정: 길이 대 폭 비가 3 미만이면 둥근 덩어리형, 3~30이면 굵거나 불규칙한 선상,
      30 이상이면 가늘고 긴 선상. 임계값은 정답 마스크 4,365장의 실측 분포에서
      두 무리 사이가 비는 지점으로 정했습니다.</p>
    <p style="font-size:12px;color:var(--muted)">데이터셋 관측: ${obs.note}</p>
    ${cands.map((c, k) => `<div class="cand">
      <div class="proc">[${k + 1}] ${c.process}${c.sub ? ' / ' + c.sub : ''}</div>
      <div class="rat">${c.rationale}</div>
      ${c.reference.map(r => `<div class="ref">출처: ${r}</div>`).join('')}
      <div class="note">${c.confidence_note}</div>
    </div>`).join('')}
    <p style="font-size:12px;font-weight:600;color:var(--chip-look)">${CAUSE.meta.disclaimer}</p>`;
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

function fRules() {
  return {lc: +$('r1').value, lr: +$('r2').value / 100,
          bc: +$('r3').value, br: +$('r4').value / 100};
}

function fRender() {
  const r = fRules();
  const res = classify(FADDR, r);
  // 산점도
  const c = $('fplot'), g = c.getContext('2d'), S = 340;
  g.clearRect(0, 0, S, S);
  g.strokeStyle = css('--border'); g.strokeRect(0.5, 0.5, S - 1, S - 1);
  g.fillStyle = css('--die-fail');
  FADDR.forEach(([x, y]) => {
    const px = 4 + (x / XMAX) * (S - 8), py = 4 + (y / YMAX) * (S - 8);
    g.beginPath(); g.arc(px, py, 2.6, 0, 6.283); g.fill();
  });
  // 표
  $('ftbl').innerHTML = FADDR.map(([x, y]) =>
    `<tr><td>${x.toString(16).padStart(4, '0')}</td><td>${y.toString(16).padStart(3, '0')}</td></tr>`).join('');

  if (!res) { $('fres').innerHTML = 'fail 없음'; return; }
  const e = res.ev;
  const sc = Object.entries(e.scores).sort((a, b) => b[1] - a[1]);
  $('fres').innerHTML = `
    <div style="font-size:17px;font-weight:700;margin-bottom:4px">
      ${MODE_LABEL[res.mode]} <span style="font-size:13px;color:var(--muted)">(${res.mode})</span></div>
    <div style="font-size:12.5px;color:var(--muted);margin-bottom:8px;white-space:pre-line">${
      ((D.fail_address.modes || {})[res.mode] || {}).plain?.trim() || ''}</div>
    <div style="margin-bottom:10px">설명 비율 <b class="mono">${res.score.toFixed(3)}</b>
      ${res.ambiguous ? `<span class="bad"> ← 경계 사례 (차상위 ${MODE_LABEL[res.runner[0]]} ${res.runner[1].toFixed(3)}, 차이 ${AMB} 미만)</span>` : ''}</div>
    <h3>근거</h3>
    <div class="kv mono" style="font-size:12px">
      <b>fail 총수</b><span>${e.n}</span>
      <b>최다 X</b><span>0x${e.tx.toString(16).padStart(4, '0')} : ${e.cx}건 (${(e.cx / e.n * 100).toFixed(1)}%) ${e.rowOk ? '<span class="ok">임계 통과</span>' : '<span style="color:var(--muted)">임계 미달</span>'}</span>
      <b>최다 Y</b><span>0x${e.ty.toString(16).padStart(3, '0')} : ${e.cy}건 (${(e.cy / e.n * 100).toFixed(1)}%) ${e.colOk ? '<span class="ok">임계 통과</span>' : '<span style="color:var(--muted)">임계 미달</span>'}</span>
      <b>최밀 블록</b><span>0x${e.bx.toString(16).padStart(4, '0')} / 0x${e.by.toString(16).padStart(3, '0')} : ${e.bestCnt}건 (${(e.bestCnt / e.n * 100).toFixed(1)}%) ${e.blkOk ? '<span class="ok">임계 통과</span>' : '<span style="color:var(--muted)">임계 미달</span>'}</span>
    </div>
    <h3 style="margin-top:12px">구조별 설명 비율</h3>
    ${sc.map(([k, v]) => `<div style="margin-bottom:5px">
      <div style="display:flex;justify-content:space-between;font-size:12.5px">
        <span>${MODE_LABEL[k]}</span><span class="mono">${v.toFixed(3)}</span></div>
      <div class="bar"><i style="width:${(v * 100).toFixed(1)}%"></i></div></div>`).join('')}
    <p style="font-size:11.5px;color:var(--muted);margin-top:10px">
      점수는 <b>그 구조가 설명하는 fail의 비율</b>이며 확률이 아닙니다.
      싱글비트 점수는 어느 구조로도 설명되지 않은 fail의 비율(합집합 기준)입니다.
      임계값을 바꾸면 판별이 바뀝니다 — 임계값이 가정치라는 뜻입니다.</p>`;
}

function fGen() {
  FADDR = addNoise(synth($('fmode').value, +$('fn').value, +$('fst').value), +$('fnz').value);
  fRender();
}
['fn', 'fnz', 'fst'].forEach(id => $(id).oninput = () => {
  $({fn: 'fnv', fnz: 'fnzv', fst: 'fstv'}[id]).textContent = $(id).value;
  fGen();
});
$('fmode').onchange = fGen;
$('fgen').onclick = fGen;
['r1', 'r2', 'r3', 'r4'].forEach((id, k) => $(id).oninput = () => {
  const v = +$(id).value;
  $('v' + (k + 1)).textContent = (k === 1 || k === 3) ? (v / 100).toFixed(2) : v;
  fRender();
});
fGen();

// 불량 모드가 어떤 공정 문제에서 나오는지 — config/fail_modes.yaml 그대로 표시한다
{
  const M = D.fail_address.modes || {};
  $('fmodes').innerHTML = Object.entries(M).map(([k, v]) => `
    <div class="cand">
      <div class="proc">${v.label} <span style="font-weight:400;color:var(--muted);font-size:12px">${k}</span></div>
      <div class="rat" style="white-space:pre-line">${(v.plain || '').trim()}</div>
      <div style="font-size:12.5px;margin-top:7px">
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
    <p style="font-size:12px;color:var(--muted);margin-bottom:0">
      fail이 6.6%뿐이라 accuracy는 의미가 없습니다(전부 pass로 찍어도 93.4%).
      주 지표는 <b>PR-AUC</b>이며, 기저율(무작위로 찍었을 때 값)과 나란히 봅니다.</p>`;

  const mo = Object.entries(S.monthly).filter(([, v]) => v.n > 0);
  const maxR = Math.max(...mo.map(([, v]) => v.fail / v.n));
  $('sc_month').innerHTML = mo.map(([k, v]) => {
    const r = v.fail / v.n;
    return `<div style="margin-bottom:7px">
      <div style="display:flex;justify-content:space-between;font-size:12.5px">
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
    <p style="font-size:12px;color:var(--muted)">결측 대치값과 표준화 통계도 <b>학습 구간에서만</b>
      계산합니다. 검증 구간 값을 쓰면 미래 정보가 샙니다.
      학습 ${ts.n_train}장(fail ${ts.fail_train}) / 검증 ${ts.n_test}장(fail ${ts.fail_test}).</p>`;

  const tk = ts.models.lightgbm.topk;
  $('sc_topk').innerHTML = `<table>
      <tr><th>재검사 비율</th><th>장수</th><th>fail 검출률</th><th>정밀도</th></tr>
      ${Object.entries(tk).map(([k, v]) => `<tr><td>상위 ${k.replace('top', '')}</td>
        <td>${v.n_reviewed}</td><td class="${v.recall > 0.3 ? '' : 'bad'}">${pct(v.recall)}</td>
        <td>${pct(v.precision)}</td></tr>`).join('')}
    </table>
    <p style="font-size:12px;color:var(--muted);margin-bottom:0">무작위로 골랐다면 검출률은
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
    <p style="font-size:12px;color:var(--muted);margin-bottom:0">최고 ${best.toFixed(4)}.
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
    <p style="font-size:12px;color:var(--warn);margin-bottom:0">센서 이름은 원본에서 익명화되어
      번호로만 식별됩니다. <b>어느 장비의 무슨 물리량인지 알 수 없어 공정 개선 조치로
      연결할 수 없습니다.</b> 이것도 공개 데이터의 한계입니다.</p>`;

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
    `<div style="margin-bottom:9px"><b style="font-size:12.5px">${k}</b>
     <div style="font-size:12px;color:var(--muted)">${v}</div></div>`).join('');

  const pe = D.pattern_eval, de = D.defect_eval;
  const seg = de.test_segmentation;
  $('perf').innerHTML = `
    <b style="font-size:12.5px">Module A 패턴 분류 (로트 단위 분할)</b>
    <table style="margin-bottom:12px">
      <tr><td>test macro-F1</td><td>${pe.test_macro_f1.toFixed(3)}</td></tr>
      <tr><td>test accuracy</td><td>${pe.test_accuracy.toFixed(3)}</td></tr>
      <tr><td>가장 낮은 클래스</td><td>Loc ${pe.per_class['Loc'].f1.toFixed(3)}</td></tr>
    </table>
    <b style="font-size:12.5px">Module B 세그멘테이션 (이미지 단위 분할)</b>
    <table style="margin-bottom:12px">
      <tr><td>이미지별 Dice 평균</td><td>${seg.dice_image_mean.toFixed(4)}</td></tr>
      <tr><td>이미지별 IoU 평균</td><td>${seg.iou_image_mean.toFixed(4)}</td></tr>
      <tr><td>빈 마스크 오검출 픽셀</td><td>${seg.empty_gt_fp_pixels_mean.toFixed(1)}</td></tr>
    </table>
    <b style="font-size:12.5px">Module B 분류</b>
    <table>
      <tr><td>macro-F1</td><td>${de.test_macro_f1.toFixed(3)}</td></tr>
      <tr><td>accuracy</td><td>${de.test_accuracy.toFixed(3)}</td></tr>
      <tr><td>class 5 (표본 ${de.per_class['5'].support}장)</td><td class="bad">${de.per_class['5'].f1.toFixed(3)}</td></tr>
    </table>
    <p style="font-size:11.5px;color:var(--muted);margin-top:9px">
      macro-F1 ${de.test_macro_f1.toFixed(3)}을 그대로 읽으면 안 됩니다. 표본 1장짜리 class 5의 F1 0이
      6분의 1 가중치로 들어가 있습니다. 표본이 충분한 class 3·4·6은 각각
      ${de.per_class['3'].f1.toFixed(3)} / ${de.per_class['4'].f1.toFixed(3)} / ${de.per_class['6'].f1.toFixed(3)}입니다.</p>`;
  $('gen').textContent = `생성 ${D.meta.generated} · 시드 ${D.meta.seed}`;
}

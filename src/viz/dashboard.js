// P&T 워크벤치 대시보드. 외부 라이브러리·API를 쓰지 않는다.
// 브라우저 저장소(localStorage 등)도 쓰지 않는다.
const D = JSON.parse(document.getElementById('payload').textContent);
const $ = (id) => document.getElementById(id);
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
    o.textContent = `${w.true_label.padEnd(10)} ${w.correct ? '  ' : '✗ '}${w.wafer_id}`;
    sel.appendChild(o);
  });
  const wrong = W.filter(w => !w.correct).length;
  $('wcount').textContent = `${W.length}장 (test 분할) · 오분류 ${wrong}장 포함 (✗ 표시)`;
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
      <b>실제 라벨</b><span>${w.true_label}</span>
      <b>예측 라벨</b><span class="${w.correct ? 'ok' : 'bad'}">${w.pred_label} ${w.correct ? '(일치)' : '(불일치)'}</span>
      <b>다이 수</b><span>${w.die_count.toLocaleString()}</span>
      <b>불량 다이</b><span>${w.fail_count.toLocaleString()} (${(w.fail_rate * 100).toFixed(2)}%)</span>
    </div>
    <h3 style="margin-top:14px">클래스 확률 상위 4</h3>
    ${top.map(([k, v]) => `<div style="margin-bottom:6px">
      <div style="display:flex;justify-content:space-between;font-size:12.5px">
        <span>${k}</span><span class="mono">${(v * 100).toFixed(1)}%</span></div>
      <div class="bar"><i style="width:${(v * 100).toFixed(1)}%"></i></div></div>`).join('')}
    <h3 style="margin-top:14px">공간 특징 요약</h3>
    <div class="kv">
      <b>이웃(8) 불량률 평균</b><span>${(f.nb8_fail_rate_mean * 100).toFixed(2)}%</span>
      <b>정규화 반경-불량 상관</b><span>${f.r_norm_fail_corr === null ? '정의 불가(불량이 상수)' : f.r_norm_fail_corr}</span>
      <b>가장자리 거리 평균</b><span>${f.edge_dist_mean}</span>
      <b>직전 웨이퍼 정보</b><span>${f.prev_wafer_available ? '있음' : '없음(로트 첫 웨이퍼 등)'}</span>
    </div>
    <p style="font-size:11.5px;color:var(--muted);margin-top:10px">
      Grad-CAM은 예측 클래스 점수에 대한 마지막 conv 특징맵의 기울기를 채널 중요도로 삼아
      가중합한 것입니다. 붉은 영역이 그 판단에 크게 기여한 자리입니다.</p>`;
}

// ================= 탭 2: SEM =================
const SEM = D.sem.items, CAUSE = D.sem.cause_map;
{
  const sel = $('ssel');
  SEM.forEach((s, i) => {
    const o = document.createElement('option');
    o.value = i;
    o.textContent = `${s.morphology.padEnd(13)} L${s.label}  ` +
      (s.dice === null ? '정답 마스크 없음' : `Dice ${s.dice.toFixed(3)}`);
    sel.appendChild(o);
  });
  $('scount').textContent = `${SEM.length}장 (test 분할). 형태 유형별로 Dice 하위·중앙·상위를 섞어 골랐습니다. `
    + `정답 마스크가 비어 있는 none 그룹은 Dice가 정의되지 않습니다.`;
  sel.onchange = () => drawSem(+sel.value);
  $('sstretch').onchange = () => drawSem(+sel.value);
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
  const s = SEM[i], N = 128, S = 192;
  const useStretch = $('sstretch').checked;
  const img = new Image();
  img.onload = () => {
    for (const [cid, rleArr, color] of [['simg', null, null],
                                        ['sgt', s.gt_rle, [46, 160, 67]],
                                        ['spr', s.pred_rle, [229, 83, 75]]]) {
      const c = $(cid), g = c.getContext('2d');
      g.imageSmoothingEnabled = false;
      g.clearRect(0, 0, S, S);
      g.drawImage(img, 0, 0, S, S);
      if (useStretch) stretch(g, S);
      if (!rleArr) continue;
      const m = rleToMask(rleArr, N * N);
      const px = S / N;
      g.fillStyle = `rgba(${color[0]},${color[1]},${color[2]},0.55)`;
      for (let y = 0; y < N; y++) for (let x = 0; x < N; x++)
        if (m[y * N + x]) g.fillRect(x * px, y * px, px, px);
    }
  };
  img.src = s.img;

  const sh = s.shape;
  $('sinfo').innerHTML = `
    <div class="kv">
      <b>파일</b><span class="mono" style="font-size:11px">${s.filename}</span>
      <b>데이터셋 라벨</b><span>${s.label} <span style="color:var(--muted)">(이름 비공개)</span></span>
      <b>측정된 형태</b><span><b>${s.morphology}</b></span>
      <b>결함 면적</b><span>${(sh.area_frac * 100).toFixed(3)}%</span>
      <b>가늘기(elongation)</b><span>${sh.elongation === null ? '∞ (완전 직선)' : sh.elongation}</span>
      <b>연결 성분 수</b><span>${sh.n_components}</span>
      <b>채움률 / 원형도</b><span>${sh.solidity ?? '-'} / ${sh.circularity ?? '-'}</span>
      <b>세그멘테이션 Dice</b><span class="${s.dice === null ? '' : (s.dice >= 0.8 ? 'ok' : 'bad')}">${
        s.dice === null
          ? '<span style="color:var(--muted)">정의 불가 — 정답 마스크가 비어 있음</span>'
          : s.dice.toFixed(4)}</span>
      <b>정답 / 예측 픽셀</b><span>${s.gt_px} / ${s.pred_px}${
        s.gt_px === 0
          ? (s.pred_px === 0 ? ' <span class="ok">← 오검출 없음</span>' : ' <span class="bad">← 오검출</span>')
          : (s.pred_px < s.gt_px * 0.6 ? ' <span class="bad">← 과소 검출</span>' : '')}</span>
      <b>분류 예측</b><span>${s.cls_pred} ${s.cls_pred === s.label ? '<span class="ok">(일치)</span>' : '<span class="bad">(불일치)</span>'}</span>
    </div>`;

  const rules = CAUSE.morphology_rules;
  const cands = CAUSE.morphologies[s.morphology].candidates;
  const obs = CAUSE.morphologies[s.morphology].observed_in_dataset;
  $('scand').innerHTML = `
    <p style="font-size:12px;color:var(--muted);margin-top:0">
      형태 판정 기준: <span class="mono">${rules.measure}</span> —
      compact &lt;3, linear_broad 3~30, linear_fine ≥30.
      임계값은 정답 마스크 4,365장의 실측 분포에서 두 군집 사이가 비는 지점으로 정했습니다.</p>
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

// ================= 탭 5: 한계 · 성능 =================
{
  const L = [
    ['L1 비구조화 층', 'Carinthia-S는 주기 구조가 없는 층이라 주기성 기반 이상 탐지를 쓸 수 없습니다. 패턴 층 일반화를 주장할 수 없습니다.'],
    ['L3 없는 라벨', 'Fail Address 비트맵, 원인 공정 라벨, 항목별 테스트 결과는 공개 데이터가 없습니다. 학습 타깃으로 삼지 않습니다.'],
    ['L5 분할 단위', 'Carinthia-S에 웨이퍼·배치 식별자가 없어 이미지 단위로 분할했습니다. Module B 수치는 낙관 편향을 가집니다.'],
    ['L6 클래스 이름 비공개', '결함 클래스는 1~6 숫자뿐입니다. 숫자에 결함 용어를 붙이지 않고 측정된 형태를 씁니다.'],
    ['L7 극단 불균형', 'class 5는 4장, class 2는 8장뿐입니다(1002:1). 이 클래스들의 F1은 잡음입니다.'],
    ['L9 마스크 예외', '설명서는 binary 마스크라고 하지만 395장(8.6%)이 비이진(경계 안티앨리어싱), 4장이 RGBA/RGB입니다. 읽기를 한 함수로 표준화했습니다.'],
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

"""EDS(Electrical Die Sorting) 웨이퍼 테스트 시뮬레이터.

    .venv/bin/python src/sim/eds.py

웨이퍼 테스트는 프로브로 전압을 인가해 출력이 규격에 맞는지 보는 전기 시험이다.
이미지 분석은 여기서 하지 않는다(그건 FA 단계다).

실데이터와 합성의 경계 — 이 경계를 코드에서 분리해 둔다
---------------------------------------------------------------------------
    실데이터 (WM-811K) : 어느 좌표의 다이가 불량인가, 웨이퍼 위 공간 분포
    합성              : 그 다이가 어느 시험에서 어떤 값으로 걸렸는가,
                        fail bit이 칩 안 어느 주소에 있는가

판정 (config/eds_tests.yaml)
    Good        모든 시험 통과
    Repairable  셀 어레이 불량이 있으나 여분 행·열로 전부 덮을 수 있음
    Fail        여분이 모자라거나, 리페어로 대체 불가한 칩 전체 특성 불량

출력: data/processed/eds_results.parquet, eds_summary.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
CONFIG = ROOT / "config" / "eds_tests.yaml"

sys.path.insert(0, str(ROOT))
from src.sim.fail_address import load_cfg as fa_load_cfg  # noqa: E402
from src.sim.fail_address import synth as fa_synth        # noqa: E402

SEED = 20260821

# 셀 어레이 불량 모드를 웨이퍼 패턴별로 어떻게 배분할 것인가 — **전부 가정치**
# 근거: 공개 데이터가 없다. 물리적으로 그럴듯한 방향만 반영했다.
#   Scratch  = 선상 손상 → 워드라인/비트라인 방향 라인성이 늘어난다
#   Loc/Center/Donut/Edge-* = 국소 밀집 → 블록성이 늘어난다
#   Random   = 산발 → 싱글비트가 대부분
# 이 표를 바꾸면 Repairable 비율이 달라진다. 민감도를 함께 본다.
MODE_MIX = {
    "none":      {"single_bit": .70, "row_fail": .10, "column_fail": .10, "block_fail": .08, "cross_fail": .02},
    "Random":    {"single_bit": .85, "row_fail": .05, "column_fail": .05, "block_fail": .04, "cross_fail": .01},
    "Scratch":   {"single_bit": .20, "row_fail": .35, "column_fail": .30, "block_fail": .10, "cross_fail": .05},
    "Loc":       {"single_bit": .25, "row_fail": .10, "column_fail": .10, "block_fail": .50, "cross_fail": .05},
    "Center":    {"single_bit": .25, "row_fail": .10, "column_fail": .10, "block_fail": .50, "cross_fail": .05},
    "Donut":     {"single_bit": .25, "row_fail": .12, "column_fail": .12, "block_fail": .46, "cross_fail": .05},
    "Edge-Loc":  {"single_bit": .30, "row_fail": .12, "column_fail": .12, "block_fail": .41, "cross_fail": .05},
    "Edge-Ring": {"single_bit": .30, "row_fail": .15, "column_fail": .15, "block_fail": .35, "cross_fail": .05},
    "Near-full": {"single_bit": .20, "row_fail": .15, "column_fail": .15, "block_fail": .40, "cross_fail": .10},
}

# 불량 다이 중 '리페어로 대체할 수 없는 칩 전체 특성 불량'의 비율 — (가정치)
# 여분 행·열은 셀 어레이를 대체하는 자원이다. 전류 초과나 배선 오픈/쇼트는
# 대체할 대상이 없어 리페어가 성립하지 않는다.
DIE_LEVEL_RATIO = 0.25

# fail bit 개수 분포 — (가정치). 모드별로 규모가 다르다.
FAIL_BITS = {
    "single_bit": (1, 6), "row_fail": (8, 60), "column_fail": (8, 60),
    "block_fail": (10, 120), "cross_fail": (20, 150),
}


def load_cfg() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# 측정값 합성
# ---------------------------------------------------------------------------
def smooth_field(h: int, w: int, rng: np.random.Generator, scale: float = 6.0) -> np.ndarray:
    """공간적으로 매끄럽게 변하는 값의 장을 만든다.

    같은 영역의 다이는 공정 조건이 비슷하므로 파라메트릭 특성도 서로 닮는다.
    백색잡음을 가우시안으로 흐린 뒤 표준화해 그 성질을 흉내낸다.
    이 구조가 있어야 '이웃을 보고 다음 다이를 예측한다'는 발상이 성립한다.
    """
    from scipy import ndimage
    f = ndimage.gaussian_filter(rng.standard_normal((h, w)), sigma=scale)
    s = f.std()
    return f / s if s > 0 else f


def synth_measurements(dies: pd.DataFrame, meta_row, rng: np.random.Generator,
                       cfg: dict) -> pd.DataFrame:
    """웨이퍼 한 장의 다이별 측정값을 만든다.

    정상 다이도 측정값을 갖는다(규격 안에서). 불량 다이는 실데이터가 정한
    '불량'이라는 사실에 맞춰 어느 항목에서 규격을 벗어나게 만든다.
    """
    h, w = int(meta_row.map_h), int(meta_row.map_w)
    n = len(dies)
    ys, xs = dies.die_y.to_numpy(), dies.die_x.to_numpy()

    # 웨이퍼 전체에 걸친 매끄러운 편차 장 (항목마다 다른 장을 쓴다)
    f_idd = smooth_field(h, w, rng)[ys, xs]
    f_ret = smooth_field(h, w, rng)[ys, xs]
    # 반경 추세: 가장자리로 갈수록 특성이 나빠지는 경향 — (가정치)
    cy, cx = ys.mean(), xs.mean()
    r = np.hypot(ys - cy, xs - cx)
    r = r / r.max() if r.max() > 0 else r

    spec = {t["id"]: t["spec"] for t in cfg["tests"]}
    out = pd.DataFrame({"die_x": xs, "die_y": ys, "is_fail_real": dies.is_fail.to_numpy()})

    # --- 정상 범위 값 생성 ---
    # 정상 다이는 **반드시 규격 안**에 들어와야 한다. 어느 다이가 불량인지는
    # 실데이터(WM-811K)가 정하며, 합성이 그 판정을 뒤집으면 안 된다.
    # 선형식 + 정규잡음으로 만들면 꼬리가 규격을 넘는다(초기 구현의 실패 원인).
    # 로지스틱으로 유계화해 규격 안에 가두되, 공간 상관 구조는 그대로 유지한다.
    def bounded(center_field, radius_coef, lo, hi):
        """(lo, hi) 안에서 공간적으로 매끄럽게 변하는 값을 만든다."""
        z = center_field + radius_coef * (r - 0.5) + rng.normal(0, 0.25, n)
        return lo + (hi - lo) / (1.0 + np.exp(-z))

    # 규격: 핀 전압 [-1.20, -0.40] → 여유를 두고 [-1.05, -0.55]
    out["open_short_v"] = bounded(f_idd, 0.0, -1.05, -0.55)
    # 규격: 대기 전류 ≤ 3.0 mA → [0.70, 2.40]. 가장자리로 갈수록 커진다.
    out["idd_standby_ma"] = bounded(f_idd, 1.2, 0.70, 2.40)
    # 규격: 동작 전류 ≤ 120 mA → [58, 106]
    out["idd_active_ma"] = bounded(f_idd, 1.2, 58.0, 106.0)
    # 규격: 리텐션 ≥ 64 ms → [72, 127]. 가장자리로 갈수록 짧아진다.
    out["retention_hot_ms"] = bounded(f_ret, -1.2, 72.0, 127.0)
    out["fail_bits_room"] = 0
    out["fail_bits_hot"] = 0
    out["fail_mode"] = ""
    out["defect_kind"] = "none"     # none | die_level | cell_array
    return out, spec


def inject_defects(m: pd.DataFrame, spec: dict, pattern: str,
                   rng: np.random.Generator) -> pd.DataFrame:
    """실데이터가 '불량'이라고 정한 다이에 불량 내용을 부여한다.

    어느 다이가 불량인지는 실데이터가 정한다. 그 다이가 **왜** 불량인지는
    공개 데이터가 없어 합성한다. 이 함수가 그 경계다.

    (성능) DataFrame.at 반복은 다이 수가 백만 단위가 되면 병목이 된다.
    numpy 배열로 한 번에 만들고 마지막에 열을 갈아끼운다.
    """
    idx = np.flatnonzero(m.is_fail_real.to_numpy())
    if not len(idx):
        return m

    n = len(idx)
    die_level = rng.random(n) < DIE_LEVEL_RATIO
    mix = MODE_MIX.get(pattern, MODE_MIX["none"])
    names = np.array(list(mix))
    p = np.array(list(mix.values()), dtype=float)
    p = p / p.sum()

    v_os = m.open_short_v.to_numpy().copy()
    v_ids = m.idd_standby_ma.to_numpy().copy()
    v_ida = m.idd_active_ma.to_numpy().copy()
    v_ret = m.retention_hot_ms.to_numpy().copy()
    v_br = m.fail_bits_room.to_numpy().copy()
    v_bh = m.fail_bits_hot.to_numpy().copy()
    v_mode = m.fail_mode.to_numpy().astype(object).copy()
    v_kind = m.defect_kind.to_numpy().astype(object).copy()

    # --- 칩 전체 특성 불량 (리페어 불가) ---
    dl = idx[die_level]
    if len(dl):
        which = rng.choice(["open_short", "idd_standby", "idd_active"], size=len(dl))
        v_kind[dl] = "die_level"
        v_mode[dl] = which
        sel = dl[which == "open_short"]
        if len(sel):
            # 오픈이면 전압이 크게 음(-), 쇼트면 0 근처
            openish = rng.random(len(sel)) < 0.5
            v_os[sel] = np.where(openish,
                                 rng.uniform(-2.5, -1.3, len(sel)),
                                 rng.uniform(-0.35, -0.02, len(sel)))
        sel = dl[which == "idd_standby"]
        if len(sel):
            v_ids[sel] = rng.uniform(3.1, 12.0, len(sel))
        sel = dl[which == "idd_active"]
        if len(sel):
            v_ida[sel] = rng.uniform(121.0, 190.0, len(sel))

    # --- 셀 어레이 불량 (리페어 대상) ---
    ca = idx[~die_level]
    if len(ca):
        modes = rng.choice(names, size=len(ca), p=p)
        lo = np.array([FAIL_BITS[mm][0] for mm in modes])
        hi = np.array([FAIL_BITS[mm][1] for mm in modes])
        nb = rng.integers(lo, hi + 1)
        v_kind[ca] = "cell_array"
        v_mode[ca] = modes
        v_bh[ca] = nb
        # 상온에서 일부, 고온에서 더 많이 드러난다 — (가정치)
        v_br[ca] = (nb * rng.uniform(0.55, 1.0, len(ca))).astype(int)
        # 리텐션 불량이 섞이면 보유 시간이 규격 아래로 내려간다
        ret_bad = ca[rng.random(len(ca)) < 0.35]
        if len(ret_bad):
            v_ret[ret_bad] = rng.uniform(20.0, 63.5, len(ret_bad))

    m["open_short_v"] = v_os
    m["idd_standby_ma"] = v_ids
    m["idd_active_ma"] = v_ida
    m["retention_hot_ms"] = v_ret
    m["fail_bits_room"] = v_br
    m["fail_bits_hot"] = v_bh
    m["fail_mode"] = v_mode
    m["defect_kind"] = v_kind
    return m


# ---------------------------------------------------------------------------
# 리페어 분석
# ---------------------------------------------------------------------------
def repair_analysis(addrs: list[tuple[int, int]], spare_rows: int, spare_cols: int) -> dict:
    """must-repair 우선 탐색으로 여분 행·열 안에 덮이는지 판정한다.

    1. 어떤 row의 fail 수가 남은 여분 열보다 많으면 그 row는 열로 못 덮는다
       → 반드시 행 리페어 (must-repair row)
    2. column도 대칭으로 판정
    3. 강제 배정 후 남은 fail을 남은 여분으로 덮을 수 있는지 본다

    반환에 사용한 행/열 수와 남은 fail 수를 담아 판정 근거를 볼 수 있게 한다.
    """
    from collections import Counter
    remaining = set(addrs)
    used_r, used_c = [], []
    R, C = spare_rows, spare_cols
    steps = []

    while True:
        if not remaining:
            break
        rows = Counter(x for x, _ in remaining)
        cols = Counter(y for _, y in remaining)
        must_r = [x for x, c in rows.items() if c > (C - len(used_c))]
        must_c = [y for y, c in cols.items() if c > (R - len(used_r))]
        if not must_r and not must_c:
            break
        for x in must_r:
            if len(used_r) >= R:
                return {"repairable": False, "reason": "must-repair 행이 여분 행보다 많다",
                        "used_rows": len(used_r), "used_cols": len(used_c),
                        "remaining": len(remaining), "steps": steps}
            used_r.append(x)
            remaining = {a for a in remaining if a[0] != x}
            steps.append(f"행 0x{x:04x} 강제 배정 (그 행의 fail이 남은 여분 열보다 많음)")
        for y in must_c:
            if len(used_c) >= C:
                return {"repairable": False, "reason": "must-repair 열이 여분 열보다 많다",
                        "used_rows": len(used_r), "used_cols": len(used_c),
                        "remaining": len(remaining), "steps": steps}
            used_c.append(y)
            remaining = {a for a in remaining if a[1] != y}
            steps.append(f"열 0x{y:03x} 강제 배정 (그 열의 fail이 남은 여분 행보다 많음)")

    # 남은 fail을 그리디로 덮는다 (가장 많이 덮이는 행/열부터)
    while remaining:
        rows = Counter(x for x, _ in remaining)
        cols = Counter(y for _, y in remaining)
        br, bc = (rows.most_common(1)[0] if rows else (None, 0)), \
                 (cols.most_common(1)[0] if cols else (None, 0))
        can_r, can_c = len(used_r) < R, len(used_c) < C
        if not can_r and not can_c:
            return {"repairable": False, "reason": "여분 행·열을 모두 썼는데 fail이 남았다",
                    "used_rows": len(used_r), "used_cols": len(used_c),
                    "remaining": len(remaining), "steps": steps}
        if can_r and (not can_c or br[1] >= bc[1]):
            used_r.append(br[0])
            remaining = {a for a in remaining if a[0] != br[0]}
            steps.append(f"행 0x{br[0]:04x} 배정 (fail {br[1]}개 덮음)")
        else:
            used_c.append(bc[0])
            remaining = {a for a in remaining if a[1] != bc[0]}
            steps.append(f"열 0x{bc[0]:03x} 배정 (fail {bc[1]}개 덮음)")

    return {"repairable": True, "reason": "여분 행·열 안에서 전부 덮임",
            "used_rows": len(used_r), "used_cols": len(used_c),
            "remaining": 0, "steps": steps}


def grade(row, spec: dict, cfg: dict, rng: np.random.Generator) -> tuple[str, str, dict]:
    """다이 하나의 등급과 그 근거를 낸다."""
    ev = {}
    # 1) 칩 전체 특성 — 리페어로 대체할 수 없다
    checks = [
        ("open_short", "open_short_v", "핀 전압", "V"),
        ("idd_standby", "idd_standby_ma", "대기 전류", "mA"),
        ("idd_active", "idd_active_ma", "동작 전류", "mA"),
    ]
    for tid, col, name, unit in checks:
        s, v = spec[tid], row[col]
        lo, hi = s.get("min"), s.get("max")
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            rng_txt = f"{lo} ~ {hi}" if lo is not None and hi is not None else f"≤ {hi}"
            ev["failed_test"] = tid
            return "fail", (f"{name} {v:.3f} {unit} 이 규격({rng_txt} {unit})을 벗어남. "
                            f"여분 행·열은 셀 어레이를 대체하는 자원이라 "
                            f"이런 칩 전체 특성 불량은 리페어로 살릴 수 없다."), ev

    # 2) 리텐션 (셀 어레이 특성) — 규격 미달이면 fail bit으로 간주해 함께 다룬다
    ret_spec = spec["retention_hot"]["min"]
    ret_bad = row["retention_hot_ms"] < ret_spec

    nb = int(row["fail_bits_hot"])
    if nb == 0 and not ret_bad:
        return "good", "모든 시험을 규격 안에서 통과", ev

    if nb == 0 and ret_bad:
        # 리텐션만 미달인 경우도 셀 단위 불량이므로 소수의 fail bit로 본다 — (가정치)
        nb = int(rng.integers(1, 5))

    return None, "", {"n_fail_bits": nb, "retention_fail": bool(ret_bad)}


def main() -> int:
    cfg = load_cfg()
    fa_cfg = fa_load_cfg()
    R = cfg["repair"]["spare_rows"]
    C = cfg["repair"]["spare_cols"]

    dies = pd.read_parquet(INTERIM / "wafers.parquet")
    meta = pd.read_parquet(INTERIM / "wafers_meta.parquet")
    print(f"입력: 웨이퍼 {len(meta):,}장 / 다이 {len(dies):,}개  (불량 여부는 WM-811K 실데이터)")
    print(f"리페어 자원: 여분 행 {R}, 여분 열 {C}  (가정치)")

    rng = np.random.default_rng(SEED)
    groups = dict(tuple(dies.groupby("wafer_id", sort=False)))
    rows = []

    for mrow in meta.itertuples():
        g = groups[mrow.wafer_id]
        m, spec = synth_measurements(g, mrow, rng, cfg)
        m = inject_defects(m, spec, mrow.pattern_label, rng)

        grades, reasons, used_r, used_c, nbits = [], [], [], [], []
        # (성능) iloc 반복은 다이 수가 백만 단위면 병목이다. dict 레코드로 순회한다.
        for r in m.to_dict("records"):
            gr, reason, ev = grade(r, spec, cfg, rng)
            if gr is not None:
                grades.append(gr); reasons.append(reason)
                used_r.append(0); used_c.append(0); nbits.append(0)
                continue
            nb = ev["n_fail_bits"]
            mode = r["fail_mode"] or "single_bit"
            addrs = fa_synth(mode, nb, rng, fa_cfg)
            res = repair_analysis(addrs, R, C)
            grades.append("repairable" if res["repairable"] else "fail")
            reasons.append(
                f"fail bit {len(addrs)}개({mode}). {res['reason']}. "
                f"여분 행 {res['used_rows']}/{R}, 열 {res['used_cols']}/{C} 사용"
                + (f", {res['remaining']}개 남음" if res["remaining"] else ""))
            used_r.append(res["used_rows"]); used_c.append(res["used_cols"])
            nbits.append(len(addrs))

        m["grade"] = grades
        m["reason"] = reasons
        m["used_spare_rows"] = used_r
        m["used_spare_cols"] = used_c
        m["n_fail_bits"] = nbits
        m["wafer_id"] = mrow.wafer_id
        m["pattern_label"] = mrow.pattern_label
        rows.append(m)

    res = pd.concat(rows, ignore_index=True)

    # --- 자체 검증: 합성이 실데이터의 정상/불량 판정을 뒤집지 않았는가 ---
    # 어느 다이가 불량인지는 실데이터가 정한다. 합성은 '왜 불량인지'만 만든다.
    # 정상 다이가 Fail/Repairable로 가면 합성이 판정을 뒤집은 것이므로 설계 위반이다.
    flipped = int(((~res.is_fail_real) & (res.grade != "good")).sum())
    if flipped:
        print(f"\n검증 실패: 실데이터상 정상인 다이 {flipped:,}개가 Good이 아니다.\n"
              f"합성이 실데이터의 판정을 뒤집었다. 저장하지 않고 중단한다.", file=sys.stderr)
        return 1
    missed = int((res.is_fail_real & (res.grade == "good")).sum())
    if missed:
        print(f"\n검증 실패: 실데이터상 불량인 다이 {missed:,}개가 Good으로 판정됐다.\n"
              f"저장하지 않고 중단한다.", file=sys.stderr)
        return 1
    print(f"\n[검증] 실데이터 판정과 합성 결과가 일치한다 "
          f"(정상→Good {int((~res.is_fail_real).sum()):,}개, "
          f"불량→Repairable/Fail {int(res.is_fail_real.sum()):,}개, 불일치 0)")

    PROCESSED.mkdir(exist_ok=True)
    res.to_parquet(PROCESSED / "eds_results.parquet", index=False)

    # --- 보고 ---
    print(f"\n[표 EDS-1] 다이 등급 분포   (불량 여부는 실데이터 / 측정값과 fail bit은 합성)")
    vc = res.grade.value_counts()
    tot = len(res)
    for k in ["good", "repairable", "fail"]:
        n = int(vc.get(k, 0))
        print(f"  {k:12s}{n:10,}  {n/tot*100:6.2f}%")
    print(f"  {'합계':12s}{tot:10,}  100.00%")

    real_fail = int(res.is_fail_real.sum())
    print(f"\n  실데이터상 불량 다이 {real_fail:,}개 중")
    sub = res[res.is_fail_real]
    print(f"    Repairable로 살린 다이 {int((sub.grade=='repairable').sum()):,}개 "
          f"({(sub.grade=='repairable').mean()*100:.2f}%)")
    print(f"    Fail {int((sub.grade=='fail').sum()):,}개")
  

    print(f"\n[표 EDS-2] 패턴별 등급 비율")
    print(f"  {'패턴':12s}{'다이수':>10s}{'Good':>9s}{'Repairable':>12s}{'Fail':>8s}")
    for p, gsub in res.groupby("pattern_label"):
        n = len(gsub)
        print(f"  {p:12s}{n:10,}"
              f"{(gsub.grade=='good').mean()*100:8.2f}%"
              f"{(gsub.grade=='repairable').mean()*100:11.2f}%"
              f"{(gsub.grade=='fail').mean()*100:7.2f}%")

    print(f"\n[표 EDS-3] 불량 모드별 리페어 성공률 (셀 어레이 불량만)")
    ca = res[res.defect_kind == "cell_array"]
    print(f"  {'모드':14s}{'다이수':>9s}{'Repairable':>12s}{'평균 여분 행':>13s}{'평균 여분 열':>13s}")
    for mode, msub in ca.groupby("fail_mode"):
        print(f"  {mode:14s}{len(msub):9,}{(msub.grade=='repairable').mean()*100:11.2f}%"
              f"{msub.used_spare_rows.mean():13.2f}{msub.used_spare_cols.mean():13.2f}")

    summary = {
        "seed": SEED,
        "spare_rows": R, "spare_cols": C,
        "die_level_ratio": DIE_LEVEL_RATIO,
        "grade_counts": {k: int(vc.get(k, 0)) for k in ["good", "repairable", "fail"]},
        "n_die": tot,
        "by_pattern": {p: {g: float((s.grade == g).mean())
                           for g in ["good", "repairable", "fail"]}
                       for p, s in res.groupby("pattern_label")},
        "by_mode": {m: {"n": int(len(s)),
                        "repairable": float((s.grade == "repairable").mean())}
                    for m, s in ca.groupby("fail_mode")},
    }
    (PROCESSED / "eds_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: data/processed/eds_results.parquet, eds_summary.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

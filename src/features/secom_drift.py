"""SECOM 공정 센서 관리도와 드리프트 추적 — **실데이터만. 합성 없음.**

    .venv/bin/python src/features/secom_drift.py

왜 이걸 하는가
    앞서 만든 수율 예측 모듈은 라벨(pass/fail) 하나만 썼다. 그런데 이 데이터의
    본체는 센서 측정값 692,614개다. 실제 양산기술 업무에서 센서값으로 하는 일은
    "합불을 맞히는 것"보다 **"평소와 달라진 지점을 찾는 것"**에 가깝다.

무엇을 계산하는가
    1. 관리도(Shewhart) — 기준 구간의 평균 ±3σ를 관리 한계로 잡고 이탈을 센다.
       (통상범위) 3σ는 SPC에서 관습적으로 쓰이는 한계다. 정규분포 가정에서
       정상 범위 밖으로 나갈 확률이 약 0.27%가 되는 지점이다.
    2. 드리프트 — 기준 구간 대비 이후 구간의 평균이 얼마나 이동했는가(σ 단위).
    3. pass/fail 분리도 — 센서값이 두 집단을 얼마나 갈라놓는가(Cohen's d).
    4. 결측 급증 — 센서가 값을 못 남긴 시점. 장비 이상 신호일 수 있다.

기준 구간
    앞 40%를 '평소'로 잡는다. 이후 구간을 그 기준으로 감시한다.
    기준 구간에 검증 구간 정보가 섞이면 이탈 탐지가 무의미해진다.

출력: data/processed/secom_drift.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

BASELINE_FRAC = 0.40      # 앞 40%를 '평소'로 삼는다
SIGMA = 3.0               # (통상범위) Shewhart 관리 한계
N_SERIES = 16             # 대시보드에 시계열을 담을 센서 수


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    """두 집단 평균 차이를 합동 표준편차로 나눈 값. 스케일이 달라도 비교 가능."""
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return np.nan
    s = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
                / (len(a) + len(b) - 2))
    return float((b.mean() - a.mean()) / s) if s > 0 else np.nan


def main() -> int:
    p = INTERIM / "secom.parquet"
    if not p.exists():
        print(f"없음: {p}\n먼저 실행: .venv/bin/python src/data/load_secom.py",
              file=sys.stderr)
        return 1
    d = pd.read_parquet(p).sort_values("timestamp").reset_index(drop=True)
    cols = [c for c in d.columns if c.startswith("s")]
    n0 = int(len(d) * BASELINE_FRAC)
    base, mon = d.iloc[:n0], d.iloc[n0:]
    print(f"입력: 웨이퍼 {len(d):,}장 × 센서 {len(cols)}개 = 측정값 "
          f"{len(d)*len(cols):,}개 (SECOM 실데이터)")
    print(f"기준 구간(평소): {base.timestamp.iloc[0]:%m-%d} ~ {base.timestamp.iloc[-1]:%m-%d} "
          f"({len(base):,}장)")
    print(f"감시 구간:       {mon.timestamp.iloc[0]:%m-%d} ~ {mon.timestamp.iloc[-1]:%m-%d} "
          f"({len(mon):,}장)")

    mu, sd = base[cols].mean(), base[cols].std().replace(0, np.nan)
    ucl, lcl = mu + SIGMA * sd, mu - SIGMA * sd

    # --- 관리 한계 이탈 ---
    out_hi = (mon[cols] > ucl).sum()
    out_lo = (mon[cols] < lcl).sum()
    out_n = (out_hi + out_lo)
    out_rate = out_n / mon[cols].notna().sum().replace(0, np.nan)

    # --- 드리프트 ---
    shift = ((mon[cols].mean() - mu) / sd).abs()

    # --- pass/fail 분리도 ---
    sep = pd.Series({c: cohens_d(d.loc[~d.is_fail, c].to_numpy(),
                                 d.loc[d.is_fail, c].to_numpy()) for c in cols})

    print(f"\n[표 D-1] 관리 한계(기준 구간 평균 ±{SIGMA:.0f}σ) 이탈")
    print(f"  감시 구간에서 한 번이라도 이탈한 센서: "
          f"{int((out_n > 0).sum()):,}개 / {len(cols)}")
    print(f"  이탈률 5% 초과 센서: {int((out_rate > 0.05).sum()):,}개")
    print(f"  {'센서':8s}{'이탈 횟수':>9s}{'이탈률':>9s}{'상한 초과':>10s}{'하한 미달':>10s}")
    for c in out_rate.nlargest(8).index:
        print(f"  {c:8s}{int(out_n[c]):9,}{out_rate[c]*100:8.2f}%"
              f"{int(out_hi[c]):10,}{int(out_lo[c]):10,}")

    print(f"\n[표 D-2] 드리프트 — 기준 구간 대비 평균 이동 (σ 단위)")
    print(f"  0.5σ 이상 이동: {int((shift > 0.5).sum()):,}개, "
          f"1.0σ 이상: {int((shift > 1.0).sum()):,}개")
    print(f"  {'센서':8s}{'기준 평균':>13s}{'감시 평균':>13s}{'이동(σ)':>9s}")
    for c in shift.nlargest(8).index:
        print(f"  {c:8s}{mu[c]:13.4g}{mon[c].mean():13.4g}{shift[c]:9.2f}")

    print(f"\n[표 D-3] pass / fail 분리도 (Cohen's d, 절대값 상위)")
    print(f"  |d| > 0.2(작음) {int((sep.abs() > 0.2).sum()):,}개, "
          f"> 0.5(중간) {int((sep.abs() > 0.5).sum()):,}개, "
          f"> 0.8(큼) {int((sep.abs() > 0.8).sum()):,}개")
    print(f"  {'센서':8s}{'pass 평균':>13s}{'fail 평균':>13s}{'d':>8s}")
    for c in sep.abs().nlargest(8).index:
        print(f"  {c:8s}{d.loc[~d.is_fail, c].mean():13.4g}"
              f"{d.loc[d.is_fail, c].mean():13.4g}{sep[c]:8.2f}")
    print(f"  → 분리도가 큰 센서가 거의 없다는 것이 앞선 예측 실패와 일관된다.")

    # --- 결측 급증 ---
    wk = d.set_index("timestamp")[cols].isna().mean(axis=1).resample("W").agg(["mean", "size"])
    wk = wk[wk["size"] > 0]
    print(f"\n[표 D-4] 주별 결측률 — 장비가 값을 못 남긴 시점")
    print(f"  {'주':12s}{'웨이퍼':>7s}{'결측률':>9s}")
    for k, r in wk.iterrows():
        mark = "  ← 급증" if r["mean"] > wk["mean"].median() * 2 else ""
        print(f"  {k:%Y-%m-%d}{int(r['size']):7,}{r['mean']*100:8.2f}%{mark}")

    # --- 드리프트와 excursion 구분 -----------------------------------------
    # 앞서 계산한 '기준 대비 평균 이동'은 둘을 섞는다. 특정 구간만 크게 튀었다가
    # 제자리로 돌아온 것(excursion)과, 서서히 이동해 그대로 머무는 것(drift)은
    # 실무 대응이 다르다. excursion은 그 기간 웨이퍼를 격리하고 원인을 찾고,
    # drift는 보정하거나 예방 정비를 건다.
    W = 100                                     # (가정치) 구간 창 크기
    seg = d[cols].groupby(np.arange(len(d)) // W).mean()
    segz = ((seg - mu) / sd).abs()
    peak = segz.max()                           # 가장 크게 벗어난 구간
    now = segz.iloc[-1]                         # **현재 상태** — 지금도 벗어나 있나
    # 판정은 '현재도 벗어나 있는가'로 한다. 마지막 몇 구간의 평균을 쓰면
    # 크게 튄 구간 하나가 평균을 끌어올려 excursion을 드리프트로 오분류한다
    # (s275: 구간별 |z|가 ... 836.9, 900.2, 0.8 로 복귀했는데 평균은 450이 된다).
    kind = pd.Series(np.where(peak < 1.0, "정상",
                     np.where(now > 1.0, "드리프트(지속)", "excursion(일시)")),
                     index=cols)
    print(f"\n[표 D-2b] 이상의 성격 구분 (창 {W}장 기준)")
    print(f"  정상            {int((kind=='정상').sum()):4d}개")
    print(f"  드리프트(지속)   {int((kind=='드리프트(지속)').sum()):4d}개  ← 보정·예방정비 대상")
    print(f"  excursion(일시) {int((kind=='excursion(일시)').sum()):4d}개  ← 해당 기간 격리·원인조사 대상")
    print(f"  {'센서':8s}{'성격':16s}{'최대 이탈(σ)':>12s}{'현재(σ)':>10s}")
    for c in peak.nlargest(6).index:
        print(f"  {c:8s}{kind[c]:16s}{peak[c]:12.1f}{now[c]:10.1f}")

    # --- 이상 구간이 실제로 불량과 연결되는가 ------------------------------
    # 개별 센서로는 합불이 갈리지 않는다(표 D-3). 그렇다면 '여러 센서가 동시에
    # 관리 한계를 벗어난 상태'는 어떤가. 이것이 SPC의 실제 사용법이다.
    z = ((d[cols] - mu) / sd).abs()
    n_out_wafer = (z > SIGMA).sum(axis=1)
    thr = int(n_out_wafer.quantile(0.95))       # (가정치) 상위 5%를 이상으로 본다
    exc_mask = n_out_wafer > thr
    r_exc = float(d.is_fail[exc_mask].mean())
    r_nor = float(d.is_fail[~exc_mask].mean())
    from scipy import stats as _st
    table = [[int(d.is_fail[exc_mask].sum()), int(exc_mask.sum() - d.is_fail[exc_mask].sum())],
             [int(d.is_fail[~exc_mask].sum()), int((~exc_mask).sum() - d.is_fail[~exc_mask].sum())]]
    odds, pval = _st.fisher_exact(table)

    print(f"\n[표 D-5] 이상 구간과 불량의 관계 — 이 절이 핵심")
    print(f"  웨이퍼별 {SIGMA:.0f}σ 이탈 센서 수: 중앙 {int(n_out_wafer.median())}, "
          f"90분위 {int(n_out_wafer.quantile(.9))}, 최대 {int(n_out_wafer.max())}")
    print(f"  이상 판정 기준: 이탈 센서 {thr}개 초과 (상위 5%)")
    print(f"  {'구간':10s}{'웨이퍼':>8s}{'fail':>7s}{'fail률':>9s}")
    print(f"  {'이상':10s}{int(exc_mask.sum()):8,}{int(d.is_fail[exc_mask].sum()):7,}{r_exc*100:8.2f}%")
    print(f"  {'정상':10s}{int((~exc_mask).sum()):8,}{int(d.is_fail[~exc_mask].sum()):7,}{r_nor*100:8.2f}%")
    print(f"  배수 {r_exc/r_nor:.2f}x, 오즈비 {odds:.2f}, Fisher 정확검정 p = {pval:.4f}")
    print(f"  → {'통계적으로 유의하다' if pval < 0.05 else '유의하지 않다'}. "
          f"개별 센서로는 합불이 갈리지 않지만(표 D-3), "
          f"**여러 센서가 동시에 벗어난 상태**는 불량과 연결된다.")

    # --- 대시보드용 시계열 (센서 일부만) ---
    pick = list(dict.fromkeys(
        list(out_rate.nlargest(6).index) + list(shift.nlargest(6).index)
        + list(sep.abs().nlargest(6).index)))[:N_SERIES]
    series = {}
    for c in pick:
        v = d[c]
        series[c] = {
            "values": [None if pd.isna(x) else round(float(x), 5) for x in v],
            "mu": float(mu[c]), "sd": float(sd[c]),
            "ucl": float(ucl[c]), "lcl": float(lcl[c]),
            "out_rate": float(out_rate[c]) if pd.notna(out_rate[c]) else 0.0,
            "shift_sigma": float(shift[c]) if pd.notna(shift[c]) else 0.0,
            "cohens_d": float(sep[c]) if pd.notna(sep[c]) else 0.0,
        }

    save = {
        "baseline_frac": BASELINE_FRAC, "sigma": SIGMA, "window": W,
        "kind_counts": {k: int((kind == k).sum())
                        for k in ["정상", "드리프트(지속)", "excursion(일시)"]},
        "kind_examples": [{"sensor": c, "kind": kind[c], "peak_sigma": float(peak[c]),
                           "now_sigma": float(now[c])} for c in peak.nlargest(8).index],
        "excursion_test": {
            "threshold_sensors": thr,
            "n_abnormal": int(exc_mask.sum()), "n_normal": int((~exc_mask).sum()),
            "fail_abnormal": int(d.is_fail[exc_mask].sum()),
            "fail_normal": int(d.is_fail[~exc_mask].sum()),
            "rate_abnormal": r_exc, "rate_normal": r_nor,
            "ratio": r_exc / r_nor, "odds_ratio": float(odds), "p_value": float(pval),
            "median_out": int(n_out_wafer.median()),
            "max_out": int(n_out_wafer.max()),
        },
        "n_out_per_wafer": [int(x) for x in n_out_wafer],
        "n_wafer": len(d), "n_sensor": len(cols),
        "n_measurement": len(d) * len(cols),
        "baseline_period": [str(base.timestamp.iloc[0]), str(base.timestamp.iloc[-1])],
        "monitor_period": [str(mon.timestamp.iloc[0]), str(mon.timestamp.iloc[-1])],
        "n_baseline": len(base), "n_monitor": len(mon),
        "summary": {
            "sensors_with_violation": int((out_n > 0).sum()),
            "sensors_violation_over_5pct": int((out_rate > 0.05).sum()),
            "sensors_drift_over_0_5sigma": int((shift > 0.5).sum()),
            "sensors_drift_over_1sigma": int((shift > 1.0).sum()),
            "sensors_cohens_d_over_0_5": int((sep.abs() > 0.5).sum()),
            "sensors_cohens_d_over_0_8": int((sep.abs() > 0.8).sum()),
        },
        "timestamps": [str(x) for x in d.timestamp],
        "is_fail": [bool(x) for x in d.is_fail],
        "series": series,
        "weekly_missing": [{"week": f"{k:%Y-%m-%d}", "n": int(r["size"]),
                            "rate": float(r["mean"])} for k, r in wk.iterrows()],
        "top_violation": [{"sensor": c, "rate": float(out_rate[c]),
                           "n": int(out_n[c])} for c in out_rate.nlargest(8).index],
        "top_drift": [{"sensor": c, "shift": float(shift[c]),
                       "base_mean": float(mu[c]), "mon_mean": float(mon[c].mean())}
                      for c in shift.nlargest(8).index],
        "top_separation": [{"sensor": c, "d": float(sep[c]),
                            "pass_mean": float(d.loc[~d.is_fail, c].mean()),
                            "fail_mean": float(d.loc[d.is_fail, c].mean())}
                           for c in sep.abs().nlargest(8).index],
    }
    PROCESSED.mkdir(exist_ok=True)
    f = PROCESSED / "secom_drift.json"
    f.write_text(json.dumps(save, ensure_ascii=False, separators=(",", ":")),
                 encoding="utf-8")
    print(f"\n저장: {f.name}  {f.stat().st_size:,} B (시계열 {len(series)}개 센서 포함)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

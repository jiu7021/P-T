"""센서별 불량 위험도와 센서 열화 탐지 — **실데이터만. 합성 없음.**

    .venv/bin/python src/features/secom_sensor_risk.py

두 가지 질문에 답한다.

    1. 어느 센서가 튀었을 때 불량이 많이 나오는가  → 센서별 위험 가중치
    2. 어느 센서가 점점 더 자주 튀는가            → 센서 자체의 열화 의심

다중비교 보정 (이 절이 없으면 결과가 전부 가짜다)
    센서 442개를 각각 검정하면, 실제로 아무 관계가 없어도 유의수준 5%에서
    약 22개가 '유의하다'고 나온다. Benjamini-Hochberg 절차로 거짓발견율(FDR)을
    통제한 뒤에 남는 것만 보고한다.

출력: data/processed/secom_sensor_risk.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

BASELINE_FRAC = 0.40
SIGMA = 3.0
N_SEG = 10          # 열화 추세를 볼 구간 수
FDR_Q = 0.10        # (통상범위) 거짓발견율 10%. 탐색 단계에서 흔히 쓰는 값.


def bh_fdr(p: np.ndarray, q: float) -> np.ndarray:
    """Benjamini-Hochberg. 보정 후 기각되는 가설의 불리언 배열을 돌려준다."""
    n = len(p)
    order = np.argsort(p)
    thresh = q * (np.arange(1, n + 1)) / n
    passed = p[order] <= thresh
    k = np.max(np.flatnonzero(passed)) + 1 if passed.any() else 0
    out = np.zeros(n, dtype=bool)
    if k:
        out[order[:k]] = True
    return out


def main() -> int:
    p = INTERIM / "secom.parquet"
    if not p.exists():
        print(f"없음: {p}", file=sys.stderr)
        return 1
    d = pd.read_parquet(p).sort_values("timestamp").reset_index(drop=True)
    cols = [c for c in d.columns if c.startswith("s")]
    n0 = int(len(d) * BASELINE_FRAC)
    mu, sd = d[cols].iloc[:n0].mean(), d[cols].iloc[:n0].std().replace(0, np.nan)
    z = ((d[cols] - mu) / sd).abs()
    out = z > SIGMA                                   # 센서별 이탈 여부 (웨이퍼 × 센서)
    fail = d.is_fail.to_numpy()

    print(f"입력: 웨이퍼 {len(d):,}장 × 센서 {len(cols)}개 (SECOM 실데이터)")
    print(f"기준 구간 앞 {BASELINE_FRAC*100:.0f}% / 이탈 기준 {SIGMA:.0f}σ / "
          f"전체 fail률 {fail.mean()*100:.2f}%")

    # ---------------------------------------------------------------
    # 1. 센서별 위험도 — 그 센서가 튄 웨이퍼의 불량률
    # ---------------------------------------------------------------
    rows = []
    for c in cols:
        o = out[c].to_numpy()
        n_out = int(o.sum())
        if n_out < 10:                                # 표본이 너무 적으면 검정 불가
            continue
        f_out, f_in = fail[o], fail[~o]
        if f_in.sum() == 0:
            continue
        table = [[int(f_out.sum()), int(n_out - f_out.sum())],
                 [int(f_in.sum()), int(len(f_in) - f_in.sum())]]
        odds, pv = stats.fisher_exact(table)
        rows.append({"sensor": c, "n_out": n_out,
                     "fail_when_out": float(f_out.mean()),
                     "fail_when_in": float(f_in.mean()),
                     "risk_ratio": float(f_out.mean() / f_in.mean()) if f_in.mean() else np.nan,
                     "odds_ratio": float(odds), "p": float(pv)})
    R = pd.DataFrame(rows)
    R["significant"] = bh_fdr(R.p.to_numpy(), FDR_Q)
    R = R.sort_values("p")

    print(f"\n[표 R-1] 센서별 위험도 — '이 센서가 튀면 불량이 나오는가'")
    print(f"  검정 가능한 센서 {len(R):,}개 (이탈 10회 이상)")
    print(f"  보정 전 p<0.05 : {int((R.p < 0.05).sum()):,}개  "
          f"← 우연히 나오는 기대치 약 {len(R)*0.05:.0f}개")
    print(f"  BH-FDR {FDR_Q:.0%} 통과: {int(R.significant.sum()):,}개  ← 이것만 신뢰한다")
    if R.significant.any():
        print(f"  {'센서':8s}{'이탈 웨이퍼':>10s}{'이탈시 fail':>12s}{'평소 fail':>11s}"
              f"{'위험비':>8s}{'p':>10s}")
        for _, r in R[R.significant].head(12).iterrows():
            print(f"  {r.sensor:8s}{int(r.n_out):10,}{r.fail_when_out*100:11.2f}%"
                  f"{r.fail_when_in*100:10.2f}%{r.risk_ratio:8.2f}{r.p:10.5f}")
    else:
        print("  보정 후 남는 센서가 없다. 개별 센서의 이탈만으로는 불량을 설명하지 못한다.")

    # ---------------------------------------------------------------
    # 2. 센서 열화 — 이탈 빈도가 시간에 따라 늘어나는가
    # ---------------------------------------------------------------
    seg_id = np.minimum(np.arange(len(d)) // (len(d) // N_SEG), N_SEG - 1)
    deg = []
    for c in cols:
        rate = out[c].groupby(seg_id).mean().to_numpy()
        if rate.sum() == 0:
            continue
        rho, pv = stats.spearmanr(np.arange(len(rate)), rate)
        if np.isnan(rho):
            continue
        deg.append({"sensor": c, "rho": float(rho), "p": float(pv),
                    "first_half": float(rate[:N_SEG//2].mean()),
                    "last_half": float(rate[N_SEG//2:].mean()),
                    "rates": [float(x) for x in rate]})
    Dg = pd.DataFrame(deg)
    Dg["significant"] = bh_fdr(Dg.p.to_numpy(), FDR_Q)
    up = Dg[(Dg.rho > 0) & Dg.significant].sort_values("rho", ascending=False)

    print(f"\n[표 R-2] 센서 열화 의심 — 이탈 빈도가 시간에 따라 **증가**하는 센서")
    print(f"  검정 대상 {len(Dg):,}개 / BH-FDR {FDR_Q:.0%} 통과하며 증가 추세: {len(up):,}개")
    print(f"  {'센서':8s}{'전반 이탈률':>12s}{'후반 이탈률':>12s}{'추세 rho':>10s}{'p':>10s}")
    for _, r in up.head(12).iterrows():
        print(f"  {r.sensor:8s}{r.first_half*100:11.2f}%{r.last_half*100:11.2f}%"
              f"{r.rho:10.2f}{r.p:10.5f}")
    print(f"  → 이탈이 점점 잦아지는 것은 공정 변화일 수도, **센서 자체의 열화**일 수도 있다.")
    print(f"    이 데이터에는 센서 교체·정비 이력이 없어 둘을 구분할 수 없다.")

    # ---------------------------------------------------------------
    # 3. 위험 가중 점수 — 유의한 센서만 써서 웨이퍼별 점수를 만든다
    # ---------------------------------------------------------------
    sig = R[R.significant].sensor.tolist()
    print(f"\n[표 R-3] 위험 가중 점수의 효과")
    if sig:
        w = np.log(R.set_index("sensor").loc[sig, "risk_ratio"].clip(lower=1e-6))
        score = (out[sig].to_numpy() * w.to_numpy()).sum(axis=1)
    else:
        score = out.sum(axis=1).to_numpy().astype(float)
        print("  유의한 센서가 없어 단순 이탈 센서 수를 점수로 쓴다.")
    plain = out.sum(axis=1).to_numpy()
    for nm, s_ in (("가중 점수", score), ("단순 이탈 수", plain)):
        thr = np.quantile(s_, 0.95)
        m = s_ > thr
        if m.sum() == 0 or (~m).sum() == 0:
            continue
        rr = fail[m].mean() / fail[~m].mean()
        _, pv = stats.fisher_exact([[int(fail[m].sum()), int(m.sum() - fail[m].sum())],
                                    [int(fail[~m].sum()), int((~m).sum() - fail[~m].sum())]])
        print(f"  {nm:12s} 상위 5% {int(m.sum()):3d}장  fail {fail[m].mean()*100:6.2f}% "
              f"vs {fail[~m].mean()*100:5.2f}%  배수 {rr:.2f}x  p={pv:.4f}")

    # ---------------------------------------------------------------
    # 4. 정직한 검증 — 가중치를 정한 데이터로 평가하면 과적합이다
    #    앞 구간에서 위험비를 학습하고, 뒤 구간에서만 평가한다.
    # ---------------------------------------------------------------
    print(f"\n[표 R-4] 시간 순 검증 — 가중치는 앞 구간에서만 학습")
    n_learn = int(len(d) * 0.60)
    lo_, hi_ = slice(0, n_learn), slice(n_learn, len(d))
    w_rows = []
    for c in cols:
        o = out[c].to_numpy()[lo_]
        if o.sum() < 10:
            continue
        f_o, f_i = fail[lo_][o], fail[lo_][~o]
        if f_i.sum() == 0 or f_i.mean() == 0:
            continue
        _, pv = stats.fisher_exact([[int(f_o.sum()), int(o.sum() - f_o.sum())],
                                    [int(f_i.sum()), int(len(f_i) - f_i.sum())]])
        w_rows.append({"sensor": c, "rr": f_o.mean() / f_i.mean(), "p": pv})
    Wl = pd.DataFrame(w_rows)
    holdout = {"n_learn": n_learn, "n_eval": len(d) - n_learn}
    if len(Wl):
        Wl["sig"] = bh_fdr(Wl.p.to_numpy(), FDR_Q)
        sig_l = Wl[Wl.sig & (Wl.rr > 1)].sensor.tolist()   # 위험을 높이는 쪽만
        print(f"  학습 구간 {n_learn:,}장에서 FDR 통과하며 위험을 높이는 센서: {len(sig_l)}개")
        ev_fail = fail[hi_]
        if sig_l:
            wv = np.log(Wl.set_index("sensor").loc[sig_l, "rr"].clip(lower=1e-6)).to_numpy()
            sc = (out[sig_l].to_numpy()[hi_] * wv).sum(axis=1)
        else:
            sc = out.sum(axis=1).to_numpy()[hi_].astype(float)
        pl = out.sum(axis=1).to_numpy()[hi_]
        for nm, s_ in (("가중 점수", sc), ("단순 이탈 수", pl)):
            thr = np.quantile(s_, 0.95)
            m = s_ > thr
            if m.sum() == 0 or (~m).sum() == 0 or ev_fail[~m].mean() == 0:
                print(f"  {nm:12s} 평가 불가")
                continue
            rr = ev_fail[m].mean() / ev_fail[~m].mean()
            _, pv = stats.fisher_exact(
                [[int(ev_fail[m].sum()), int(m.sum() - ev_fail[m].sum())],
                 [int(ev_fail[~m].sum()), int((~m).sum() - ev_fail[~m].sum())]])
            print(f"  {nm:12s} 평가 구간 상위 5% {int(m.sum()):3d}장  "
                  f"fail {ev_fail[m].mean()*100:6.2f}% vs {ev_fail[~m].mean()*100:5.2f}%  "
                  f"배수 {rr:.2f}x  p={pv:.4f}")
            holdout[nm] = {"n_flagged": int(m.sum()), "rate_flagged": float(ev_fail[m].mean()),
                           "rate_rest": float(ev_fail[~m].mean()), "ratio": float(rr),
                           "p": float(pv)}
        holdout["n_sig_learned"] = len(sig_l)
    print(f"  → 같은 데이터로 가중치를 정하고 평가하면 과적합이다. 이 표가 실제 성능에 가깝다.")

    save = {
        "holdout": holdout,
        "baseline_frac": BASELINE_FRAC, "sigma": SIGMA, "fdr_q": FDR_Q,
        "n_tested": int(len(R)),
        "n_raw_significant": int((R.p < 0.05).sum()),
        "n_expected_by_chance": float(len(R) * 0.05),
        "n_fdr_significant": int(R.significant.sum()),
        "risk": R[R.significant].head(15).drop(columns=["significant"]).to_dict("records"),
        "risk_all_top": R.head(15).drop(columns=["significant"]).to_dict("records"),
        "degradation": {
            "n_tested": int(len(Dg)), "n_increasing": int(len(up)),
            "top": up.head(12)[["sensor", "rho", "p", "first_half", "last_half", "rates"]]
                     .to_dict("records"),
        },
    }
    PROCESSED.mkdir(exist_ok=True)
    f = PROCESSED / "secom_sensor_risk.json"
    f.write_text(json.dumps(save, ensure_ascii=False, separators=(",", ":")),
                 encoding="utf-8")
    print(f"\n저장: {f.name}  {f.stat().st_size:,} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

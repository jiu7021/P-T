"""SECOM 수율 예측 — **실데이터만. 합성 없음.**

    .venv/bin/python src/model/secom_yield.py

실제 fab 라인의 공정 센서 590개(전처리 후 442개)로 웨이퍼 합불을 예측하고,
어느 센서가 판별에 기여하는지 본다.

분할에 관한 원칙 — 시간 순 분할
    이 데이터에는 타임스탬프가 있고, 월별 fail률이 22.2% → 2.9%로 흔들린다.
    무작위로 섞어 나누면 **미래 웨이퍼로 학습해 과거를 맞히는** 셈이 되어
    성능이 부풀려진다. 실제 라인에서는 과거로 학습해 다음 로트를 판단한다.
    따라서 앞 70%를 학습, 뒤 30%를 검증으로 쓴다.
    비교를 위해 무작위 분할 결과도 함께 내서 편향의 크기를 수치로 보인다.

불균형
    fail 104장 / 1,567장 (6.64%). accuracy는 아무 의미가 없다
    (전부 pass로 찍어도 93.4%). 주 지표는 PR-AUC로 한다.
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

SEED = 20260821
TRAIN_FRAC = 0.70


def prep(tr: pd.DataFrame, te: pd.DataFrame, cols: list[str]):
    """결측 대치와 표준화를 **학습 구간 통계로만** 수행한다.

    검증 구간 값을 써서 대치하면 미래 정보가 새어 들어간다.
    Module A-2에서 이웃 다이 특징에 적용한 원칙과 같다.
    """
    med = tr[cols].median()
    mu, sd = tr[cols].fillna(med).mean(), tr[cols].fillna(med).std().replace(0, 1.0)
    f = lambda d: ((d[cols].fillna(med) - mu) / sd).to_numpy(dtype=np.float64)
    return f(tr), f(te)


def pr_auc(y: np.ndarray, s: np.ndarray) -> float:
    """평균 정밀도(average precision). 불균형 데이터의 표준 지표."""
    from sklearn.metrics import average_precision_score
    return float(average_precision_score(y, s))


def evaluate(y: np.ndarray, s: np.ndarray, base: float) -> dict:
    from sklearn.metrics import roc_auc_score
    ap = pr_auc(y, s)
    # 상위 N개를 재검사 대상으로 올렸을 때 실제 fail을 몇 개 잡는가.
    # 실무에서 "몇 장을 더 볼 여력이 있는가"에 직접 대응한다.
    order = np.argsort(-s)
    hits = {}
    for frac in (0.05, 0.10, 0.20):
        k = max(int(len(y) * frac), 1)
        hits[f"top{int(frac*100)}%"] = {
            "n_reviewed": k,
            "recall": float(y[order[:k]].sum() / max(y.sum(), 1)),
            "precision": float(y[order[:k]].mean()),
        }
    return {"pr_auc": ap, "pr_auc_baseline": base, "lift": ap / base if base else None,
            "roc_auc": float(roc_auc_score(y, s)), "topk": hits}


def run(X: pd.DataFrame, cols: list[str], tr_idx, te_idx, tag: str) -> dict:
    from sklearn.linear_model import LogisticRegression
    import lightgbm as lgb

    tr, te = X.iloc[tr_idx], X.iloc[te_idx]
    Xtr, Xte = prep(tr, te, cols)
    ytr, yte = tr.is_fail.to_numpy(), te.is_fail.to_numpy()
    base = float(yte.mean())

    out = {"tag": tag, "n_train": len(tr), "n_test": len(te),
           "fail_train": int(ytr.sum()), "fail_test": int(yte.sum()),
           "base_rate": base, "models": {}}

    lr = LogisticRegression(max_iter=3000, C=0.05, class_weight="balanced",
                            random_state=SEED)
    lr.fit(Xtr, ytr)
    out["models"]["logistic"] = evaluate(yte, lr.predict_proba(Xte)[:, 1], base)

    gb = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=15,
                            min_child_samples=30, subsample=0.8, colsample_bytree=0.5,
                            class_weight="balanced", random_state=SEED, verbose=-1)
    gb.fit(Xtr, ytr)
    out["models"]["lightgbm"] = evaluate(yte, gb.predict_proba(Xte)[:, 1], base)
    out["_gb"] = gb
    out["_lr"] = lr
    return out


def main() -> int:
    p = INTERIM / "secom.parquet"
    if not p.exists():
        print(f"없음: {p}\n먼저 실행: .venv/bin/python src/data/load_secom.py",
              file=sys.stderr)
        return 1
    X = pd.read_parquet(p).sort_values("timestamp").reset_index(drop=True)
    cols = [c for c in X.columns if c.startswith("s")]
    print(f"입력: 웨이퍼 {len(X):,}장 × 센서 {len(cols):,}개 (SECOM 실데이터, 합성 없음)")
    print(f"  fail {int(X.is_fail.sum()):,}장 ({X.is_fail.mean()*100:.2f}%)")

    n_tr = int(len(X) * TRAIN_FRAC)
    time_tr, time_te = np.arange(n_tr), np.arange(n_tr, len(X))
    print(f"\n시간 순 분할: 학습 {X.timestamp.iloc[0]:%m-%d} ~ "
          f"{X.timestamp.iloc[n_tr-1]:%m-%d} / 검증 {X.timestamp.iloc[n_tr]:%m-%d} ~ "
          f"{X.timestamp.iloc[-1]:%m-%d}")

    rng = np.random.default_rng(SEED)
    perm = rng.permutation(len(X))
    rand_tr, rand_te = perm[:n_tr], perm[n_tr:]

    res_time = run(X, cols, time_tr, time_te, "시간 순 분할")
    res_rand = run(X, cols, rand_tr, rand_te, "무작위 분할")

    print(f"\n[표 S-2] 분할 방식별 성능   (주 지표 PR-AUC. accuracy는 쓰지 않는다)")
    print(f"  {'분할':12s}{'모델':12s}{'PR-AUC':>9s}{'기저율':>9s}{'배수':>7s}{'ROC-AUC':>9s}")
    for r in (res_time, res_rand):
        for m in ("logistic", "lightgbm"):
            v = r["models"][m]
            print(f"  {r['tag']:12s}{m:12s}{v['pr_auc']:9.4f}{v['pr_auc_baseline']:9.4f}"
                  f"{v['lift']:7.2f}{v['roc_auc']:9.4f}")
    print(f"  검증셋 fail 수: 시간 순 {res_time['fail_test']}장 / "
          f"무작위 {res_rand['fail_test']}장")

    d_lr = res_rand["models"]["logistic"]["pr_auc"] - res_time["models"]["logistic"]["pr_auc"]
    d_gb = res_rand["models"]["lightgbm"]["pr_auc"] - res_time["models"]["lightgbm"]["pr_auc"]
    print(f"\n  무작위 분할이 부풀리는 폭: 로지스틱 {d_lr:+.4f}, LightGBM {d_gb:+.4f}")
    print(f"  → 무작위로 섞으면 미래 웨이퍼로 학습해 과거를 맞히게 된다."
          f" 실제 라인 조건은 시간 순 분할이다.")

    print(f"\n[표 S-3] 상위 N%를 재검사에 올렸을 때 (시간 순 분할, LightGBM)")
    tk = res_time["models"]["lightgbm"]["topk"]
    print(f"  {'재검사 비율':12s}{'장수':>7s}{'fail 검출률':>13s}{'정밀도':>9s}")
    for k, v in tk.items():
        print(f"  {k:12s}{v['n_reviewed']:7d}{v['recall']*100:12.1f}%{v['precision']*100:8.1f}%")
    print(f"  (무작위로 골랐다면 검출률은 재검사 비율과 같다: 5% / 10% / 20%)")

    print(f"\n[표 S-4] 기여 센서 상위 12개 (LightGBM, 시간 순 분할)")
    gb = res_time["_gb"]
    imp = pd.Series(gb.feature_importances_, index=cols).sort_values(ascending=False)
    orig = pd.read_parquet(p)
    print(f"  {'센서':8s}{'중요도':>8s}{'pass 평균':>12s}{'fail 평균':>12s}{'차이':>9s}")
    for c in imp.head(12).index:
        a, b = orig.loc[~orig.is_fail, c].mean(), orig.loc[orig.is_fail, c].mean()
        rel = (b - a) / abs(a) * 100 if a else np.nan
        print(f"  {c:8s}{imp[c]:8.0f}{a:12.3f}{b:12.3f}{rel:8.1f}%")
    print(f"  센서 이름은 원본에서 익명화되어 있다. 번호로만 식별된다.")

    PROCESSED.mkdir(exist_ok=True)
    save = {"seed": SEED, "n_wafer": len(X), "n_sensor": len(cols),
            "fail_rate": float(X.is_fail.mean()),
            "period": [str(X.timestamp.min()), str(X.timestamp.max())],
            "time_split": {k: v for k, v in res_time.items() if not k.startswith("_")},
            "random_split": {k: v for k, v in res_rand.items() if not k.startswith("_")},
            "top_sensors": [{"sensor": c, "importance": float(imp[c]),
                             "pass_mean": float(orig.loc[~orig.is_fail, c].mean()),
                             "fail_mean": float(orig.loc[orig.is_fail, c].mean())}
                            for c in imp.head(12).index],
            "monthly": {str(k): {"n": int(v["n"]), "fail": int(v["f"])}
                        for k, v in X.set_index("timestamp").resample("ME").agg(
                            n=("is_fail", "size"), f=("is_fail", "sum")).iterrows()},
            }
    (PROCESSED / "secom_eval.json").write_text(
        json.dumps(save, ensure_ascii=False, indent=2), encoding="utf-8")
    # --- 개선 시도 -------------------------------------------------------
    # "튜닝을 안 해봐서 낮은 것"과 "해봐도 안 오르는 것"은 다르다. 기록해 둔다.
    print(f"\n[표 S-5] 개선 시도 (시간 순 분할 기준)")
    import warnings
    warnings.filterwarnings("ignore")
    from sklearn.feature_selection import mutual_info_classif
    from sklearn.linear_model import LogisticRegression
    import lightgbm as lgb
    tr, te = X.iloc[time_tr], X.iloc[time_te]
    Xtr, Xte = prep(tr, te, cols)
    ytr, yte = tr.is_fail.to_numpy(), te.is_fail.to_numpy()
    b = float(yte.mean())
    trials = {}
    mi = mutual_info_classif(Xtr, ytr, random_state=SEED)
    for k in (30, 60, 120):
        idx = np.argsort(-mi)[:k]
        m = lgb.LGBMClassifier(n_estimators=250, learning_rate=0.05, num_leaves=7,
                               min_child_samples=40, colsample_bytree=0.7,
                               class_weight="balanced", random_state=SEED,
                               verbose=-1).fit(Xtr[:, idx], ytr)
        trials[f"센서 상위 {k}개 선택"] = pr_auc(yte, m.predict_proba(Xte[:, idx])[:, 1])
    for C in (0.005, 0.02):
        m = LogisticRegression(max_iter=4000, C=C, class_weight="balanced",
                               random_state=SEED).fit(Xtr, ytr)
        trials[f"로지스틱 강한 정규화 C={C}"] = pr_auc(yte, m.predict_proba(Xte)[:, 1])
    for w in (300, 600):
        m = lgb.LGBMClassifier(n_estimators=250, learning_rate=0.05, num_leaves=7,
                               min_child_samples=25, colsample_bytree=0.7,
                               class_weight="balanced", random_state=SEED,
                               verbose=-1).fit(Xtr[max(0, len(Xtr)-w):], ytr[max(0, len(ytr)-w):])
        trials[f"최근 {w}장만 학습(드리프트 대응)"] = pr_auc(yte, m.predict_proba(Xte)[:, 1])
    print(f"  {'시도':30s}{'PR-AUC':>9s}{'기저 대비':>10s}")
    for k, v in trials.items():
        print(f"  {k:30s}{v:9.4f}{v/b:9.2f}x")
    print(f"  {'(기본 LightGBM)':30s}"
          f"{res_time['models']['lightgbm']['pr_auc']:9.4f}"
          f"{res_time['models']['lightgbm']['lift']:9.2f}x")
    print(f"\n  최고 {max(trials.values()):.4f} ({max(trials.values())/b:.2f}x). "
          f"어떤 시도도 실용 수준에 이르지 못한다.")
    save["improvement_trials"] = {k: {"pr_auc": v, "lift": v / b} for k, v in trials.items()}
    save["conclusion"] = (
        "시간 순 분할 조건에서 이 데이터만으로는 웨이퍼 합불 예측이 사실상 되지 않는다"
        "(ROC-AUC 0.55~0.59). 무작위 분할은 PR-AUC를 2.5배 부풀린다. "
        "특징 선택·정규화·최근 데이터 학습 등 6가지 시도로도 개선되지 않았다.")
    (PROCESSED / "secom_eval.json").write_text(
        json.dumps(save, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n저장: data/processed/secom_eval.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

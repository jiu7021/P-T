"""A-1. WM-811K 로드 · 선별 · 균형 샘플링.

    .venv/bin/python src/data/load_wm811k.py

출력
    data/interim/wafers.parquet       다이 단위 long 테이블 (선택된 웨이퍼)
    data/interim/wafers_meta.parquet  웨이퍼 단위 메타 (맵 크기, 다이 수, 불량 수)
    data/interim/prev_wafers.parquet  선택 웨이퍼의 '같은 로트 직전 웨이퍼' 다이 테이블
                                      → A-2 특징 계산 전용. 분석 표본이 아니다.

원본 데이터는 재배포하지 않는다. 출처와 필수 인용은 docs/data_sources.md 참조.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PKL = ROOT / "data" / "raw" / "wm811k" / "MIR-WM811K" / "Python" / "WM811K.pkl"
OUT = ROOT / "data" / "interim"

SEED = 20260821          # 난수 시드 고정. 이 값을 바꾸면 이후 모든 결과가 바뀐다.
DIE_MIN, DIE_MAX = 600, 1500
N_TARGET = 2000

# 웨이퍼 맵 픽셀값 정의 (데이터셋 명세)
OUTSIDE, PASS_DIE, FAIL_DIE = 0, 1, 2

PATTERNS = ["none", "Center", "Donut", "Edge-Loc", "Edge-Ring",
            "Loc", "Random", "Scratch", "Near-full"]


def flatten_cell(v) -> str | None:
    """failureType / trainTestLabel 셀을 문자열 하나로 평탄화한다.

    이 두 열은 중첩 ndarray(shape (1,1)), 빈 ndarray(shape (0,0)), 문자열이
    섞여 있다. 곧바로 인덱싱하면 스칼라에서 IndexError가 난다.
    """
    a = np.asarray(v)
    while a.ndim > 0:
        if a.size == 0:
            return None
        a = np.asarray(a.reshape(-1)[0])
    s = a.item() if hasattr(a, "item") else a
    return s if isinstance(s, str) else None


def balanced_quota(available: dict[str, int], total: int) -> dict[str, int]:
    """클래스 균형 할당량 계산.

    균등 몫보다 가용량이 적은 클래스는 전량 배정하고, 남은 할당량을 나머지
    클래스에 다시 균등 배분한다(더 줄 곳이 없을 때까지 반복). 마지막 나머지는
    가용량이 많은 클래스 순으로 1장씩 배분한다 — 결과를 시드와 무관하게
    결정적으로 만들기 위함이다.
    """
    quota = {k: 0 for k in available}
    remaining_classes = set(available)
    remaining = total
    while remaining_classes and remaining > 0:
        share = remaining // len(remaining_classes)
        if share == 0:
            break
        capped = {k for k in remaining_classes if available[k] - quota[k] <= share}
        if capped:
            for k in capped:
                remaining -= available[k] - quota[k]
                quota[k] = available[k]
                remaining_classes.discard(k)
        else:
            for k in remaining_classes:
                quota[k] += share
                remaining -= share
    # 나머지 1장씩
    for k in sorted(remaining_classes, key=lambda k: -available[k]):
        if remaining <= 0:
            break
        if quota[k] < available[k]:
            quota[k] += 1
            remaining -= 1
    return quota


def wafer_to_long(wafer_id: str, wmap: np.ndarray) -> pd.DataFrame:
    """웨이퍼 맵 2차원 배열을 다이 단위 long 테이블로 편다.

    웨이퍼 밖(0)은 제외한다. die_x = 열 인덱스, die_y = 행 인덱스.
    """
    m = np.asarray(wmap)
    ys, xs = np.nonzero(m != OUTSIDE)
    return pd.DataFrame({
        "wafer_id": wafer_id,
        "die_x": xs.astype(np.int16),
        "die_y": ys.astype(np.int16),
        "is_fail": (m[ys, xs] == FAIL_DIE),
    })


def main() -> int:
    if not PKL.exists():
        print(f"원본 파일이 없다: {PKL}\n"
              f"먼저 실행: .venv/bin/python src/data/download.py --only wm811k",
              file=sys.stderr)
        return 1

    print(f"로드: {PKL.name} ({PKL.stat().st_size:,} B)")
    df = pd.read_pickle(PKL)
    df["pattern_label"] = df["failureType"].map(flatten_cell)
    df["lot_id"] = df["lotName"].map(flatten_cell)
    print(f"  전체 {len(df):,}장 / 라벨 보유 {df.pattern_label.notna().sum():,}장")

    # --- 선별 -----------------------------------------------------------
    sel = df[df.pattern_label.notna() & df.dieSize.between(DIE_MIN, DIE_MAX)]
    print(f"  다이 수 {DIE_MIN}~{DIE_MAX} 필터 후 {len(sel):,}장")

    available = {k: int((sel.pattern_label == k).sum()) for k in PATTERNS}
    quota = balanced_quota(available, N_TARGET)
    print("\n  클래스별 가용/할당")
    for k in PATTERNS:
        mark = "  ← 가용량 상한" if quota[k] == available[k] else ""
        print(f"    {k:12s} 가용 {available[k]:6,}  할당 {quota[k]:4,}{mark}")
    print(f"    {'합계':12s} {'':6}       {sum(quota.values()):4,}")

    rng = np.random.default_rng(SEED)
    picks = []
    for k in PATTERNS:                     # 클래스 순서 고정 → 재현 가능
        idx = sel.index[sel.pattern_label == k].to_numpy()
        picks.append(rng.choice(idx, size=quota[k], replace=False))
    chosen = np.sort(np.concatenate(picks))
    w = df.loc[chosen].copy()
    w["wafer_id"] = ["w" + str(i) for i in chosen]

    # --- 다이 단위 테이블 -------------------------------------------------
    dies = pd.concat([wafer_to_long(wid, m)
                      for wid, m in zip(w.wafer_id, w.waferMap)], ignore_index=True)
    meta_cols = w[["wafer_id", "lot_id", "waferIndex", "pattern_label"]].rename(
        columns={"waferIndex": "wafer_index"})
    meta_cols["wafer_index"] = meta_cols["wafer_index"].astype(np.int16)
    dies = dies.merge(meta_cols, on="wafer_id", how="left")
    dies = dies[["wafer_id", "lot_id", "wafer_index", "pattern_label",
                 "die_x", "die_y", "is_fail"]]

    meta = meta_cols.copy()
    meta["map_h"] = [np.asarray(m).shape[0] for m in w.waferMap]
    meta["map_w"] = [np.asarray(m).shape[1] for m in w.waferMap]
    meta["die_count"] = w.dieSize.astype(int).to_numpy()
    g = dies.groupby("wafer_id", sort=False).is_fail
    meta = meta.merge(g.sum().rename("fail_count").reset_index(), on="wafer_id")
    meta["fail_rate"] = meta.fail_count / meta.die_count

    # --- 같은 로트 직전 웨이퍼 (A-2 특징 전용) -----------------------------
    # 균형 샘플링을 하면 같은 로트의 연속 웨이퍼가 함께 뽑힐 확률이 낮다.
    # 따라서 직전 웨이퍼는 원본 전체에서 따로 찾아온다. 라벨·다이 수 필터를
    # 적용하지 않는다 — 특징 계산에만 쓰고 분석 표본에는 넣지 않기 때문이다.
    key = pd.MultiIndex.from_arrays([df.lot_id, df.waferIndex])
    lookup = pd.Series(df.index, index=key)
    lookup = lookup[~lookup.index.duplicated(keep="first")]
    want = pd.MultiIndex.from_arrays([meta.lot_id, meta.wafer_index - 1])
    prev_idx = lookup.reindex(want)
    found = prev_idx.notna().to_numpy()
    print(f"\n  직전 웨이퍼: {found.sum():,}/{len(meta):,}장에서 발견 "
          f"({found.mean()*100:.1f}%)")

    prev_rows = []
    for wid, pidx in zip(meta.wafer_id[found], prev_idx[found].astype(int)):
        prev_rows.append(wafer_to_long(wid, df.at[pidx, "waferMap"]))
    prev = (pd.concat(prev_rows, ignore_index=True) if prev_rows
            else pd.DataFrame(columns=["wafer_id", "die_x", "die_y", "is_fail"]))
    # 맵 크기가 다르면 좌표를 맞출 수 없다. A-2에서 메타와 대조해 걸러야 하므로
    # 직전 웨이퍼의 맵 크기도 함께 남긴다.
    prev_meta = pd.DataFrame({
        "wafer_id": meta.wafer_id[found].to_numpy(),
        "prev_map_h": [np.asarray(df.at[i, "waferMap"]).shape[0]
                       for i in prev_idx[found].astype(int)],
        "prev_map_w": [np.asarray(df.at[i, "waferMap"]).shape[1]
                       for i in prev_idx[found].astype(int)],
    })
    meta = meta.merge(prev_meta, on="wafer_id", how="left")
    same_size = (meta.prev_map_h == meta.map_h) & (meta.prev_map_w == meta.map_w)
    print(f"  그중 맵 크기가 같아 좌표 대조가 가능한 웨이퍼: {int(same_size.sum()):,}장")

    # --- 저장 -------------------------------------------------------------
    OUT.mkdir(parents=True, exist_ok=True)
    dies.to_parquet(OUT / "wafers.parquet", index=False)
    meta.to_parquet(OUT / "wafers_meta.parquet", index=False)
    prev.to_parquet(OUT / "prev_wafers.parquet", index=False)

    print(f"\n저장")
    for f in ["wafers.parquet", "wafers_meta.parquet", "prev_wafers.parquet"]:
        p = OUT / f
        print(f"  {f:24s} {p.stat().st_size:>12,} B")
    print(f"  웨이퍼 {len(meta):,}장 / 다이 {len(dies):,}개")

    # --- 수용 기준 표 1: 패턴 클래스별 웨이퍼 수와 평균 불량률 ---------------
    print("\n[표 A-1] 패턴 클래스별 웨이퍼 수와 불량률   (WM-811K 실데이터)")
    t = (meta.groupby("pattern_label")
              .agg(웨이퍼수=("wafer_id", "size"),
                   다이수합=("die_count", "sum"),
                   불량다이합=("fail_count", "sum"),
                   웨이퍼평균불량률=("fail_rate", "mean")))
    t["전체불량률"] = t.불량다이합 / t.다이수합
    t = t.reindex(PATTERNS)
    print(f"  {'클래스':12s}{'웨이퍼':>7s}{'다이수':>10s}{'불량다이':>10s}"
          f"{'웨이퍼평균불량률':>16s}{'전체불량률':>12s}")
    for k, r in t.iterrows():
        print(f"  {k:12s}{int(r.웨이퍼수):7,}{int(r.다이수합):10,}{int(r.불량다이합):10,}"
              f"{r.웨이퍼평균불량률*100:15.2f}%{r.전체불량률*100:11.2f}%")
    tot_d, tot_f = int(t.다이수합.sum()), int(t.불량다이합.sum())
    print(f"  {'합계':12s}{int(t.웨이퍼수.sum()):7,}{tot_d:10,}{tot_f:10,}"
          f"{meta.fail_rate.mean()*100:15.2f}%{tot_f/tot_d*100:11.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

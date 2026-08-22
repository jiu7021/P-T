"""SECOM 로드 — 실제 fab 라인 공정 센서 데이터. **합성이 하나도 없다.**

    .venv/bin/python src/data/load_secom.py

무엇인가
    실제 반도체 제조 라인에서 웨이퍼 1,567장을 만드는 동안 기록된 공정 센서
    측정값 590개와, 그 웨이퍼가 최종 검사에서 pass인지 fail인지의 결과.
    타임스탬프가 있어 시간 순서를 알 수 있다.

이 프로젝트에서의 위치
    EDS 모듈의 측정값은 합성이다(공개 데이터가 없다). SECOM은 그 빈자리를
    메우지는 못한다 — 성격이 다르다. SECOM은 '공정 장비가 남긴 센서값'이고
    EDS는 '테스터가 잰 전기 특성'이다.
    대신 **가정이 하나도 들어가지 않는 축**을 하나 만든다:
    실제 공정 센서값으로 웨이퍼 합불을 예측하고 어느 센서가 기여하는지 본다.

출력: data/interim/secom.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "secom"
INTERIM = ROOT / "data" / "interim"

# 전처리 기준 — 근거를 함께 적는다
MAX_MISSING_RATIO = 0.40   # (가정치) 결측이 40%를 넘는 센서는 대치해도 신호가 남지 않는다
MIN_UNIQUE = 2             # 값이 하나뿐인 센서는 판별에 기여할 수 없다


def main() -> int:
    f_x, f_y = RAW / "secom.data", RAW / "secom_labels.data"
    if not f_x.exists():
        print(f"없음: {f_x}\n먼저 실행: .venv/bin/python src/data/download.py --only secom",
              file=sys.stderr)
        return 1

    X = pd.read_csv(f_x, sep=r"\s+", header=None, na_values=["NaN"])
    # 라벨 파일은 `-1 "19/07/2008 11:55:00"` 형태다. 따옴표 덕에 날짜와 시각이
    # 한 열로 들어온다(공백으로 쪼개지지 않는다).
    y = pd.read_csv(f_y, sep=r"\s+", header=None, names=["label", "ts"], quotechar='"')
    ts = pd.to_datetime(y.ts, format="%d/%m/%Y %H:%M:%S")
    df = X.copy()
    df.columns = [f"s{i:03d}" for i in range(X.shape[1])]
    df.insert(0, "timestamp", ts)
    # 원본 라벨은 pass = -1, fail = 1. 헷갈리므로 불리언으로 바꾼다.
    df.insert(1, "is_fail", (y.label.to_numpy() == 1))

    print(f"원본: 웨이퍼 {len(df):,}장 × 센서 {X.shape[1]}개")
    print(f"  기간 {ts.min():%Y-%m-%d} ~ {ts.max():%Y-%m-%d} "
          f"({(ts.max()-ts.min()).days}일)")
    print(f"  fail {int(df.is_fail.sum()):,}장 ({df.is_fail.mean()*100:.2f}%) "
          f"→ 불균형 1 : {(~df.is_fail).sum()/df.is_fail.sum():.1f}")
    print(f"  시간 순 정렬 여부: {ts.is_monotonic_increasing}")

    # --- 결측 ---
    sens = [c for c in df.columns if c.startswith("s")]
    miss = df[sens].isna().mean()
    print(f"\n결측")
    print(f"  전체 결측률 {df[sens].isna().to_numpy().mean()*100:.2f}%")
    print(f"  결측이 하나라도 있는 센서 {int((miss > 0).sum()):,}개 / {len(sens):,}개")
    print(f"  결측률 {MAX_MISSING_RATIO*100:.0f}% 초과 센서 {int((miss > MAX_MISSING_RATIO).sum()):,}개 → 제거")

    drop_missing = miss[miss > MAX_MISSING_RATIO].index.tolist()
    keep = [c for c in sens if c not in drop_missing]
    nuniq = df[keep].nunique(dropna=True)
    drop_const = nuniq[nuniq < MIN_UNIQUE].index.tolist()
    print(f"  값이 하나뿐인 센서 {len(drop_const):,}개 → 제거")
    keep = [c for c in keep if c not in drop_const]

    out = df[["timestamp", "is_fail"] + keep].copy()
    # 남은 결측은 중앙값으로 대치한다. 평균은 이상치에 끌려간다.
    # (주의) 대치값은 **학습 구간에서만** 계산해야 미래 정보가 새지 않는다.
    #        여기서는 열을 고르기만 하고, 대치는 분할 이후 모델 쪽에서 한다.
    print(f"\n남은 센서 {len(keep):,}개 (대치는 시간 순 분할 이후에 수행)")

    INTERIM.mkdir(parents=True, exist_ok=True)
    p = INTERIM / "secom.parquet"
    out.to_parquet(p, index=False)
    print(f"저장: {p.name}  {p.stat().st_size:,} B")

    print(f"\n[표 S-1] 월별 웨이퍼 수와 fail률   (SECOM 실데이터, 합성 없음)")
    g = out.set_index("timestamp").resample("ME").agg(
        웨이퍼=("is_fail", "size"), fail=("is_fail", "sum"))
    g["fail률"] = g.fail / g.웨이퍼
    print(f"  {'월':10s}{'웨이퍼':>8s}{'fail':>7s}{'fail률':>9s}")
    for k, r in g.iterrows():
        if r.웨이퍼 == 0:
            continue
        print(f"  {k:%Y-%m}   {int(r.웨이퍼):8,}{int(r.fail):7,}{r['fail률']*100:8.2f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

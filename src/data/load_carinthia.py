"""B-1. Carinthia-S 로드 · 페어링 · 분할.

    .venv/bin/python src/data/load_carinthia.py

분할 단위에 관한 경고 (docs/data_limits.md L5)
    데이터셋에는 웨이퍼·배치·취득시각 등 상위 단위 식별자가 전혀 없다.
    파일명은 32자리 UUID다. 따라서 이미지 단위로 분할할 수밖에 없고,
    같은 웨이퍼의 인접 영역이 학습/검증 양쪽에 들어갈 수 있다.
    **Module B의 성능 수치는 낙관 편향을 가진다.** 일반화 성능이 아니다.

출력
    data/interim/carinthia_index.parquet   경로·라벨·분할·마스크 통계
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "carinthia_s" / "data"
INTERIM = ROOT / "data" / "interim"

SEED = 20260821
FRAC = (0.70, 0.15, 0.15)

MASK_THRESHOLD = 128     # 마스크 이진화 임계값. 아래 load_mask() 주석 참조.


def load_mask(path) -> np.ndarray:
    """마스크를 이진 배열(bool)로 표준화해 읽는다.

    데이터셋 설명서는 "binary segmentation mask"라고 기술하지만, 실제 파일에는
    두 가지 예외가 있다(2026-08-21 전수 확인).

    1. 4,591장 중 **395장(8.6%)이 비이진**이다. 다만 중간값(1~254) 픽셀은
       중앙값 0.044% / 최대 1.67%에 불과해 **결함 경계의 안티앨리어싱**이다.
       마스크가 원본 이미지로 뒤바뀐 경우는 0건이다.
       → 임계값 128로 이진화한다. 결함 픽셀 비율 변화는 중앙값 0.026%p로 무시 가능.
    2. 4장이 L 모드가 아니다(RGBA 2, RGB 2, 모두 class 6). RGBA 2장은 alpha
       채널이 전부 255여서 `array > 0`으로 세면 커버리지가 25%로 잘못 나온다.
       실제 색 채널은 전부 0, 즉 **빈 마스크**다.
       → `convert("L")`로 통일한 뒤 이진화하면 두 문제가 함께 해결된다.

    이 함수를 거치지 않고 마스크를 직접 읽지 않는다.
    """
    with Image.open(path) as im:
        return np.array(im.convert("L")) >= MASK_THRESHOLD


# 설명서에 기재된 사실. 클래스 이름은 공개되어 있지 않다(L6).
CLASS_NOTE = {
    6: "결함 없음 — SEM 정렬 오차로 결함 옆 영역을 촬영한 이미지. 결함 클래스가 아니다.",
    5: "전체 4장. 분할이 성립하지 않는다.",
    2: "전체 8장. 검증셋 표본이 1~2장이라 지표가 무의미하다.",
}


def stratified_split(labels: np.ndarray, seed=SEED, frac=FRAC) -> np.ndarray:
    """클래스별로 나눠 배정한다. 표본이 극히 적은 클래스도 최소 1장씩 배분한다.

    class 5(4장)처럼 표본이 4장뿐이면 어떤 방식으로 나눠도 통계적 의미가 없다.
    그래도 test에 0장이 되면 지표 계산 자체가 안 되므로 최소 1장은 넣는다.
    """
    rng = np.random.default_rng(seed)
    out = np.empty(len(labels), dtype=object)
    for c in np.unique(labels):
        idx = np.flatnonzero(labels == c)
        rng.shuffle(idx)
        n = len(idx)
        n_va = max(1, int(round(n * frac[1]))) if n >= 3 else (1 if n >= 2 else 0)
        n_te = max(1, int(round(n * frac[2]))) if n >= 3 else (1 if n >= 3 else 0)
        n_tr = n - n_va - n_te
        if n_tr < 1:                      # 학습셋이 비면 안 된다
            n_tr, n_va, n_te = max(1, n - 2), min(1, n - 1), max(0, n - 2)
            n_te = n - n_tr - n_va
        out[idx[:n_tr]] = "train"
        out[idx[n_tr:n_tr + n_va]] = "val"
        out[idx[n_tr + n_va:]] = "test"
    return out


def main() -> int:
    csv = RAW / "carinthia-s.csv"
    if not csv.exists():
        print(f"없음: {csv}\n먼저 실행: "
              f".venv/bin/python src/data/download.py --only carinthia", file=sys.stderr)
        return 1

    df = pd.read_csv(csv, sep=";")
    print(f"CSV {len(df):,}행, 열 {list(df.columns)}")

    # --- 페어링 검증 -----------------------------------------------------
    df["img_abs"] = df.image_path.map(lambda p: str(RAW / p))
    df["mask_abs"] = df.mask_path.map(lambda p: str(RAW / p))
    miss_i = sum(not Path(p).exists() for p in df.img_abs)
    miss_m = sum(not Path(p).exists() for p in df.mask_abs)
    print(f"파일 존재 확인: 이미지 결측 {miss_i}, 마스크 결측 {miss_m}, "
          f"filename 중복 {int(df.filename.duplicated().sum())}")
    if miss_i or miss_m:
        print("파일이 빠졌다. 압축 해제를 다시 확인하라.", file=sys.stderr)
        return 1

    # --- 마스크 통계 (전수) ------------------------------------------------
    print(f"마스크 전수 스캔 중 ({len(df):,}장)…")
    cov, npix, sizes, modes, nonbinary = [], [], set(), {}, 0
    for p in df.mask_abs:
        with Image.open(p) as im:
            sizes.add(im.size)
            modes[im.mode] = modes.get(im.mode, 0) + 1
            g = np.array(im.convert("L"))
        if len(np.unique(g)) > 2:
            nonbinary += 1
        b = g >= MASK_THRESHOLD
        npix.append(int(b.sum()))
        cov.append(float(b.mean()))
    df["mask_pixels"] = npix
    df["mask_coverage"] = cov
    print(f"  마스크 크기 고유값: {sorted(sizes)}")
    print(f"  마스크 파일 모드: {modes}  (L이 아닌 파일은 convert('L')로 통일)")
    print(f"  고유값이 3개 이상인 마스크: {nonbinary:,}장 "
          f"({nonbinary/len(df)*100:.2f}%) — 경계 안티앨리어싱. 임계값 "
          f"{MASK_THRESHOLD}로 이진화한다.")

    # --- 분할 -------------------------------------------------------------
    df["split"] = stratified_split(df.label.to_numpy())

    # --- 보고 -------------------------------------------------------------
    print("\n[표 B-1] 클래스 분포와 분할   (Carinthia-S 실데이터)")
    print(f"  {'label':>5s}{'전체':>7s}{'비율':>8s}{'train':>7s}{'val':>5s}{'test':>6s}"
          f"{'빈 마스크':>10s}{'결함픽셀 중앙값':>16s}")
    for c in sorted(df.label.unique()):
        s = df[df.label == c]
        sp = s.split.value_counts()
        empty = int((s.mask_pixels == 0).sum())
        med = s.mask_coverage.median() * 100
        print(f"  {c:5d}{len(s):7,}{len(s)/len(df)*100:7.2f}%"
              f"{sp.get('train',0):7d}{sp.get('val',0):5d}{sp.get('test',0):6d}"
              f"{empty:10d}{med:15.3f}%")
    sp = df.split.value_counts()
    print(f"  {'합계':>5s}{len(df):7,}{100.0:7.1f}%"
          f"{sp.get('train',0):7d}{sp.get('val',0):5d}{sp.get('test',0):6d}"
          f"{int((df.mask_pixels==0).sum()):10d}{df.mask_coverage.median()*100:15.3f}%")

    print("\n  주의 사항 (docs/data_limits.md L6·L7)")
    for c, note in sorted(CLASS_NOTE.items()):
        print(f"    class {c}: {note}")

    print("\n  결함 픽셀 비율 분포 (전체)")
    q = df.mask_coverage.describe([.05, .25, .5, .75, .95])
    for k in ["min", "5%", "25%", "50%", "75%", "95%", "max"]:
        print(f"    {k:>4s} {q[k]*100:8.3f}%")
    print(f"    → 픽셀 단위로도 극단 불균형이다. 세그멘테이션 손실은 BCE 단독이 아니라"
          f" Dice 계열을 병용해야 한다.")

    INTERIM.mkdir(parents=True, exist_ok=True)
    out = INTERIM / "carinthia_index.parquet"
    df.drop(columns=["img_abs", "mask_abs"]).to_parquet(out, index=False)
    print(f"\n저장: {out.name}  {out.stat().st_size:,} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

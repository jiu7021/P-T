"""B-3 준비. 정답 마스크에서 결함의 형태 특징을 측정한다.

    .venv/bin/python src/features/defect_shape.py

왜 형태를 재는가
    Carinthia-S는 결함 클래스 이름을 공개하지 않는다(docs/data_limits.md L6).
    숫자 라벨 1~6에 "particle", "scratch" 같은 이름을 임의로 붙이는 것은 근거
    없는 라벨 생성이다. 대신 **마스크에서 직접 측정되는 형태**를 근거로 삼는다.
    형태는 관측 사실이고, 형태와 원인 공정의 관계는 문헌으로 뒷받침할 수 있다.

측정 항목 (전부 원본 480×480 해상도 기준)
    area_px        결함 픽셀 수
    area_frac      결함 픽셀 비율
    n_components   연결 성분 개수 (8-연결)
    largest_frac   가장 큰 성분이 전체 결함 면적에서 차지하는 비율
    elongation     최대 성분의 주축/부축 비 (2차 모멘트 고유값 비의 제곱근)
    solidity       최대 성분 면적 / 볼록껍질 면적 (오목할수록 작다)
    circularity    4πA/P² (1이면 원, 가늘수록 0에 가깝다)
    center_dist    최대 성분 중심의 이미지 중심으로부터 거리 / 이미지 반경

출력: data/interim/defect_shape.parquet
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "carinthia_s" / "data"
INTERIM = ROOT / "data" / "interim"

sys.path.insert(0, str(ROOT))
from src.data.load_carinthia import load_mask  # noqa: E402


def convex_area(ys: np.ndarray, xs: np.ndarray) -> float:
    """볼록껍질 면적. 점이 3개 미만이면 성분 면적을 그대로 돌려준다."""
    if len(ys) < 3:
        return float(len(ys))
    try:
        from scipy.spatial import ConvexHull
        pts = np.column_stack([xs, ys]).astype(float)
        if np.linalg.matrix_rank(pts - pts.mean(0)) < 2:
            return float(len(ys))
        return float(ConvexHull(pts).volume)      # 2D에서 volume이 면적
    except Exception:
        return float(len(ys))


def shape_of(mask: np.ndarray) -> dict:
    h, w = mask.shape
    area = int(mask.sum())
    out = dict(area_px=area, area_frac=area / mask.size, n_components=0,
               largest_frac=np.nan, elongation=np.nan, solidity=np.nan,
               circularity=np.nan, center_dist=np.nan)
    if area == 0:
        return out

    lab, n = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    sizes = ndimage.sum_labels(mask, lab, index=np.arange(1, n + 1))
    out["n_components"] = int(n)
    k = int(np.argmax(sizes)) + 1
    out["largest_frac"] = float(sizes.max() / area)

    comp = lab == k
    ys, xs = np.nonzero(comp)
    cy, cx = ys.mean(), xs.mean()

    # 2차 중심 모멘트의 고유값으로 주축/부축을 잡는다.
    cov = np.cov(np.vstack([ys - cy, xs - cx]))
    if cov.ndim == 2:
        ev = np.linalg.eigvalsh(cov)
        ev = np.clip(ev, 0, None)
        out["elongation"] = float(np.sqrt(ev[1] / ev[0])) if ev[0] > 1e-9 else float("inf")
    # 둘레: 성분에서 침식한 것을 뺀 경계 픽셀 수
    per = int((comp & ~ndimage.binary_erosion(comp)).sum())
    a = float(sizes.max())
    out["circularity"] = float(4 * np.pi * a / (per ** 2)) if per > 0 else np.nan
    out["solidity"] = float(a / max(convex_area(ys, xs), 1.0))
    out["center_dist"] = float(np.hypot(cy - h / 2, cx - w / 2) / (np.hypot(h, w) / 2))
    return out


def main() -> int:
    idx = INTERIM / "carinthia_index.parquet"
    if not idx.exists():
        print(f"없음: {idx}", file=sys.stderr)
        return 1
    df = pd.read_parquet(idx)

    rows = []
    for i, r in enumerate(df.itertuples()):
        rows.append(shape_of(load_mask(RAW / r.mask_path)))
        if (i + 1) % 1000 == 0:
            print(f"  {i+1:,}/{len(df):,}", flush=True)
    s = pd.DataFrame(rows)
    s.insert(0, "label", df.label.to_numpy())
    s.insert(0, "filename", df.filename.to_numpy())
    s["split"] = df.split.to_numpy()

    out = INTERIM / "defect_shape.parquet"
    s.to_parquet(out, index=False)
    print(f"저장: {out.name}  {out.stat().st_size:,} B")

    print("\n[표 B-3a] 클래스별 결함 형태 (중앙값)   (Carinthia-S 실데이터, 정답 마스크)")
    print(f"  {'class':>5s}{'장수':>6s}{'면적%':>9s}{'성분수':>7s}{'최대성분비':>10s}"
          f"{'가늘기':>8s}{'채움률':>8s}{'원형도':>8s}{'중심거리':>9s}")
    nz = s[s.area_px > 0]
    for c in sorted(s.label.unique()):
        g = nz[nz.label == c]
        if not len(g):
            print(f"  {c:5d}{int((s.label==c).sum()):6d}   (결함 픽셀이 있는 이미지 없음)")
            continue
        print(f"  {c:5d}{len(g):6d}{g.area_frac.median()*100:8.3f}%"
              f"{g.n_components.median():7.0f}{g.largest_frac.median():10.3f}"
              f"{g.elongation.median():8.2f}{g.solidity.median():8.3f}"
              f"{g.circularity.median():8.4f}{g.center_dist.median():9.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

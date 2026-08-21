"""B-2 준비. Carinthia-S 이미지·마스크를 학습 해상도로 캐시한다.

    .venv/bin/python src/data/cache_carinthia.py --size 128

원본은 480×480이다. CPU 학습 실측(U-Net base16, 8스레드):
    128×128  276 s/epoch    192×192  645 s/epoch    256×256  1,246 s/epoch
학습 해상도를 128로 정한 근거는 docs/assumptions.md B-2 참조.

출력: data/interim/carinthia_cache_{size}.npz
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "carinthia_s" / "data"
INTERIM = ROOT / "data" / "interim"

sys.path.insert(0, str(ROOT))
from src.data.load_carinthia import load_mask  # noqa: E402  마스크는 반드시 이 함수로 읽는다


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--size", type=int, default=128)
    args = ap.parse_args()
    S = args.size

    idx = INTERIM / "carinthia_index.parquet"
    if not idx.exists():
        print(f"없음: {idx}\n먼저 실행: "
              f".venv/bin/python src/data/load_carinthia.py", file=sys.stderr)
        return 1
    df = pd.read_parquet(idx)

    imgs = np.zeros((len(df), S, S), dtype=np.uint8)
    masks = np.zeros((len(df), S, S), dtype=bool)
    # 리사이즈 전 원본 결함 픽셀 수. 축소로 얼마나 소실되는지 보고하기 위해 함께 센다.
    src_px = np.zeros(len(df), dtype=np.int32)

    for i, r in enumerate(df.itertuples()):
        with Image.open(RAW / r.image_path) as im:
            imgs[i] = np.array(im.convert("L").resize((S, S), Image.BILINEAR))
        m = load_mask(RAW / r.mask_path)
        src_px[i] = int(m.sum())
        # 마스크는 이진이므로 축소 후에도 이진이어야 한다. 면적 보간 후 0.5로 자르면
        # 작은 결함이 통째로 사라진다. NEAREST는 얇은 구조를 끊는다.
        # 면적 보간 + 임계값 0.25로 절충한다(원본 픽셀의 1/4만 남아도 살린다).
        small = np.array(Image.fromarray((m * 255).astype(np.uint8))
                         .resize((S, S), Image.BOX)) / 255.0
        masks[i] = small >= 0.25

    dst_px = masks.reshape(len(df), -1).sum(1)
    scale = (S / 480) ** 2
    lost = (src_px > 0) & (dst_px == 0)
    print(f"캐시 {S}×{S}: 이미지 {imgs.nbytes/1e6:.1f} MB, 마스크 {masks.nbytes/1e6:.1f} MB")
    print(f"  결함이 있던 이미지 중 축소로 마스크가 완전히 사라진 것: "
          f"{int(lost.sum()):,} / {int((src_px>0).sum()):,} "
          f"({lost.sum()/max((src_px>0).sum(),1)*100:.2f}%)")
    keep = src_px > 0
    ratio = dst_px[keep] / (src_px[keep] * scale)
    print(f"  결함 면적 보존 비율(축소 배율 보정 후): 중앙값 {np.median(ratio):.3f}, "
          f"5분위 {np.percentile(ratio,5):.3f}, 95분위 {np.percentile(ratio,95):.3f}")
    print(f"  원본 결함 픽셀 5분위 미만 이미지의 축소 후 결함 픽셀 수: "
          f"중앙값 {np.median(dst_px[keep][src_px[keep] <= np.percentile(src_px[keep],5)]):.0f}")

    out = INTERIM / f"carinthia_cache_{S}.npz"
    np.savez_compressed(out, imgs=imgs, masks=masks, src_px=src_px,
                        label=df.label.to_numpy(), split=df.split.to_numpy().astype(str),
                        filename=df.filename.to_numpy().astype(str))
    print(f"저장: {out.name}  {out.stat().st_size:,} B")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

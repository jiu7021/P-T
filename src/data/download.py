"""원본 데이터셋 다운로드.

두 데이터셋 모두 인증이 필요 없는 공개 배포처에서 직접 받는다.
이미 받아둔 파일이 있으면 크기를 확인하고 건너뛴다.

    python src/data/download.py            # 둘 다
    python src/data/download.py --only wm811k
    python src/data/download.py --only carinthia
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"

# (출처, 기대 바이트 수). 기대 크기는 2026-08-21 실측값이다.
WM811K_URL = "http://mirlab.org/dataSet/public/MIR-WM811K.zip"
WM811K_BYTES = 344_542_743
CARINTHIA_URL = "https://zenodo.org/records/16895427/files/data.zip?download=1"
CARINTHIA_BYTES = 139_225_942  # 실측 (Zenodo 표기 139.2 MB)
CARINTHIA_DOC_URL = "https://zenodo.org/records/16895427/files/carinthia-s_dataset.html?download=1"


def _download(url: str, dest: Path, expect_bytes: int | None = None) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        size = dest.stat().st_size
        if expect_bytes is None or size == expect_bytes:
            print(f"  이미 있음, 건너뜀: {dest.name} ({size:,} B)")
            return dest
        print(f"  크기 불일치({size:,} != {expect_bytes:,}), 다시 받음: {dest.name}")

    print(f"  받는 중: {url}")
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while chunk := r.read(1 << 20):
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r    {done/total*100:5.1f}%  {done:,} / {total:,} B", end="")
        print()
    tmp.replace(dest)
    size = dest.stat().st_size
    if expect_bytes is not None and size != expect_bytes:
        print(f"  경고: 크기가 기대값과 다르다 ({size:,} != {expect_bytes:,}). "
              f"배포처에서 파일이 갱신되었을 수 있다.", file=sys.stderr)
    print(f"  완료: {dest} ({size:,} B)")
    return dest


def fetch_wm811k() -> None:
    """MIR Lab에서 WM-811K를 받아 Python용 pkl만 풀어낸다.

    zip 전체를 풀면 MATLAB용 .mat(3.6 GB)까지 나와 5.6 GB가 된다.
    본 프로젝트는 pkl만 쓰므로 Python/ 하위만 추출한다.
    """
    print("[WM-811K]")
    zip_path = _download(WM811K_URL, RAW / "wm811k" / "MIR-WM811K.zip", WM811K_BYTES)
    pkl = RAW / "wm811k" / "MIR-WM811K" / "Python" / "WM811K.pkl"
    if pkl.exists():
        print(f"  이미 풀림: {pkl.name} ({pkl.stat().st_size:,} B)")
        return
    print("  Python/ 하위만 압축 해제 중 (MATLAB .mat 3.6 GB는 건너뜀)")
    with zipfile.ZipFile(zip_path) as z:
        members = [n for n in z.namelist() if n.startswith("MIR-WM811K/Python/")]
        z.extractall(RAW / "wm811k", members=members)
    print(f"  완료: {pkl}")


def fetch_carinthia() -> None:
    print("[Carinthia-S]")
    zip_path = _download(CARINTHIA_URL, RAW / "carinthia_s" / "data.zip", CARINTHIA_BYTES)
    csv = RAW / "carinthia_s" / "data" / "carinthia-s.csv"
    if csv.exists():
        print(f"  이미 풀림: {csv.parent}")
    else:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(RAW / "carinthia_s")
        print(f"  완료: {csv.parent}")
    # 클래스 분포·이미지 특징이 기술된 공식 설명서. 데이터 한계 근거로 보관한다.
    _download(CARINTHIA_DOC_URL, RAW / "carinthia_s" / "carinthia-s_dataset.html")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", choices=["wm811k", "carinthia"], help="한쪽만 받는다")
    args = ap.parse_args()

    free_gb = shutil.disk_usage(ROOT).free / 1e9
    if free_gb < 4:
        print(f"디스크 여유 {free_gb:.1f} GB. 최소 4 GB 필요(zip 0.5 GB + 해제분 2.2 GB).",
              file=sys.stderr)
        return 1

    if args.only in (None, "wm811k"):
        fetch_wm811k()
    if args.only in (None, "carinthia"):
        fetch_carinthia()
    print("\n출처와 라이선스: docs/data_sources.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

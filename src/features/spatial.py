"""A-2. 다이 단위 공간 특징 추출.

    .venv/bin/python src/features/spatial.py

핵심 제약 — 미래 정보 누수 금지
------------------------------
테스트는 좌표 순서대로 진행된다. 어떤 다이의 특징을 만들 때, 그 다이보다 **뒤에**
테스트될 다이의 합불을 쓰면 실제 라인에서 재현 불가능한 성능이 나온다.
이 모듈은 스캔 순서를 명시적으로 정의하고, 이웃 집계에서 순서가 앞선 다이만
쓰도록 코드로 강제한다(`_tested_neighbor_stats`). 검증은 `--verify`로 수행한다.

스캔 순서 정의: serpentine(뱀 모양)
    행 0은 왼→오른쪽, 행 1은 오른→왼쪽, 행 2는 다시 왼→오른쪽 …
    근거(통상범위): 프로버는 행 끝에서 되돌아가지 않고 방향을 바꿔 진행하는 것이
    스텝 이동 거리가 짧다. 단방향 래스터로 정의하면 모든 행에서 왼쪽 이웃만
    "이미 테스트됨"이 되어 좌우 비대칭 편향이 특징에 들어간다.

출력
    data/interim/die_features.parquet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"

SEED = 20260821

# 반경 2 이내 이웃 오프셋 (유클리드 거리 ≤ 2, 자기 자신 제외)
_R2 = [(dy, dx) for dy in range(-2, 3) for dx in range(-2, 3)
       if (dy, dx) != (0, 0) and dy * dy + dx * dx <= 4]
_R1 = [(dy, dx) for dy in range(-1, 2) for dx in range(-1, 2) if (dy, dx) != (0, 0)]


def scan_order(h: int, w: int) -> np.ndarray:
    """serpentine 스캔 순서 번호를 (h, w) 배열로 만든다. 0부터 시작.

    웨이퍼 밖 칸도 번호를 받지만, 유효 다이만 남기고 순위를 다시 매기므로
    실제 특징에는 영향이 없다(순서의 대소 관계만 쓰기 때문).
    """
    o = np.arange(h * w, dtype=np.int32).reshape(h, w)
    o[1::2] = o[1::2, ::-1]        # 홀수 행은 방향을 뒤집는다
    return o


def _shift(a: np.ndarray, dy: int, dx: int, fill):
    """배열을 (dy, dx)만큼 민다. 밀려난 자리는 fill로 채운다.

    결과의 [y, x]에는 원본의 [y - dy, x - dx]가 온다. 즉 오프셋 (dy, dx)의
    이웃 값을 자기 자리로 끌어오는 연산이다.
    """
    out = np.full_like(a, fill)
    ys_dst = slice(max(dy, 0), a.shape[0] + min(dy, 0))
    ys_src = slice(max(-dy, 0), a.shape[0] + min(-dy, 0))
    xs_dst = slice(max(dx, 0), a.shape[1] + min(dx, 0))
    xs_src = slice(max(-dx, 0), a.shape[1] + min(-dx, 0))
    out[ys_dst, xs_dst] = a[ys_src, xs_src]
    return out


def _tested_neighbor_stats(fail: np.ndarray, valid: np.ndarray,
                           order: np.ndarray, offsets) -> tuple[np.ndarray, np.ndarray]:
    """이웃 중 **이미 테스트된** 다이의 (불량 수, 개수)를 센다.

    '이미 테스트된' = 유효 다이이면서 스캔 순서 번호가 자기보다 작은 것.
    이 조건이 미래 정보 누수를 막는 유일한 지점이므로 여기 외에서
    이웃을 집계하지 않는다.
    """
    n_fail = np.zeros(fail.shape, dtype=np.int16)
    n_cnt = np.zeros(fail.shape, dtype=np.int16)
    big = np.iinfo(np.int32).max
    for dy, dx in offsets:
        nb_valid = _shift(valid, dy, dx, False)
        nb_order = _shift(order, dy, dx, big)      # 바깥은 '아직 안 됨'으로 취급
        nb_fail = _shift(fail, dy, dx, False)
        earlier = nb_valid & (nb_order < order)    # ← 누수 차단 조건
        n_cnt += earlier
        n_fail += earlier & nb_fail
    return n_fail, n_cnt


def wafer_features(wmap_fail: np.ndarray, valid: np.ndarray,
                   prev_fail: np.ndarray | None) -> pd.DataFrame:
    """웨이퍼 한 장의 다이별 특징을 만든다.

    wmap_fail : 불량이면 True인 (h, w) 배열
    valid     : 유효 다이(웨이퍼 안)면 True인 (h, w) 배열
    prev_fail : 같은 로트 직전 웨이퍼의 불량 배열. 없으면 None.
    """
    h, w = valid.shape
    order = scan_order(h, w)
    ys, xs = np.nonzero(valid)

    # 중심: 유효 다이의 무게중심. 맵 중심이 아니라 실제 다이 배치의 중심이다.
    cy, cx = ys.mean(), xs.mean()
    r = np.hypot(ys - cy, xs - cx)
    r_norm = r / r.max() if r.max() > 0 else np.zeros_like(r)

    # 가장자리까지의 거리: 유효 영역의 거리 변환. 값이 클수록 웨이퍼 안쪽.
    edt = ndimage.distance_transform_edt(valid)
    edge_dist = edt[ys, xs]
    edge_dist_norm = edge_dist / edge_dist.max() if edge_dist.max() > 0 else edge_dist

    f8, c8 = _tested_neighbor_stats(wmap_fail, valid, order, _R1)
    f2, c2 = _tested_neighbor_stats(wmap_fail, valid, order, _R2)

    with np.errstate(invalid="ignore", divide="ignore"):
        rate8 = np.where(c8[ys, xs] > 0, f8[ys, xs] / c8[ys, xs], np.nan)
        rate2 = np.where(c2[ys, xs] > 0, f2[ys, xs] / c2[ys, xs], np.nan)

    # 스캔 진행률: 유효 다이 중 몇 번째로 테스트되는가. 미래 정보가 아니다.
    rank = np.empty(len(ys), dtype=np.int32)
    rank[np.argsort(order[ys, xs], kind="stable")] = np.arange(len(ys))
    scan_progress = rank / max(len(ys) - 1, 1)

    out = pd.DataFrame({
        "die_x": xs.astype(np.int16),
        "die_y": ys.astype(np.int16),
        "is_fail": wmap_fail[ys, xs],
        "scan_rank": rank,
        "scan_progress": scan_progress.astype(np.float32),
        "r_norm": r_norm.astype(np.float32),
        "edge_dist": edge_dist.astype(np.float32),
        "edge_dist_norm": edge_dist_norm.astype(np.float32),
        "nb8_tested_cnt": c8[ys, xs].astype(np.int8),
        "nb8_tested_fail_rate": rate8.astype(np.float32),
        "nb_r2_tested_cnt": c2[ys, xs].astype(np.int8),
        "nb_r2_tested_fail_rate": rate2.astype(np.float32),
    })
    if prev_fail is not None:
        out["prev_wafer_fail"] = prev_fail[ys, xs]
    else:
        out["prev_wafer_fail"] = pd.array([pd.NA] * len(ys), dtype="boolean")
    return out


def _to_map(g: pd.DataFrame, h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
    """long 테이블을 (불량 배열, 유효 배열)로 되돌린다."""
    valid = np.zeros((h, w), dtype=bool)
    fail = np.zeros((h, w), dtype=bool)
    valid[g.die_y.to_numpy(), g.die_x.to_numpy()] = True
    fail[g.die_y.to_numpy(), g.die_x.to_numpy()] = g.is_fail.to_numpy()
    return fail, valid


def verify_no_leakage(feats: pd.DataFrame, dies: pd.DataFrame, meta: pd.DataFrame,
                      n_wafers: int = 20, n_dies: int = 300) -> bool:
    """벡터화 결과를 브루트포스로 재계산해 대조한다.

    벡터화 코드가 '이미 테스트된 이웃만' 조건을 실제로 지키는지는 눈으로
    확인할 수 없다. 무작위 다이를 뽑아 이중 루프로 다시 세고 값이 같은지 본다.
    동시에 '자기보다 순서가 늦은 이웃이 하나도 쓰이지 않았음'을 직접 확인한다.
    """
    rng = np.random.default_rng(SEED)
    wids = rng.choice(meta.wafer_id.to_numpy(), size=min(n_wafers, len(meta)),
                      replace=False)
    checked = mismatch = 0
    for wid in wids:
        m = meta[meta.wafer_id == wid].iloc[0]
        g = dies[dies.wafer_id == wid]
        fail, valid = _to_map(g, int(m.map_h), int(m.map_w))
        order = scan_order(int(m.map_h), int(m.map_w))
        f = feats[feats.wafer_id == wid].set_index(["die_y", "die_x"])
        ys, xs = np.nonzero(valid)
        pick = rng.choice(len(ys), size=min(n_dies, len(ys)), replace=False)
        for i in pick:
            y, x = int(ys[i]), int(xs[i])
            for offs, cnt_col, rate_col in ((_R1, "nb8_tested_cnt", "nb8_tested_fail_rate"),
                                            (_R2, "nb_r2_tested_cnt", "nb_r2_tested_fail_rate")):
                cnt = nf = 0
                for dy, dx in offs:
                    yy, xx = y + dy, x + dx
                    if not (0 <= yy < valid.shape[0] and 0 <= xx < valid.shape[1]):
                        continue
                    if not valid[yy, xx]:
                        continue
                    if order[yy, xx] >= order[y, x]:   # 미래 다이 → 절대 쓰지 않는다
                        continue
                    cnt += 1
                    nf += bool(fail[yy, xx])
                row = f.loc[(y, x)]
                exp_rate = (nf / cnt) if cnt else np.nan
                got_rate = row[rate_col]
                ok = (int(row[cnt_col]) == cnt) and (
                    (np.isnan(exp_rate) and np.isnan(got_rate))
                    or (not np.isnan(exp_rate) and abs(exp_rate - got_rate) < 1e-6))
                checked += 1
                mismatch += (not ok)
    print(f"  브루트포스 대조: {checked:,}건 확인, 불일치 {mismatch}건")
    return mismatch == 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true", help="누수 검증만 다시 수행")
    args = ap.parse_args()

    for f in ("wafers.parquet", "wafers_meta.parquet", "prev_wafers.parquet"):
        if not (INTERIM / f).exists():
            print(f"없음: {INTERIM/f}\n먼저 실행: "
                  f".venv/bin/python src/data/load_wm811k.py", file=sys.stderr)
            return 1

    dies = pd.read_parquet(INTERIM / "wafers.parquet")
    meta = pd.read_parquet(INTERIM / "wafers_meta.parquet")
    prev = pd.read_parquet(INTERIM / "prev_wafers.parquet")
    print(f"입력: 웨이퍼 {len(meta):,}장 / 다이 {len(dies):,}개")

    prev_groups = dict(tuple(prev.groupby("wafer_id", sort=False)))
    meta_by_id = meta.set_index("wafer_id")

    rows = []
    for wid, g in dies.groupby("wafer_id", sort=False):
        m = meta_by_id.loc[wid]
        h, w = int(m.map_h), int(m.map_w)
        fail, valid = _to_map(g, h, w)

        pg = prev_groups.get(wid)
        prev_fail = None
        if pg is not None and int(m.prev_map_h) == h and int(m.prev_map_w) == w:
            prev_fail = np.zeros((h, w), dtype=bool)
            prev_fail[pg.die_y.to_numpy(), pg.die_x.to_numpy()] = pg.is_fail.to_numpy()

        f = wafer_features(fail, valid, prev_fail)
        f.insert(0, "wafer_id", wid)
        rows.append(f)

    feats = pd.concat(rows, ignore_index=True)
    feats = feats.merge(meta[["wafer_id", "lot_id", "wafer_index", "pattern_label"]],
                        on="wafer_id", how="left")
    print(f"특징 생성 완료: {len(feats):,}행 × {feats.shape[1]}열")

    print("\n[누수 검증]")
    ok = verify_no_leakage(feats, dies, meta)
    if not ok:
        print("  불일치가 있다. 저장하지 않고 중단한다.", file=sys.stderr)
        return 1
    # 첫 번째로 테스트되는 다이는 이웃 정보가 있을 수 없다.
    first = feats[feats.scan_rank == 0]
    assert (first.nb8_tested_cnt == 0).all() and (first.nb_r2_tested_cnt == 0).all()
    print(f"  scan_rank=0 다이 {len(first):,}개 모두 이웃 수 0 확인")

    out = INTERIM / "die_features.parquet"
    feats.to_parquet(out, index=False)
    print(f"\n저장: {out.name}  {out.stat().st_size:,} B")

    # --- 수용 기준 표 2: 이웃 불량률 구간별 다이 불량률 ---------------------
    print("\n[표 A-2] 이미 테스트된 8-이웃의 불량률 구간별 다이 불량률   (WM-811K 실데이터)")
    d = feats[feats.nb8_tested_cnt > 0].copy()
    bins = [-.001, 0, .125, .25, .375, .5, .625, .75, .875, 1.0]
    names = ["0 (전부 정상)", "0~0.125", "0.125~0.25", "0.25~0.375", "0.375~0.5",
             "0.5~0.625", "0.625~0.75", "0.75~0.875", "0.875~1.0"]
    d["bin"] = pd.cut(d.nb8_tested_fail_rate, bins=bins, labels=names)
    t = d.groupby("bin", observed=True).agg(다이수=("is_fail", "size"),
                                            불량률=("is_fail", "mean"))
    base = feats.is_fail.mean()
    print(f"  {'이웃 불량률':16s}{'다이 수':>12s}{'해당 다이 불량률':>18s}{'전체 대비':>12s}")
    for k, r in t.iterrows():
        print(f"  {str(k):16s}{int(r.다이수):12,}{r.불량률*100:17.2f}%"
              f"{r.불량률/base:11.2f}x")
    print(f"  {'(전체 평균)':16s}{len(feats):12,}{base*100:17.2f}%{1.0:11.2f}x")
    print(f"\n  이웃 정보가 없는 다이(스캔 초입): {(feats.nb8_tested_cnt==0).sum():,}개 "
          f"({(feats.nb8_tested_cnt==0).mean()*100:.2f}%)")

    print("\n[표 A-2b] 직전 웨이퍼 동일 좌표 불량 여부별 다이 불량률")
    pv = feats[feats.prev_wafer_fail.notna()]
    if len(pv):
        for v in (False, True):
            s = pv[pv.prev_wafer_fail == v]
            print(f"  직전 웨이퍼 {'불량' if v else '정상':4s}: {len(s):10,}개  "
                  f"불량률 {s.is_fail.mean()*100:6.2f}%  ({s.is_fail.mean()/base:.2f}x)")
        print(f"  직전 웨이퍼 정보 없음: {feats.prev_wafer_fail.isna().sum():,}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""EDS 판정의 민감도 분석.

    .venv/bin/python src/sim/eds_sensitivity.py --wafers 200

EDS 시뮬레이터의 가정 중 셋이 Good/Repairable/Fail 비율을 직접 정한다.

    1. 여분 행·열 개수          (docs/assumptions.md EDS-c)
    2. 리페어 불가 비율          (EDS-d)
    3. 웨이퍼 패턴별 불량 모드 배분 (EDS-e)

값을 바꿔가며 결론이 얼마나 흔들리는지 본다. 흔들리면 그것도 결과다. 숨기지 않는다.

전체 2,000장은 느리므로 웨이퍼를 층화 추출해 돌린다(기본 200장).
절대값이 아니라 **조건 간 상대 변화**를 보는 것이 목적이다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"

SEED = 20260821


def run_once(meta: pd.DataFrame, groups: dict, cfg, fa_cfg, spare_r: int, spare_c: int,
             die_ratio: float, mode_mix: dict | None, seed: int = SEED) -> dict:
    """주어진 조건으로 등급 비율을 낸다."""
    import src.sim.eds as E
    old_ratio, old_mix = E.DIE_LEVEL_RATIO, E.MODE_MIX
    E.DIE_LEVEL_RATIO = die_ratio
    if mode_mix is not None:
        E.MODE_MIX = mode_mix
    try:
        rng = np.random.default_rng(seed)
        cnt = {"good": 0, "repairable": 0, "fail": 0}
        for mrow in meta.itertuples():
            g = groups[mrow.wafer_id]
            m, spec = E.synth_measurements(g, mrow, rng, cfg)
            m = E.inject_defects(m, spec, mrow.pattern_label, rng)
            arr = m.to_dict("records")            # iloc 반복보다 훨씬 빠르다
            for r in arr:
                gr, _, ev = E.grade(r, spec, cfg, rng)
                if gr is not None:
                    cnt[gr] += 1
                    continue
                addrs = E.fa_synth(r["fail_mode"] or "single_bit",
                                          ev["n_fail_bits"], rng, fa_cfg)
                res = E.repair_analysis(addrs, spare_r, spare_c)
                cnt["repairable" if res["repairable"] else "fail"] += 1
        tot = sum(cnt.values())
        return {k: v / tot for k, v in cnt.items()} | {"n": tot}
    finally:
        E.DIE_LEVEL_RATIO, E.MODE_MIX = old_ratio, old_mix


def main() -> int:
    import sys
    sys.path.insert(0, str(ROOT))
    import src.sim.eds as E
    from src.sim.fail_address import load_cfg as fa_load

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wafers", type=int, default=200)
    args = ap.parse_args()

    cfg, fa_cfg = E.load_cfg(), fa_load()
    dies = pd.read_parquet(INTERIM / "wafers.parquet")
    meta_all = pd.read_parquet(INTERIM / "wafers_meta.parquet")

    # 패턴 균형을 유지한 채 층화 추출
    rng = np.random.default_rng(SEED)
    per = max(args.wafers // meta_all.pattern_label.nunique(), 1)
    picks = []
    for p, sub in meta_all.groupby("pattern_label"):
        take = sub.sample(min(per, len(sub)), random_state=SEED)
        picks.append(take)
    meta = pd.concat(picks).reset_index(drop=True)
    groups = dict(tuple(dies[dies.wafer_id.isin(meta.wafer_id)].groupby("wafer_id", sort=False)))
    print(f"민감도 표본: 웨이퍼 {len(meta)}장 / 다이 "
          f"{sum(len(g) for g in groups.values()):,}개")

    R0, C0 = cfg["repair"]["spare_rows"], cfg["repair"]["spare_cols"]
    base = run_once(meta, groups, cfg, fa_cfg, R0, C0, E.DIE_LEVEL_RATIO, None)
    print(f"\n기준 조건 (여분 {R0}행/{C0}열, 리페어불가 {E.DIE_LEVEL_RATIO:.2f})")
    print(f"  Good {base['good']*100:.2f}%  Repairable {base['repairable']*100:.2f}%  "
          f"Fail {base['fail']*100:.2f}%")

    out = {"base": base, "spare": {}, "die_ratio": {}, "mode_mix": {}}

    print(f"\n[민감도 1] 여분 행·열 개수")
    print(f"  {'여분':>10s}{'Good':>9s}{'Repairable':>12s}{'Fail':>8s}")
    for r, c in [(2, 2), (3, 3), (4, 4), (6, 6), (8, 8)]:
        v = run_once(meta, groups, cfg, fa_cfg, r, c, E.DIE_LEVEL_RATIO, None)
        out["spare"][f"{r}r{c}c"] = v
        mark = "  ← 기준" if (r, c) == (R0, C0) else ""
        print(f"  {f'{r}행/{c}열':>10s}{v['good']*100:8.2f}%{v['repairable']*100:11.2f}%"
              f"{v['fail']*100:7.2f}%{mark}")

    print(f"\n[민감도 2] 리페어 불가(칩 전체 특성) 비율")
    print(f"  {'비율':>10s}{'Good':>9s}{'Repairable':>12s}{'Fail':>8s}")
    for dr in [0.10, 0.15, 0.25, 0.40, 0.60]:
        v = run_once(meta, groups, cfg, fa_cfg, R0, C0, dr, None)
        out["die_ratio"][f"{dr:.2f}"] = v
        mark = "  ← 기준" if abs(dr - E.DIE_LEVEL_RATIO) < 1e-9 else ""
        print(f"  {f'{dr:.2f}':>10s}{v['good']*100:8.2f}%{v['repairable']*100:11.2f}%"
              f"{v['fail']*100:7.2f}%{mark}")

    print(f"\n[민감도 3] 불량 모드 배분 시나리오")
    scen = {
        "기준": None,
        "싱글비트 편중": {k: {"single_bit": .90, "row_fail": .03, "column_fail": .03,
                          "block_fail": .03, "cross_fail": .01} for k in E.MODE_MIX},
        "라인성 편중": {k: {"single_bit": .15, "row_fail": .35, "column_fail": .35,
                        "block_fail": .10, "cross_fail": .05} for k in E.MODE_MIX},
        "블락성 편중": {k: {"single_bit": .15, "row_fail": .08, "column_fail": .07,
                        "block_fail": .60, "cross_fail": .10} for k in E.MODE_MIX},
    }
    print(f"  {'시나리오':>14s}{'Good':>9s}{'Repairable':>12s}{'Fail':>8s}")
    for name, mix in scen.items():
        v = base if mix is None else run_once(meta, groups, cfg, fa_cfg, R0, C0,
                                              E.DIE_LEVEL_RATIO, mix)
        out["mode_mix"][name] = v
        print(f"  {name:>14s}{v['good']*100:8.2f}%{v['repairable']*100:11.2f}%"
              f"{v['fail']*100:7.2f}%")

    PROCESSED.mkdir(exist_ok=True)
    (PROCESSED / "eds_sensitivity.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n저장: data/processed/eds_sensitivity.json")

    # --- 결론 요약 ---
    sp = out["spare"]
    rep_range = (min(v["repairable"] for v in sp.values()),
                 max(v["repairable"] for v in sp.values()))
    dr = out["die_ratio"]
    fail_range = (min(v["fail"] for v in dr.values()), max(v["fail"] for v in dr.values()))
    mm = out["mode_mix"]
    mm_range = (min(v["repairable"] for v in mm.values()),
                max(v["repairable"] for v in mm.values()))
    print(f"\n[결론] 가정이 결론을 얼마나 흔드는가")
    print(f"  여분 2~8행/열   → Repairable {rep_range[0]*100:.2f}% ~ {rep_range[1]*100:.2f}% "
          f"(폭 {(rep_range[1]-rep_range[0])*100:.2f}%p)")
    print(f"  리페어불가 0.10~0.60 → Fail {fail_range[0]*100:.2f}% ~ {fail_range[1]*100:.2f}% "
          f"(폭 {(fail_range[1]-fail_range[0])*100:.2f}%p)")
    print(f"  모드 배분 시나리오   → Repairable {mm_range[0]*100:.2f}% ~ {mm_range[1]*100:.2f}% "
          f"(폭 {(mm_range[1]-mm_range[0])*100:.2f}%p)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

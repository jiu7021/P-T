"""B-3. 결함 형태 → 원인 공정 후보 룩업.

    .venv/bin/python src/model/cause_lookup.py

이 모듈은 **모델이 아니다.** config/cause_map.yaml을 읽어 조회할 뿐이며,
학습하지 않고 파라미터도 없다. AI가 원인 공정을 예측하지 않는다는 프로젝트
절대 원칙을 코드 구조로 지킨다.

출력: data/processed/cause_lookup.json  (대시보드가 그대로 읽는다)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config" / "cause_map.yaml"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"


def load_map() -> dict:
    with open(CONFIG, encoding="utf-8") as f:
        m = yaml.safe_load(f)
    # 근거 없는 항목이 들어오지 못하게 로드 시점에 막는다.
    for morph, v in m["morphologies"].items():
        for c in v["candidates"]:
            if not c.get("rationale") or not c.get("reference"):
                raise ValueError(f"근거 또는 출처가 없는 후보: {morph} / {c.get('process')}")
    return m


def morphology(area_px: int, elongation: float, thresholds: dict) -> str:
    """형태 유형을 판정한다. 임계값은 YAML에 있는 값을 그대로 쓴다.

    임계값을 코드에 하드코딩하지 않는 이유: 근거와 값이 한곳(YAML)에 있어야
    나중에 값만 바뀌고 근거가 남는 사고를 막을 수 있다.
    """
    if area_px == 0:
        return "none"
    if not np.isfinite(elongation):
        return "linear_fine"          # 부축이 0이면 완전한 직선이다
    if elongation < 3:
        return "compact"
    if elongation < 30:
        return "linear_broad"
    return "linear_fine"


def candidates_for(morph: str, m: dict) -> list[dict]:
    return m["morphologies"][morph]["candidates"]


def main() -> int:
    m = load_map()
    print(f"cause_map v{m['meta']['version']} | is_model={m['meta']['is_model']} | "
          f"결정 주체={m['meta']['decision_owner']}")

    shape_path = INTERIM / "defect_shape.parquet"
    if not shape_path.exists():
        print(f"없음: {shape_path}\n먼저 실행: "
              f".venv/bin/python src/features/defect_shape.py", file=sys.stderr)
        return 1
    s = pd.read_parquet(shape_path)
    s["morphology"] = [morphology(a, e, m["morphology_rules"]["thresholds"])
                       for a, e in zip(s.area_px, s.elongation)]

    print("\n[표 B-3b] 라벨 × 형태 유형 교차표   (Carinthia-S 실데이터, 정답 마스크)")
    ct = pd.crosstab(s.label, s.morphology)
    order = [c for c in ["none", "compact", "linear_broad", "linear_fine"] if c in ct.columns]
    ct = ct[order]
    print(f"  {'label':>5s}" + "".join(f"{c:>14s}" for c in ct.columns) + f"{'합계':>8s}")
    for lb, r in ct.iterrows():
        print(f"  {lb:5d}" + "".join(f"{int(v):14,}" for v in r) + f"{int(r.sum()):8,}")
    print(f"  {'합계':>5s}" + "".join(f"{int(v):14,}" for v in ct.sum()) + f"{int(ct.values.sum()):8,}")

    print("\n  형태 유형별 원인 공정 후보 수")
    for morph in ct.columns:
        cands = candidates_for(morph, m)
        refs = sum(len(c["reference"]) for c in cands)
        print(f"    {morph:14s} 후보 {len(cands)}개, 출처 {refs}건")

    s.to_parquet(INTERIM / "defect_shape.parquet", index=False)

    PROCESSED.mkdir(exist_ok=True)
    out = {
        "meta": m["meta"],
        "morphology_rules": m["morphology_rules"],
        "morphologies": m["morphologies"],
        "observed_crosstab": {str(k): {c: int(v) for c, v in row.items()}
                              for k, row in ct.iterrows()},
    }
    (PROCESSED / "cause_lookup.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\n저장: data/processed/cause_lookup.json")
    print(f"\n  {m['meta']['disclaimer']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
